import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# Conexión nativa y segura con tu Google Sheet
conn = st.connection("gsheets", type=GSheetsConnection)

# Función para formatear dinero de manera amigable
def fmt(v):
    try:
        val = float(v)
        return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "$ 0,00"

# --- LEER DATOS DESDE LA NUBE ---
# ttl="0m" obliga a que lea datos frescos de Google Drive cada vez que recargas
df = conn.read(ttl="0m")

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

# Filtrar registros que coincidan con el día de hoy
df_hoy = df[df["FECHA"].astype(str).str.contains(f"{hoy_str1}|{hoy_str2}", na=False)]

total_usd_hoy = df_hoy["USD_CALC"].sum()
total_bs_hoy = df_hoy["Bs_CALC"].sum()
comision_hoy = total_usd_hoy * 0.15

# Mostrar los totales en tarjetas llamativas en la zona superior
st.title("📊 Control Diario Nova")
col1, col2, col3 = st.columns(3)
col1.metric("TOTAL USD HOY", fmt(total_usd_hoy))
col2.metric("TOTAL Bs HOY", fmt(total_bs_hoy))
col3.metric("COMISIÓN HOY (15%)", fmt(comision_hoy))

st.markdown("---")

# --- DISEÑO EN DOS COLUMNAS (Formulario de un lado, Historial del otro) ---
col_izq, col_der = st.columns([1, 2])

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
                # Armamos la fila tal como le gusta a tu reporte
                nueva_fila = pd.DataFrame([{
                    "FECHA": datetime.now().strftime("%d/%m/%Y"),
                    "CUENTA": cuenta,
                    "USD": usd_val,
                    "Bs": bs_val
                }])
                
                # Unimos con lo existente eliminando columnas auxiliares de cálculo
                df_to_save = pd.concat([df, nueva_fila], ignore_index=True).drop(columns=["USD_CALC", "Bs_CALC"], errors="ignore")
                
                # Impactamos la base de datos de Google Drive inmediatamente
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
    
    # Mostrar la tabla interactiva
    st.dataframe(df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]], use_container_width=True)
    
    # Calcular totales del mes consultado
    if not df_filtrado.empty:
        m_usd = df_filtrado["USD_CALC"].sum()
        m_bs = df_filtrado["Bs_CALC"].sum()
        
        st.write(f"**Totales del Mes seleccionado:** USD: `{fmt(m_usd)}` | Bs: `{fmt(m_bs)}` | 15%: `{fmt(m_usd*0.15)}`")
        
        # Eliminar fila seleccionada
        registro_a_eliminar = st.selectbox("Selecciona fila a eliminar (Por Cuenta):", df_filtrado["CUENTA"].unique(), index=None, placeholder="Elija una cuenta...")
        if st.button("❌ ELIMINAR SELECCIONADO", type="primary") and registro_a_eliminar:
            df_to_save = df[df["CUENTA"] != registro_a_eliminar].drop(columns=["USD_CALC", "Bs_CALC"], errors="ignore")
            conn.update(data=df_to_save)
            st.warning(f"Cuenta '{registro_a_eliminar}' eliminada.")
            st.rerun()
