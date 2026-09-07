import streamlit as st
import requests
import csv
import io
from datetime import datetime
import pytz

st.set_page_config(page_title="Control Diario Nova", layout="wide")

# --- CONFIGURACIÓN ---
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# URL DIRECTA DE TU HOJA (Exportación CSV)
# Nota: Esto solo funciona si la hoja está compartida como "Cualquiera con el enlace"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA/export?format=csv"

# --- FUNCIÓN DE LIMPIEZA MANUAL (EL SECRETO) ---
def limpiar_numero(valor):
    """
    Convierte cualquier formato a número real.
    Ejemplos: "$ 1.234,56" -> 1234.56 | "1,234.56" -> 1234.56
    """
    if not valor: return 0.0
    try:
        # 1. Quitar símbolos innecesarios
        texto = str(valor).replace('$', '').replace(' ', '').strip()
        
        # 2. Detectar formato
        if ',' in texto and '.' in texto:
            # Si hay ambos, el último es el decimal
            if texto.rfind(',') > texto.rfind('.'):
                # Formato Latino: 1.234,56
                texto = texto.replace('.', '').replace(',', '.')
            else:
                # Formato Anglo: 1,234.56
                texto = texto.replace(',', '')
        elif ',' in texto:
            # Solo coma: asumimos decimal latino (123,45)
            texto = texto.replace(',', '.')
        elif '.' in texto:
            # Solo punto: asumimos decimal anglo (123.45)
            pass
            
        return float(texto)
    except:
        return 0.0

# --- CARGA DE DATOS SIN PANDAS ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # Descargamos el contenido como texto puro
        response = requests.get(SPREADSHEET_URL)
        response.raise_for_status()
        
        # Usamos el lector CSV nativo de Python (mucho más tolerante)
        reader = csv.reader(io.StringIO(response.text))
        
        # Convertir a lista de diccionarios
        data = []
        headers = []
        for i, row in enumerate(reader):
            if i == 0:
                headers = row
            else:
                # Verificar que la fila no esté vacía
                if not any(row):
                    continue
                # Crear diccionario solo con las columnas que existen
                item = {}
                for j, header in enumerate(headers):
                    if j < len(row):
                        item[header] = row[j]
                    else:
                        item[header] = ""
                data.append(item)
        return data
    except Exception as e:
        st.error(f"Error al descargar: {e}")
        return []

# --- INICIALIZACIÓN ---
if "datos_base" not in st.session_state:
    st.session_state.datos_base = load_data()

datos = st.session_state.datos_base

# --- INTERFAZ ---
st.title("📊 Control Diario Nova")

if not datos:
    st.warning("⚠️ No hay datos. Verifica que la hoja esté compartida con 'Cualquiera con el enlace'.")
else:
    # MÉTRICAS (Usando limpieza manual)
    total_usd = 0
    total_bs = 0
    for fila in datos:
        if hoy_str in str(fila.get("FECHA", "")):
            total_usd += limpiar_numero(fila.get("USD", 0))
            total_bs += limpiar_numero(fila.get("Bs", 0))

    col1, col2, col3 = st.columns(3)
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
                    # Guardamos el formato visual que tú quieras
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
        
        # Filtrado manual
        datos_filtrados = [f for f in datos if patron in str(f.get("FECHA", ""))]
        
        if datos_filtrados:
            # st.dataframe acepta listas de diccionarios perfectamente
            st.dataframe(datos_filtrados, use_container_width=True)
        else:
            st.info("📭 No hay datos para este periodo.")
