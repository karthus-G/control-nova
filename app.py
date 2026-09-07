import streamlit as st
import requests
import csv
import io
from datetime import datetime
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Diario Nova", layout="wide")
zona_co = pytz.timezone('America/Bogota')
hoy_co = datetime.now(zona_co)
hoy_str = hoy_co.strftime("%d/%m/%Y")

# URL de tu hoja (para lectura)
READ_URL = "https://docs.google.com/spreadsheets/d/16XJJ17pfE7n-O8jBhRRTb-niqh0LBYqwubcECsjwOdA/export?format=csv"

# URL DE TU APPS SCRIPT
WRITE_URL = "https://script.google.com/macros/s/AKfycbx0tSVe-9Q9rEjeylvuPRnK-rV_RTZhAhU_Ul75CpwmeTvf8442pM3O6-nhm4mu8wkawA/exec"

# --- FUNCIONES DE AYUDA ---

def limpiar_numero(valor):
    """Convierte cualquier formato a número real (float) para cálculos"""
    if not valor: return 0.0
    try:
        texto = str(valor).replace('$', '').replace(' ', '').strip()
        # Lógica para detectar formato
        if ',' in texto and '.' in texto:
            # Si la coma va después del punto, es formato anglo: 1,234.56
            if texto.rfind(',') > texto.rfind('.'):
                texto = texto.replace('.', '') # Quitar miles
            else:
                # Formato latino: 1.234,56 -> quitar punto, cambiar coma por punto
                texto = texto.replace('.', '').replace(',', '.')
        elif ',' in texto:
            # Solo coma: 123,45 -> formato latino
            texto = texto.replace(',', '.')
        # Si solo tiene punto, ya está en formato anglo
        return float(texto)
    except:
        return 0.0

def formatear_numero(valor):
    """Convierte un número a formato latino: $ 1.234,56"""
    if not valor: return "$ 0,00"
    # Formateamos con punto para miles y coma para decimales
    # Primero usamos el formato estándar y luego intercambiamos los separadores
    formato = f"${valor:,.2f}" # Ejemplo: $1,234.56
    # Intercambiamos: ',' por 'X', '.' por ',', 'X' por '.'
    return formato.replace(",", "X").replace(".", ",").replace("X", ".")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data():
    try:
        response = requests.get(READ_URL)
        reader = csv.reader(io.StringIO(response.text))
        data = []
        headers = []
        for i, row in enumerate(reader):
            if i == 0:
                headers = row
            else:
                if not any(row): continue
                item = {headers[j]: row[j] for j in range(len(headers)) if j < len(row)}
                data.append(item)
        return data
    except Exception as e:
        st.error(f"Error al leer: {e}")
        return []

# --- INICIALIZACIÓN ---
if "datos_base" not in st.session_state:
    st.session_state.datos_base = load_data()

datos = st.session_state.datos_base

# --- INTERFAZ PRINCIPAL ---
st.title("📊 Control Diario Nova")

if not datos:
    st.warning("⚠️ No hay datos cargados.")
else:
    # MÉTRICAS (Calculadas con números reales)
    total_usd = sum(limpiar_numero(f.get("USD", 0)) for f in datos if hoy_str in str(f.get("FECHA", "")))
    total_bs = sum(limpiar_numero(f.get("Bs", 0)) for f in datos if hoy_str in str(f.get("FECHA", "")))
    
    col1, col2, col3 = st.columns(3)
    # Aquí aplicamos el formato visual
    col1.metric("TOTAL USD HOY", formatear_numero(total_usd))
    col2.metric("TOTAL Bs HOY", formatear_numero(total_bs))
    col3.metric("COMISIÓN (15%)", formatear_numero(total_usd * 0.15))
    st.markdown("---")
    
    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("📝 Nueva Transacción")
        with st.form(key="transaccion_form", clear_on_submit=True):
            cuenta_input = st.text_input("CUENTA:").strip().upper()
            usd_input = st.number_input("USD:", min_value=0.0, step=0.01, format="%.2f")
            bs_input = st.number_input("Bs:", min_value=0.0, step=0.01, format="%.2f")
            
            if st.form_submit_button("✓ AGREGAR"):
                if cuenta_input:
                    nueva = {
                        "FECHA": hoy_str,
                        "CUENTA": cuenta_input,
                        "USD": formatear_numero(usd_input),
                        "Bs": formatear_numero(bs_input)
                    }
                    st.session_state.datos_base.append(nueva)
                    st.success("Agregado a la sesión (pendiente de sincronizar)")
                    st.rerun()
    
    with col_der:
        st.subheader("🔍 Historial y Edición")
        mes_filtro = st.text_input("Mes (MM):", hoy_co.strftime("%m"))
        anio_filtro = st.text_input("Año (YYYY):", hoy_co.strftime("%Y"))
        patron = f"/{mes_filtro.zfill(2)}/{anio_filtro}"
        
        indices_coincidentes = [i for i, f in enumerate(datos) if patron in str(f.get("FECHA", ""))]
        
        if not indices_coincidentes:
            st.info("📭 No hay datos para este periodo.")
        else:
            df_mostrar = [datos[i] for i in indices_coincidentes]
            
            # Editor interactivo
            df_editado = st.data_editor(
                df_mostrar,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_tabla",
                hide_index=True,
                column_config={
                    "FECHA": st.column_config.TextColumn("Fecha", width="medium"),
                    "CUENTA": st.column_config.TextColumn("Cuenta", width="medium"),
                    "USD": st.column_config.TextColumn(
                        "USD", 
                        width="medium",
                        help="Formato: $ 1.234,56"
                    ),
                    "Bs": st.column_config.TextColumn(
                        "Bs", 
                        width="medium",
                        help="Formato: $ 1.234,56"
                    ),
                }
            )
            
            st.markdown("**⚠️ Los cambios se aplicarán a tu Google Sheet al hacer clic en Sincronizar**")
            
            # Botones de acción
            col_sync, col_cancel = st.columns(2)
            
            with col_sync:
                if st.button("💾 SINCRONIZAR CON DRIVE", type="primary", use_container_width=True):
                    # 1. Preparar datos para enviar
                    # Convertimos el dataframe editado a lista de dicts
                    datos_editados = df_editado.to_dict('records')
                    
                    try:
                        # Enviar a Apps Script
                        payload = {
                            "action": "update",
                            "data": datos_editados
                        }
                        response = requests.post(WRITE_URL, json=payload, timeout=10)
                        
                        if response.status_code == 200 and response.json().get("status") == "success":
                            # Actualizar la sesión local con lo que acabamos de guardar
                            st.session_state.datos_base = load_data()
                            st.success("✅ ¡Guardado exitosamente en Google Sheets!")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar: " + response.json().get("message", "Desconocido"))
                            
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
                        st.info("Asegúrate de que la URL de Apps Script sea correcta y esté pública.")

            with col_cancel:
                if st.button("🔄 RESETEAR", use_container_width=True):
                    st.session_state.datos_base = load_data()
                    st.rerun()
