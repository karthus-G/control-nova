import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Diario Nova", layout="wide")

# 1. CONEXIÓN A GOOGLE SHEETS (Usando Secrets)
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Cargar credenciales del secrets.toml
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    
    # ID de tu hoja
    spreadsheet_id = "16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA"
    sheet = gc.open_by_key(spreadsheet_id).sheet1
    return sheet

# 2. FUNCIONES DE FORMATO
def formatear_numero(valor):
    """Convierte número a formato latino: $ 1.234,56"""
    if not valor: return "$ 0,00"
    formato = f"${valor:,.2f}"
    return formato.replace(",", "X").replace(".", ",").replace("X", ".")

def limpiar_numero(valor):
    """Convierte texto a número para cálculos"""
    if not valor: return 0.0
    try:
        texto = str(valor).replace('$', '').replace(' ', '').strip()
        if not texto: return 0.0
        # Manejo básico de formatos
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

# 3. CARGA Y GUARDADO
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = get_sheet()
        # get_all_records convierte a lista de diccionarios
        return sheet.get_all_records()
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return []

def save_data(data_list):
    """Reemplaza TODOS los datos de la hoja con la nueva lista"""
    sheet = get_sheet()
    # Convertir lista de diccionarios a lista de listas para gspread
    if not data_list: return
    
    headers = list(data_list[0].keys())
    rows = [headers]
    for item in data_list:
        row = [item.get(h, "") for h in headers]
        rows.append(row)
        
    # Limpiar hoja y escribir todo de nuevo (Método más seguro para evitar duplicados)
    sheet.clear()
    sheet.update(range="A1", values=rows)

# --- INICIALIZACIÓN ---
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

if "datos_base" not in st.session_state:
    st.session_state.datos_base = load_data()

datos = st.session_state.datos_base

# --- INTERFAZ ---
st.title("📊 Control Diario Nova")

if not datos:
    st.warning("⚠️ No hay datos. Revisa las credenciales.")
else:
    # MÉTRICAS
    total_usd = sum(limpiar_numero(f.get("USD", 0)) for f in datos if hoy_str in str(f.get("FECHA", "")))
    total_bs = sum(limpiar_numero(f.get("Bs", 0)) for f in datos if hoy_str in str(f.get("FECHA", "")))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("TOTAL USD HOY", formatear_numero(total_usd))
    col2.metric("TOTAL Bs HOY", formatear_numero(total_bs))
    col3.metric("COMISIÓN (15%)", formatear_numero(total_usd * 0.15))
    
    st.markdown("---")
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("📝 Agregar")
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
                    st.session_state.datos_base.append(nueva)
                    st.success("Agregado. Sincroniza para guardar.")
                    st.rerun()

    with col_der:
        st.subheader("🔍 Historial")
        mes = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
        anio = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
        patron = f"/{mes.zfill(2)}/{anio}"
        
        # Filtrar índices para no perder la referencia original
        indices_filtro = [i for i, f in enumerate(datos) if patron in str(f.get("FECHA", ""))]
        
        if indices_filtro:
            df_mostrar = [datos[i] for i in indices_filtro]
            
            # Editor
            df_editado = st.data_editor(
                df_mostrar,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_gspread",
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
                # 1. Obtener los datos editados
                # Si df_editado es lista, usamos tal cual. Si es DataFrame, usamos to_dict
                if isinstance(df_editado, pd.DataFrame):
                    datos_editados = df_editado.to_dict('records')
                else:
                    datos_editados = df_editado
                
                # 2. Reconstruir la lista completa
                # Quitamos los datos antiguos del filtro
                datos_sin_filtro = [f for i, f in enumerate(datos) if i not in indices_filtro]
                # Agregamos los nuevos
                datos_completos = datos_sin_filtro + datos_editados
                
                # 3. Guardar
                try:
                    save_data(datos_completos)
                    st.session_state.datos_base = load_data() # Recargar
                    st.success("✅ ¡Guardado en Google Sheets!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
        else:
            st.info("📭 No hay datos para este mes.")
