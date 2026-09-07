import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# --- 1. CONEXIÓN OFICIAL DE STREAMLIT ---
# Esto usa el bloque [connections.gsheets] de tus Secrets
try:
    con = st.connection("gsheets", type="gsheets")
except Exception as e:
    st.error(f"Error crítico de conexión: {e}")
    st.stop()

# --- 2. FUNCIONES DE AYUDA ---
def limpiar_numero(valor):
    if not valor: return 0.0
    try:
        texto = str(valor).replace('$', '').replace(' ', '').strip()
        if not texto: return 0.0
        # Formato latino: 1.234,56 -> 1234.56
        if ',' in texto and '.' in texto:
            if texto.rfind(',') > texto.rfind('.'):
                texto = texto.replace('.', '').replace(',', '.')
            else:
                texto = texto.replace(',', '')
        elif ',' in texto:
            texto = texto.replace(',', '.')
        return float(texto)
    except:
        return 0.0

def formatear_numero(valor):
    if not valor: return "$ 0,00"
    formato = f"${valor:,.2f}"
    return formato.replace(",", "X").replace(".", ",").replace("X", ".")

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data():
    # ID de tu hoja
    url = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA"
    try:
        # Usamos el conector para leer
        df = con.query(url)
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame()

# --- 4. INICIALIZACIÓN ---
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# --- 5. INTERFAZ ---
st.title("📊 Control Diario Nova")

if df_trabajo.empty:
    st.warning("⚠️ No hay datos o error de conexión.")
else:
    # Normalizar columnas si faltan
    for col in ["FECHA", "CUENTA", "USD", "Bs"]:
        if col not in df_trabajo.columns:
            df_trabajo[col] = None

    # MÉTRICAS
    # Filtramos hoy
    mask_hoy = df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)
    df_hoy = df_trabajo[mask_hoy]
    
    # Sumamos limpiando los números
    total_usd = df_hoy["USD"].apply(limpiar_numero).sum()
    total_bs = df_hoy["Bs"].apply(limpiar_numero).sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("TOTAL USD HOY", formatear_numero(total_usd))
    col2.metric("TOTAL Bs HOY", formatear_numero(total_bs))
    col3.metric("COMISIÓN (15%)", formatear_numero(total_usd * 0.15))
    
    st.markdown("---")
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("📝 Nueva Transacción")
        with st.form(key="add_form", clear_on_submit=True):
            cuenta = st.text_input("CUENTA:").upper()
            usd = st.number_input("USD:", min_value=0.0, step=0.01)
            bs = st.number_input("Bs:", min_value=0.0, step=0.01)
            
            if st.form_submit_button("✓ AGREGAR"):
                if cuenta:
                    nueva = {
                        "FECHA": hoy_str,
                        "CUENTA": cuenta,
                        "USD": formatear_numero(usd),
                        "Bs": formatear_numero(bs)
                    }
                    # Añadir a la sesión
                    st.session_state.df_base = pd.concat([st.session_state.df_base, pd.DataFrame([nueva])], ignore_index=True)
                    st.success("Agregado. Sincroniza para guardar.")
                    st.rerun()

    with col_der:
        st.subheader("🔍 Historial")
        mes = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
        anio = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
        patron = f"/{mes.zfill(2)}/{anio}"
        
        # Filtrar
        mask_filtro = df_trabajo["FECHA"].astype(str).str.contains(patron, na=False)
        df_filtrado = df_trabajo[mask_filtro]
        
        if not df_filtrado.empty:
            # Editor
            # Convertimos a lista de diccionarios para que el editor sea compatible
            datos_lista = df_filtrado.to_dict('records')
            
            df_editado = st.data_editor(
                datos_lista,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_oficial",
                hide_index=True,
                column_config={
                    "FECHA": st.column_config.TextColumn("Fecha"),
                    "CUENTA": st.column_config.TextColumn("Cuenta"),
                    "USD": st.column_config.TextColumn("USD"),
                    "Bs": st.column_config.TextColumn("Bs"),
                }
            )
            
            st.markdown("---")
            
            if st.button("💾 GUARDAR EN GOOGLE SHEETS", type="primary", use_container_width=True):
                # 1. Obtener datos editados
                datos_editados = df_editado if isinstance(df_editado, list) else df_editado.to_dict('records')
                
                # 2. Reconstruir dataframe completo
                # Quitamos lo que estaba filtrado
                df_sin_filtro = df_trabajo[~mask_filtro]
                # Convertimos lo editado a DataFrame
                df_nuevo = pd.DataFrame(datos_editados)
                # Unimos
                df_final = pd.concat([df_sin_filtro, df_nuevo], ignore_index=True)
                
                # 3. Guardar usando el conector
                try:
                    # El conector de streamlit tiene un método para escribir
                    # OJO: Esto requiere que la hoja esté limpia o use append/update según versión
                    # La forma más segura con el conector nativo es a menudo usar gspread interno
                    # Pero intentemos con la escritura nativa si está disponible, si no, usamos fallback
                    
                    # Fallback robusto: Usar gspread directamente ya que tenemos las credenciales en secrets
                    import gspread
                    from google.oauth2.service_account import Credentials
                    
                    # Cargar creds desde secrets
                    creds_dict = {
                        "type": "service_account",
                        "project_id": st.secrets["connections"]["gsheets"]["project_id"],
                        "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
                        "private_key": st.secrets["connections"]["gsheets"]["private_key"],
                        "client_email": st.secrets["connections"]["gsheets"]["client_email"],
                        "client_id": st.secrets["connections"]["gsheets"]["client_id"]
                    }
                    
                    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                    gc = gspread.authorize(creds)
                    sh = gc.open_by_key("16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA").sheet1
                    
                    # Preparar datos para gspread
                    if not df_final.empty:
                        headers = list(df_final.columns)
                        rows = [headers]
                        # Llenar NaN con string vacío para evitar errores en gspread
                        df_final = df_final.fillna("")
                        for _, row in df_final.iterrows():
                            rows.append([str(v) for v in row.values])
                        
                        sh.clear()
                        sh.update(range="A1", values=rows)
                        
                    st.success("✅ ¡Guardado exitosamente!")
                    st.session_state.df_base = load_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        else:
            st.info("📭 No hay datos para este periodo.")
