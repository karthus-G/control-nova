import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN Y CONEXIÓN ---
def get_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Cargar credenciales desde secrets.toml
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    # Abrir la hoja por su ID
    return gc.open_by_key("16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA")

# --- FUNCIONES DE DATOS ---
@st.cache_data(ttl=60) # Cachea por 60 segundos para ahorrar llamadas a la API
def load_data():
    try:
        sh = get_gsheet()
        worksheet = sh.sheet1 # Asumiendo que la hoja principal se llama "Sheet1"
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Asegurar que existan las columnas necesarias
        for col in ["FECHA", "CUENTA", "USD", "Bs"]:
            if col not in df.columns:
                df[col] = None
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

def save_transaction(fecha, cuenta, usd, bs):
    """Guarda una nueva fila en Google Sheets"""
    sh = get_gsheet()
    worksheet = sh.sheet1
    worksheet.append_row([fecha, cuenta, usd, bs])

# --- INICIALIZACIÓN ---
st.set_page_config(page_title="Control Diario Nova", layout="wide")

zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# Cargar datos
if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# --- PROCESAMIENTO ---
def clean_money(v):
    if pd.isna(v): return 0.0
    # Limpia símbolos de moneda y puntos de miles
    clean = str(v).replace('$', '').replace(',', '').strip()
    try:
        return float(clean)
    except:
        return 0.0

df_trabajo["USD_CALC"] = df_trabajo["USD"].apply(clean_money)
df_trabajo["Bs_CALC"] = df_trabajo["Bs"].apply(clean_money)

def fmt(v):
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFAZ ---
st.title("📊 Control Diario Nova")

col1, col2, col3 = st.columns(3)
df_hoy = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)]
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
        
        if st.form_submit_button("✓ GUARDAR EN DRIVE"):
            if cuenta_input:
                # Guardar y recargar
                save_transaction(hoy_str, cuenta_input, usd_input, bs_input)
                st.cache_data.clear() # Limpiar caché para ver el cambio inmediato
                st.session_state.df_base = load_data()
                st.success("¡Transacción sincronizada!")
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
