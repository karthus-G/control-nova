import streamlit as st
import pandas as pd
from datetime import datetime
import gspread

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# Conexión directa y ultra-estable usando la URL secreta
@st.cache_data(ttl="0m")
def cargar_datos():
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    gc = gspread.public_api()
    sh = gc.open_by_url(url)
    worksheet = sh.get_worksheet(0)
    data = worksheet.get_all_records()
    return pd.DataFrame(data), worksheet

try:
    df, worksheet = cargar_datos()
except Exception as e:
    st.error("Error al conectar con Google Sheets. Verifica que el archivo sea público para cualquiera con el enlace en modo Editor.")
    st.stop()

# Aseguramos que existan las columnas correspondientes
for col in ["FECHA", "CUENTA", "USD", "Bs"]:
    if col not in df.columns:
        df[col] = None

# Convertir tipos para operar matemáticamente de forma segura
df["USD_CALC"] = pd.to_numeric(df["USD"].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0.0)
df["Bs_CALC"] = pd.to_numeric(df["Bs"].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0.0)

# --- RESUMEN DE HOY ---
hoy_str1 = datetime.now().strftime("%d/%m/%Y")
hoy_str2 = datetime.now().strftime("%Y-%m-%d")

df_hoy = df[df["FECHA"].astype(str).str.contains(f"{hoy_str1}|{hoy_str2}", na=False)]

total_usd_hoy = df_hoy["USD_CALC"].sum()
total_bs_hoy = df_hoy["Bs_CALC"].sum()
comision_hoy = total_usd_hoy * 0.15

st.title("📊 Control Diario Nova")
col1, col2, col3 = st.columns(3)
col1.metric("TOTAL USD HOY", f"$ {total_usd_hoy:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("TOTAL Bs HOY", f"$ {total_bs_hoy:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("COMISIÓN HOY (15%)", f"$ {comision_hoy:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.markdown("---")

col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📝 Nueva Transacción")
    with st.form(key="transaccion_form", clear_on_submit=True):
        cuenta = st.text_input("CUENTA:").strip().upper()
        usd_val = st.number_input("USD:", min_value=0.0, step=0.01, format="%.2f")
        bs_val = st.number_input("Bs:", min_value=0.0, step=0.01, format="%.2f")
        
        btn_guardar = st.form_submit_button("✓ GUARDAR")
        
        if btn_guardar:
            if not cuenta:
                st.error("La CUENTA es requerida.")
            else:
                # Añadir fila directamente a la hoja de Google Sheets
                nueva_fila = [datetime.now().strftime("%d/%m/%Y"), cuenta, str(usd_val), str(bs_val)]
                worksheet.append_row(nueva_fila)
                st.success("¡Guardado exitosamente en Google Drive!")
                st.cache_data.clear()
                st.rerun()

with col_der:
    st.subheader("🔍 Historial y Filtro Mensual")
    
    col_m, col_a = st.columns(2)
    mes_filtro = col_m.text_input("Mes (MM):", datetime.now().strftime("%m"))
    anio_filtro = col_a.text_input("Año (YYYY):", datetime.now().strftime("%Y"))
    
    patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
    df_filtrado = df[df["FECHA"].astype(str).str.contains(patron, na=False)]
    
    st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
