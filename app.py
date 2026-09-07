import streamlit as st
import requests
import json
from datetime import datetime
import pytz

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# --- CONFIGURACIÓN ---
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# PEGA AQUÍ LA URL QUE TE DIO GOOGLE APPS SCRIPT EN EL PASO 1
APPS_SCRIPT_URL = "PEGA_TU_URL_DE_APPS_SCRIPT_AQUI"

# --- FUNCIÓN DE LIMPIEZA MANUAL (SIN PANDAS) ---
def limpiar_numero(valor):
    """Convierte '$ 1.234,56' a 1234.56 manualmente"""
    if not valor: return 0.0
    try:
        # 1. Quitar símbolos de moneda y espacios
        texto = str(valor).replace('$', '').replace(' ', '').strip()
        # 2. Si tiene coma decimal, la convertimos a punto
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        return float(texto)
    except:
        return 0.0

# --- CARGA DE DATOS (SIN PANDAS) ---
@st.cache_data(ttl=60)
def load_data_raw():
    try:
        response = requests.get(APPS_SCRIPT_URL)
        data = response.json()
        if not data:
            return []
        
        # La primera fila suele ser el encabezado
        headers = data[0]
        rows = data[1:]
        
        # Convertir a lista de diccionarios para mantener el formato original
        df = []
        for row in rows:
            # Asegurar que la fila tenga el largo correcto
            if len(row) >= len(headers):
                item = {headers[i]: row[i] for i in range(len(headers))}
                df.append(item)
        return df
    except Exception as e:
        st.error(f"Error al conectar: {e}")
        return []

# --- INICIALIZACIÓN ---
if "datos_base" not in st.session_state:
    st.session_state.datos_base = load_data_raw()

datos = st.session_state.datos_base

# --- INTERFAZ ---
st.title("📊 Control Diario Nova")

if not datos:
    st.warning("⚠️ No se han cargado datos. Verifica la URL de Apps Script.")
else:
    # CÁLCULO DE MÉTRICAS (Usando la limpieza manual)
    total_usd = 0
    total_bs = 0
    for fila in datos:
        fecha_fila = str(fila.get("FECHA", ""))
        if hoy_str in fecha_fila:
            total_usd += limpiar_numero(fila.get("USD", 0))
            total_bs += limpiar_numero(fila.get("Bs", 0))

    col1, col2, col3 = st.columns(3)
    # Mostramos los valores tal cual los calculamos
    col1.metric("TOTAL USD HOY", f"$ {total_usd:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("TOTAL Bs HOY", f"$ {total_bs:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("COMISIÓN (15%)", f"$ {total_usd * 0.15:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

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
                    nueva = {
                        "FECHA": hoy_str,
                        "CUENTA": cuenta_input,
                        "USD": f"$ {usd_input:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        "Bs": f"$ {bs_input:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    }
                    st.session_state.datos_base.append(nueva)
                    st.success("¡Añadido a la sesión actual!")
                    st.rerun()
                else:
                    st.error("El campo CUENTA es obligatorio.")
    
    with col_der:
        st.subheader("🔍 Historial del Mes")
        mes_filtro = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
        anio_filtro = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
        patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
        
        # Filtrar manualmente
        datos_filtrados = [f for f in datos if patron in str(f.get("FECHA", ""))]
        
        if datos_filtrados:
            # Mostrar tabla con los datos EXACTOS de la hoja
            st.dataframe(datos_filtrados, use_container_width=True)
        else:
            st.info("📭 No hay datos para este periodo.")
