import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# Conexión nativa de Streamlit para Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Lee los datos directamente usando la configuración de Secrets
    df = conn.read(ttl="0m")
except Exception as e:
    st.error("Error al conectar con la base de datos de Google Drive. Por favor, verifica el enlace en Secrets.")
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
                nueva_fila = pd.DataFrame([{
                    "FECHA": datetime.now().strftime("%d/%m/%Y"),
                    "CUENTA": cuenta,
                    "USD": str(usd_val),
                    "Bs": str(bs_val)
                }])
                df_to_save = pd.concat([df, nueva_fila], ignore_index=True).drop(columns=["USD_CALC", "Bs_CALC"], errors="ignore")
                conn.update(data=df_to_save)
                st.success("¡Guardado exitosamente en Google Drive!")
                st.rerun()

with col_der:
    st.subheader("🔍 Historial y Filtro Mensual")
    
    col_m, col_a = st.columns(2)
    mes_filtro = col_m.text_input("Mes (MM):", datetime.now().strftime("%m"))
    anio_filtro = col_a.text_input("Año (YYYY):", datetime.now().strftime("%Y"))
    
    patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
    df_filtrado = df[df["FECHA"].astype(str).str.contains(patron, na=False)]
    
    st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
