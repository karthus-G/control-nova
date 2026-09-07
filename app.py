import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# --- 1. CONFIGURACIÓN ---
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

spreadsheet_url = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA"
url_csv = spreadsheet_url + "/export?format=csv"

# --- 2. FUNCIÓN DE CARGA INTELIGENTE ---
@st.cache_data(ttl=60)
def load_data():
    """
    Intenta cargar el CSV de 3 formas diferentes para asegurar que funcione
    independientemente del formato de tu hoja.
    """
    try:
        # Opción 1: Formato Latino (coma decimal, punto miles)
        try:
            df = pd.read_csv(
                url_csv, 
                on_bad_lines='skip', 
                decimal=',',   # Coma como decimal
                thousands='.', # Punto como miles
                sep=';'        # Separador de columnas (ajustar si es necesario)
            )
            return df
        except:
            pass
        
        # Opción 2: Formato Anglosajón (punto decimal, coma miles)
        try:
            df = pd.read_csv(
                url_csv, 
                on_bad_lines='skip', 
                decimal='.',   # Punto como decimal
                thousands=',', # Coma como miles
                sep=','        # Separador de columnas
            )
            return df
        except:
            pass
            
        # Opción 3: Lectura básica (si el CSV ya viene bien hecho)
        try:
            df = pd.read_csv(url_csv, on_bad_lines='skip')
            return df
        except:
            pass
            
        st.error("⚠️ No se pudo leer la hoja de cálculo. Verifica que el enlace sea público y tenga datos.")
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error crítico al cargar: {e}")
        return pd.DataFrame()

# --- 3. INICIALIZACIÓN Y PROCESAMIENTO ---
if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# Verificar si la carga fue exitosa
if df_trabajo.empty:
    st.warning("⚠️ No se cargaron datos. Asegúrate de que la hoja tenga los encabezados: FECHA, CUENTA, USD, Bs")
else:
    # Normalizar columnas
    for col in ["FECHA", "CUENTA", "USD", "Bs"]:
        if col not in df_trabajo.columns:
            df_trabajo[col] = None

    # Limpiar columnas numéricas
    def clean_money(v):
        if pd.isna(v): return 0.0
        return pd.to_numeric(str(v).replace('$', '').replace(',', '').replace('.', ''), errors='coerce') or 0.0

    df_trabajo["USD_CALC"] = df_trabajo["USD"].apply(clean_money)
    df_trabajo["Bs_CALC"] = df_trabajo["Bs"].apply(clean_money)

# --- 4. INTERFAZ ---
st.title("📊 Control Diario Nova")

if not df_trabajo.empty:
    # MÉTRICAS
    df_hoy = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)]
    col1, col2, col3 = st.columns(3)
    col1.metric("TOTAL USD HOY", f"$ {df_hoy['USD_CALC'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("TOTAL Bs HOY", f"$ {df_hoy['Bs_CALC'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("COMISIÓN (15%)", f"$ {df_hoy['USD_CALC'].sum() * 0.15:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    st.markdown("---")
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("📝 Nueva Transacción")
        with st.form(key="transaccion_form", clear_on_submit=True):
            cuenta_input = st.text_input("CUENTA:").strip().upper()
            usd_input = st.number_input("USD:", min_value=0.0, step=0.01, format="%.2f")
            bs_input = st.number_input("Bs:", min_value=0.0, step=0.01, format="%.2f")
            
            if st.form_submit_button("✓ GUARDAR (SOLO SESIÓN)"):
                if cuenta_input:
                    nueva_fila = pd.DataFrame([{
                        "FECHA": hoy_str,
                        "CUENTA": cuenta_input,
                        "USD": usd_input,
                        "Bs": bs_input
                    }])
                    st.session_state.df_base = pd.concat([st.session_state.df_base, nueva_fila], ignore_index=True)
                    st.success("¡Añadido a la sesión actual!")
                    st.rerun()
                else:
                    st.error("El campo CUENTA es obligatorio.")
    
    with col_der:
        st.subheader("🔍 Historial del Mes")
        mes_filtro = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
        anio_filtro = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
        
        patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
        df_filtrado = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(patron, na=False)]
        
        if df_filtrado.empty:
            st.info("📭 No hay datos para este periodo.")
        else:
            st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
else:
    st.markdown("### 📭 La hoja de cálculo está vacía o no se pudo cargar.")
    st.info("Verifica que tu Google Sheet tenga los encabezados: **FECHA, CUENTA, USD, Bs**")
