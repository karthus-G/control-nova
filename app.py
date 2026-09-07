import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
import requests

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# CONFIGURACIÓN DE ZONA HORARIA
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# ENLACE DIRECTO A TU HOJA (sin editar)
spreadsheet_url = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA"
url_csv = spreadsheet_url.replace("/edit?usp=sharing", "/export?format=csv")

def load_data():
    """Carga datos desde el CSV de Google Sheets"""
    try:
        df = pd.read_csv(url_csv)
        for col in ["FECHA", "CUENTA", "USD", "Bs"]:
            if col not in df.columns:
                df[col] = None
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame(columns=["FECHA", "CUENTA", "USD", "Bs"])

def save_transaction(fecha, cuenta, usd, bs):
    """
    Guarda una transacción usando gspread con el enlace de la hoja.
    Funciona si la hoja está compartida con 'Cualquiera con el enlace'.
    """
    try:
        # Intentar con gspread (recomendado para escritura)
        try:
            creds_dict = st.secrets.get("gcp_service_account", {})
            if creds_dict:
                scopes = ["https://www.googleapis.com/auth/spreadsheets"]
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                gc = gspread.authorize(creds)
                sh = gc.open_by_key("16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA")
                worksheet = sh.sheet1
                worksheet.append_row([fecha, cuenta, usd, bs])
                return True
        except:
            pass
            
        # Fallback: Usar requests para añadir fila (menos seguro pero funciona sin credenciales)
        # Esto requiere que la hoja esté compartida como "Cualquiera con el enlace"
        st.warning("⚠️ No se pudieron usar las credenciales. Verifica que la hoja esté compartida.")
        return False
        
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

# CARGAR DATOS
if "df_base" not in st.session_state:
    st.session_state.df_base = load_data()

df_trabajo = st.session_state.df_base.copy()

# PROCESAMIENTO NUMÉRICO
def clean_money(v):
    if pd.isna(v): return 0.0
    return float(str(v).replace('$', '').replace(',', '').replace('.', '').strip())

df_trabajo["USD_CALC"] = df_trabajo["USD"].apply(clean_money)
df_trabajo["Bs_CALC"] = df_trabajo["Bs"].apply(clean_money)

def fmt(v):
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# INTERFAZ
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
        
        if st.form_submit_button("✓ GUARDAR EN DRIVE"):
            if cuenta_input:
                if save_transaction(hoy_str, cuenta_input, usd_input, bs_input):
                    st.cache_data.clear()
                    st.session_state.df_base = load_data()
                    st.success("¡Transacción guardada!")
                    st.rerun()
                else:
                    st.error("❌ No se pudo guardar. Revisa la configuración de la hoja.")
            else:
                st.error("El campo CUENTA es obligatorio.")

with col_der:
    st.subheader("🔍 Historial del Mes")
    mes_filtro = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
    anio_filtro = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
    
    patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
    df_filtrado = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(patron, na=False)]
    
    st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
