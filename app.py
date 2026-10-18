import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os

# Configuración inicial de la página
st.set_page_config(
    page_title="Value Radar - Auditor de Apuestas",
    page_icon="⚽",
    layout="wide"
)

# ---------------------------------------------------------
# CONTROL DE ACCESO (Persistente en sesión)
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

app_password = st.secrets.get("APP_PASSWORD", "")
if app_password and not st.session_state.authenticated:
    st.title("🔒 Acceso Restringido")
    pwd_input = st.text_input("Ingrese la contraseña de acceso:", type="password")
    if st.button("Ingresar"):
        if pwd_input == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

# Inicializar estados en sesión
if "images_list" not in st.session_state:
    st.session_state.images_list = []
if "scan_result" not in st.session_state:
    st.session_state.scan_result = None

# Encabezado principal
st.title("⚽ Value Radar: Escáner y Auditor de Apuestas")
st.markdown("Sistema de dos fases: **1)** Radar de valor para filtrar las mejores oportunidades de la cartelera. **2)** Auditoría quirúrgica (+EV) con búsqueda web y SRI.")

# ---------------------------------------------------------
# BARRA LATERAL (Configuración)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración del Agente")
    
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if api_key:
        st.success("✔ Clave API cargada automáticamente")
    else:
        st.error("❌ No se encontró GEMINI_API_KEY en los Secrets.")

    st.markdown("---")
    
    retencion = st.number_input(
        "Retención de impuesto SRI (%)",
        min_value=0.0,
        max_value=100.0,
        value=15.0,
        step=1.0,
        help="Porcentaje de retención sobre la ganancia neta"
    )
    
    prob_min = st.number_input(
        "Probabilidad Mínima Exigida (%)",
        min_value=0.0,
        max_value=100.0,
        value=85.0,
        step=1.0,
        help="Umbral mínimo para considerar que la apuesta es rentable"
    )

# ---------------------------------------------------------
# FASE 1: RADAR DE VALOR (FILTRADO DE OPORTUNIDADES)
# ---------------------------------------------------------
st.subheader("Fase 1: Radar de Oportunidades (Betano)")

uploaded_files = st.file_uploader(
    "Sube tu captura con la cartelera de partidos:",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        img = Image.open(file)
        if img not in st.session_state.images_list:
            st.session_state.images_list.append(img)

# Mostrar previsualización de imágenes cargadas en Fase 1
if st.session_state.images_list:
    cols = st.columns(min(len(st.session_state.images_list), 4))
    indices_to_remove = []
    for idx, img in enumerate(st.session_state.images_list):
        with cols[idx % 4]:
            st.image(img, use_container_width=True)
            if st.button(f"❌ Quitar #{idx+1}", key=f"del_{idx}"):
                indices_to_remove.append(idx)
    
    if indices_to_remove:
        for index in sorted(indices_to_remove, reverse=True):
            st.session_state.images_list.pop(index)
        st.rerun()

    if st.button("🎯 Escanear y Filtrar Mejores Oportunidades", type="primary"):
        if not api_key:
            st.error("❌ Falta la clave API.")
        else:
            with st.spinner("Analizando la cartelera y filtrando partidos con mayor potencial..."):
                try:
                    client = genai.Client(api_key=api_key)
                    
                    # Prompt actualizado para que actúe estrictamente como un filtro de valor
                    scan_prompt = """
                    Eres un experto analista de mercados de apuestas y cazador de valor (+EV). 
                    Analiza detalladamente la(s) imagen(es) de la cartelera de partidos adjuntas.
                    
                    INSTRUCCIÓN CRÍTICA: NO listes todos los partidos de forma genérica. FILTRA y SELECCIONA ÚNICAMENTE aquellos encuentros que presenten cuotas más atractivas, desproporcionadas o con mayor potencial de valor para apostar. Descarta los partidos aburridos o sin atractivo.
                    
                    Presenta una lista limpia y directa con las mejores oportunidades detectadas, indicando:
                    1. Nombre del Partido (Local vs Visitante).
                    2. Cuotas clave observadas.
                    3. Por qué destaca como una oportunidad interesante a investigar.
                    """
                    
                    contents = [scan_prompt] + st.session_state.images_list
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=contents
                    )
                    st.session_state.scan_result = response.text
                except Exception as e:
                    st.error(f"Ocurrió un error en el escaneo: {str(e)}")

# Mostrar resultados del escaneo si ya se procesó la Fase 1
if st.session_state.scan_result:
    st.markdown("---")
    st.subheader("🎯 Oportunidades Detectadas por el Radar")
    st.markdown(st.session_state.scan_result)

    if st.button("🗑️ Limpiar Radar y Cargar Otra Captura", type="secondary"):
        st.session_state.images_list = []
        st.session_state.scan_result = None
        st.rerun()

    # ---------------------------------------------------------
    # FASE 2: AUDITORÍA QUIRÚRGICA (+EV)
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("Fase 2: Auditoría Quirúrgica de la Oportunidad Elegida")
    st.markdown("Copia el nombre del partido que más te haya llamado la atención del radar anterior para investigarlo a fondo.")

    selected_match = st.text_input("Partido seleccionado para auditar (ej. Equipo A vs Equipo B):")
    monto_apuesta = st.number_input(
        "Monto a apostar ($ USD):",
        min_value=1.0,
        value=10.0,
        step=5.0,
        help="Monto simulado para calcular ganancias y gestión de riesgo (Stake)"
    )

    if st.button("🚀 Auditar Partido Seleccionado (Web Search + SRI)", type="primary"):
        if not selected_match:
            st.warning("⚠️ Por favor, ingresa el nombre del partido que deseas auditar.")
        else:
            with st.spinner(f"Investigando en la web sobre '{selected_match}', analizando lesiones, rachas y valor (+EV)..."):
                try:
                    client = genai.Client(api_key=api_key)
                    
                    audit_prompt = f"""
                    Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV).
                    El usuario ha seleccionado el siguiente partido para auditar a fondo: "{selected_match}".
                    
                    PARÁMETROS DE CONFIGURACIÓN:
                    - Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
                    - Probabilidad Mínima Exigida: {prob_min}%.
                    - Monto planificado para apostar: ${monto_apuesta:.2f} USD.

                    INSTRUCCIONES DE FORMATO Y CONTENIDO:
                    1. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas de última hora, lesiones, estado de forma y contexto actual de este evento específico.
                    2. Genera un informe estructurado con los siguientes puntos:
                       - 📌 **EVENTO Y MERCADO SELECCIONADO**
                       - 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
                       - 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI {retencion}%)**
                       - 💡 **VEREDICTO FINAL Y GESTIÓN DE RIESGO (STAKE)**
                       - 🔀 **COMBINACIONES Y MERCADOS ALTERNATIVOS**
                    """
                    
                    audit_response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=[audit_prompt],
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}]
                        )
                    )

                    st.markdown("---")
                    st.subheader("📊 Informe de Auditoría Quirúrgica")
                    st.markdown(audit_response.text)

                except Exception as e:
                    st.error(f"Ocurrió un error al procesar la auditoría: {str(e)}")
