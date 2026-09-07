import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# 1. CONFIGURACIÓN DE FECHA
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# 2. CONEXIÓN SEGURA (MANEJO DE DECIMALES CON COMA)
@st.cache_data(ttl=60)
def load_data():
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA"
    url_csv = spreadsheet_url + "/export?format=csv"
    try:
        # IMPORTANTE: 
        # decimal="," -> Le dice que la coma es el punto decimal
        # thousands="." -> Le dice que el punto es para miles
        # sep=";" -> Si tu CSV usa punto y coma como separador de columnas. 
        # Si usa coma, cambia sep=";" por sep=","
        df = pd.read_csv(
            url_csv, 
            on_bad_lines='skip', 
            decimal=',', 
            thousands='.',
            sep=';'  # Cambia esto a ',' si tus columnas están separadas por comas
        )
        
        # Si al usar sep=';' las columnas salen mal, usa esta alternativa:
        # df = pd.read_csv(url_csv, on_bad_lines='skip', decimal=',', thousands='.')
        
        for col in ["FECHA", "CUENTA", "USD", "Bs"]:
            if col not in df.columns:
                df[col] = None
        return df
    except Exception as e:
        st.error(f"Error al cargar: {e}")
        return pd.DataFrame()

# 3. INICIALIZACIÓN
if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# 4. PROCESAMIENTO (YA NO NECESITA LIMPIEZA MANUAL)
# Como usamos decimal=',' en la carga, Pandas ya convirtió los textos en números reales.
# Solo nos aseguramos de que no haya valores vacíos.
df_trabajo["USD_CALC"] = pd.to_numeric(df_trabajo["USD"], errors='coerce').fillna(0.0)
df_trabajo["Bs_CALC"] = pd.to_numeric(df_trabajo["Bs"], errors='coerce').fillna(0.0)

def fmt(v):
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# 5. INTERFAZ
st.title("📊 Control Diario Nova")

# MÉTRICAS
df_hoy = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)]
col1, col2, col3 = st.columns(3)
col1.metric("TOTAL USD HOY", fmt(df_hoy["USD_CALC"].sum()))
col2.metric("TOTAL Bs HOY", fmt(df_hoy["Bs_CALC"].sum()))
col3.metric("COMISIÓN (15%)", fmt(df_hoy["USD_CALC"].sum() * 0.15))

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
    
    st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
