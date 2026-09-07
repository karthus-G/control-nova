import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# Usamos st.session_state para almacenar los datos en la memoria de la aplicación
if "df_base" not in st.session_state:
    url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
    if "/edit" in url_base:
        # CORRECCIÓN ENLACE: Extraemos el ID base correctamente usando split
        partes = url_base.split('/edit')
        url_csv = f"{partes[0]}/export?format=csv"
    else:
        url_csv = url_base
    try:
        # Carga inicial desde tu Google Sheet en la nube
        df_inicial = pd.read_csv(url_csv)
        # Aseguramos tus columnas exactas en orden
        for col in ["FECHA", "CUENTA", "USD", "Bs"]:
            if col not in df_inicial.columns:
                df_inicial[col] = None
        st.session_state.df_base = df_inicial
    except Exception as e:
        st.error("Error al conectar con la base de datos de Google Drive. Revisa el enlace en Secrets.")
        st.stop()

# --- PROCESAMIENTO DE DATOS EN TIEMPO REAL ---
df_trabajo = st.session_state.df_base.copy()

# Limpieza matemática interna instantánea para las tarjetas de totales
df_trabajo["USD_CALC"] = pd.to_numeric(df_trabajo["USD"].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0.0)
df_trabajo["Bs_CALC"] = pd.to_numeric(df_trabajo["Bs"].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0.0)

# Formateador visual idéntico al de tu tabla original
def fmt(v):
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- RESUMEN DE HOY ---
hoy_str = datetime.now().strftime("%d/%m/%Y")
df_hoy = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(hoy_str, na=False)]

total_usd_hoy = df_hoy["USD_CALC"].sum()
total_bs_hoy = df_hoy["Bs_CALC"].sum()
comision_hoy = total_usd_hoy * 0.15

# Encabezado principal y tarjetas con actualización inmediata
st.title("📊 Control Diario Nova")
col1, col2, col3 = st.columns(3)
col1.metric("TOTAL USD HOY", fmt(total_usd_hoy))
col2.metric("TOTAL Bs HOY", fmt(total_bs_hoy))
col3.metric("COMISIÓN HOY (15%)", fmt(comision_hoy))

st.markdown("---")

# --- DISEÑO DE PANTALLA ---
# CORRECCIÓN EN COLUMNS: Pasamos explícitamente el número 2 para dividir en dos columnas
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📝 Nueva Transacción")
    with st.form(key="transaccion_form", clear_on_submit=True):
        cuenta_input = st.text_input("CUENTA:").strip().upper()
        usd_input = st.number_input("USD:", min_value=0.0, step=0.01, format="%.2f")
        bs_input = st.number_input("Bs:", min_value=0.0, step=0.01, format="%.2f")
        
        btn_guardar = st.form_submit_button("✓ AGREGAR AL HISTORIAL")
        
        if btn_guardar:
            if not cuenta_input:
                st.error("El campo CUENTA es obligatorio.")
            else:
                # Formateamos valores como texto idéntico a tu Google Sheet original
                usd_formateado = f"$ {usd_input:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if usd_input > 0 else None
                bs_formateado = f"$ {bs_input:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if bs_input > 0 else None
                
                # Crear la nueva fila
                nueva_fila = pd.DataFrame([{
                    "FECHA": hoy_str,
                    "CUENTA": cuenta_input,
                    "USD": usd_formateado,
                    "Bs": bs_formateado
                }])
                
                # Insertar al estado de la aplicación e inyectar cambios
                st.session_state.df_base = pd.concat([st.session_state.df_base, nueva_fila], ignore_index=True)
                st.success("¡Transacción añadida exitosamente abajo!")
                st.rerun()

with col_der:
    st.subheader("🔍 Historial y Filtro Mensual Interactivo")
    
    col_m, col_a = st.columns(2)
    mes_filtro = col_m.text_input("Mes (MM):", datetime.now().strftime("%m"))
    anio_filtro = col_a.text_input("Año (YYYY):", datetime.now().strftime("%Y"))
    
    # Filtrar el historial dinámicamente según el mes y año solicitado
    patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
    df_filtrado = df_trabajo[df_trabajo["FECHA"].astype(str).str.contains(patron, na=False)]
    
    st.info("💡 **Cómo eliminar registros:** Selecciona la casilla de la fila que deseas borrar en el cuadro de abajo y presiona el botón **Eliminar** de tu teclado (o el icono de papelera). Los totales de arriba cambiarán al instante.")
    
    # El editor de datos interactivo
    datos_editados = st.data_editor(
        df_filtrado[["FECHA", "CUENTA", "USD", "Bs"]],
        use_container_width=True,
        num_rows="dynamic",
        key="tabla_interactiva"
    )
    
    # Sincronizar cualquier cambio o eliminación realizada en la tabla interactiva hacia la memoria principal
    if st.checkbox("💾 Confirmar y aplicar cambios del historial"):
        lineas_actuales = st.session_state.df_base.copy()
        df_resto = lineas_actuales[~lineas_actuales["FECHA"].astype(str).str.contains(patron, na=False)]
        st.session_state.df_base = pd.concat([df_resto, datos_editados], ignore_index=True)
        st.success("¡Historial sincronizado!")
        st.rerun()
