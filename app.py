import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# 1. CONFIGURACIÓN Y CONEXIÓN A GOOGLE SHEETS
def get_gsheet():
    # Define scopes and credentials from secrets
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(st.secrets["spreadsheet_id"])

# 2. FUNCIONES DE LECTURA/ESCRITURA
@st.cache_data(ttl=60) # Cachea la lectura por 60s para no saturar la API
def load_data():
    try:
        sh = get_gsheet()
        worksheet = sh.sheet1 # Ajusta el nombre de la hoja si es necesario
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame(columns=["FECHA", "CUENTA", "USD", "Bs"])

def save_new_transaction(fecha, cuenta, usd, bs):
    sh = get_gsheet()
    worksheet = sh.sheet1
    worksheet.append_row([fecha, cuenta, usd, bs])

# 3. LÓGICA DE LA APP
st.set_page_config(page_title="Control Diario Nova", layout="wide")

zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# Cargar datos iniciales
if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# Procesamiento numérico
def clean_money(v):
    if pd.isna(v): return 0.0
    return float(str(v).replace('$', '').replace(',', '').replace('.', '')) if str(v).strip() != '' else 0.0

df_trabajo["USD_CALC"] = df_trabajo["USD"].apply(clean_money)
df_trabajo["Bs_CALC"] = df_trabajo["Bs"].apply(clean_money)

def fmt(v):
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFAZ ---
st.title("📊 Control Diario Nova")

# MÉTRICAS
df_hoy = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)]
total_usd = df_hoy["USD_CALC"].sum()
total_bs = df_hoy["Bs_CALC"].sum()
comision = total_usd * 0.15

col1, col2, col3 = st.columns(3)
col1.metric("TOTAL USD HOY", fmt(total_usd))
col2.metric("TOTAL Bs HOY", fmt(total_bs))
col3.metric("COMISIÓN (15%)", fmt(comision))

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
                # Guardar en Drive
                save_new_transaction(hoy_str, cuenta_input, usd_input, bs_input)
                st.session_state.df_base = load_data() # Recargar para ver el cambio
                st.success("¡Transacción sincronizada con Google Drive!")
                st.rerun()
            else:
                st.error("El campo CUENTA es obligatorio.")

with col_der:
    st.subheader("🔍 Historial del Mes")
    # Aquí mantienes tu lógica de filtro y data_editor, pero recuerda que 
    # para que el data_editor guarde, necesitas una función similar a save_new_transaction 
    # que reemplace los valores en la hoja.
    st.info("💡 Para que los cambios en la tabla se guarden, necesitas implementar una función de actualización masiva en gspread.")
    st.dataframe(df_trabajo.tail(10)) # Muestra las últimas 10 para no saturar
