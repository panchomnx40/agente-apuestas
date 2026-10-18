import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import re

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
if "detected_matches" not in st.session_state:
    st.session_state.detected_matches = []
if "detail_images_list" not in st.session_state:
    st.session_state.detail_images_list = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None

# Encabezado principal
st.title("⚽ Value Radar: Escáner y Auditor de Apuestas")
st.markdown("Sistema interactivo en dos fases: **1)** Escaneo y filtrado de valor. **2)** Selección rápida, análisis de mercados/combinadas, Búsqueda Web y SRI.")

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
    accept_multiple_files=True,
    key="uploader_fase1"
)

if uploaded_files:
    for file in uploaded_files:
        img = Image.open(file)
        if img not in st.session_state.images_list:
            st.session_state.images_list.append(img)

# Previsualización de imágenes Fase 1
if st.session_state.images_list:
    cols = st.columns(min(len(st.session_state.images_list), 4))
    indices_to_remove = []
    for idx, img in enumerate(st.session_state.images_list):
        with cols[idx % 4]:
            st.image(img, use_container_width=True)
            if st.button(f"❌ Quitar #{idx+1}", key=f"del_f1_{idx}"):
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
                    
                    scan_prompt = """
                    Eres un experto analista de mercados de apuestas y cazador de valor (+EV).
                    Analiza detalladamente la(s) imagen(es) de la cartelera de partidos adjuntas.
                    
                    INSTRUCCIÓN CRÍTICA:
                    1. FILTRA y SELECCIONA ÚNICAMENTE los encuentros que presenten cuotas atractivas o potencial de valor.
                    2. Al final de tu respuesta, INCLUYE OBLIGATORIAMENTE un bloque etiquetado exactamente como `LISTA_PARTIDOS:` seguido de los nombres de los partidos filtrados separados por comas o saltos de línea (ejemplo: `LISTA_PARTIDOS: Equipo A vs Equipo B, Equipo C vs Equipo D`). Esto servirá para alimentarlos al menú desplegable.
                    
                    Estructura tu reporte visual así:
                    - 📌 **Resumen de Oportunidades Detectadas** (Indica el partido, cuotas clave y por qué destaca).
                    """
                    
                    contents = [scan_prompt] + st.session_state.images_list
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=contents
                    )
                    st.session_state.scan_result = response.text
                    
                    # Extraer partidos formateados para la lista desplegable
                    if "LISTA_PARTIDOS:" in response.text:
                        raw_matches = response.text.split("LISTA_PARTIDOS:")[1].strip().split("\n")[0]
                        matches = [m.strip(" *-•") for m in raw_matches.split(",") if m.strip()]
                        st.session_state.detected_matches = matches
                    else:
                        st.session_state.detected_matches = ["Ingresar partido manualmente..."]

                except Exception as e:
                    st.error(f"Ocurrió un error en el escaneo: {str(e)}")

# Mostrar resultados del escaneo si ya se procesó
if st.session_state.scan_result:
    st.markdown("---")
    st.subheader("🎯 Oportunidades Detectadas por el Radar")
    st.markdown(st.session_state.scan_result)

    if st.button("🗑️ Limpiar Radar y Cargar Otra Captura", type="secondary"):
        st.session_state.images_list = []
        st.session_state.scan_result = None
        st.session_state.detected_matches = []
        st.session_state.detail_images_list = []
        st.session_state.audit_result = None
        st.rerun()

    # ---------------------------------------------------------
    # FASE 2: AUDITORÍA QUIRÚRGICA CON MERCADOS Y SELECCIÓN
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("Fase 2: Auditoría Quirúrgica de un Partido Seleccionado")
    
    # Menú desplegable alimentado por el Radar
    options = st.session_state.detected_matches + ["Otro (Escribir manualmente)"]
    selected_option = st.selectbox("Elige el partido a auditar del radar:", options)
    
    if selected_option == "Otro (Escribir manualmente)":
        target_match = st.text_input("Escribe el nombre del partido (ej. Equipo A vs Equipo B):")
    else:
        target_match = selected_option

    st.markdown("#### 📸 Capturas específicas de mercados (Opcional)")
    st.caption("Puedes subir capturas de los mercados específicos de este partido (ej. Ambos Anotan, Córneres, Doble Oportunidad, Combinadas de la casa).")
    
    detail_files = st.file_uploader(
        "Sube capturas de mercados específicos del partido:",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="uploader_fase2"
    )

    if detail_files:
        for file in detail_files:
            img = Image.open(file)
            if img not in st.session_state.detail_images_list:
                st.session_state.detail_images_list.append(img)

    if st.session_state.detail_images_list:
        d_cols = st.columns(min(len(st.session_state.detail_images_list), 4))
        d_indices_to_remove = []
        for idx, img in enumerate(st.session_state.detail_images_list):
            with d_cols[idx % 4]:
                st.image(img, use_container_width=True)
                if st.button(f"❌ Quitar #{idx+1}", key=f"del_f2_{idx}"):
                    d_indices_to_remove.append(idx)
        
        if d_indices_to_remove:
            for index in sorted(d_indices_to_remove, reverse=True):
                st.session_state.detail_images_list.pop(index)
            st.rerun()

    monto_apuesta = st.number_input(
        "Monto a apostar ($ USD):",
        min_value=1.0,
        value=10.0,
        step=5.0,
        help="Monto simulado para calcular ganancias y gestión de riesgo (Stake)"
    )

    if st.button("🚀 Auditar Partido Seleccionado (Web Search + SRI)", type="primary"):
        if not target_match:
            st.warning("⚠️ Selecciona o ingresa un partido para auditar.")
        else:
            with st.spinner(f"Investigando en la web sobre '{target_match}', evaluando mercados, combinadas y SRI..."):
                try:
                    client = genai.Client(api_key=api_key)
                    
                    audit_prompt = f"""
                    Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV).
                    El usuario ha seleccionado el siguiente partido para auditar a fondo: "{target_match}".
                    
                    PARÁMETROS DE CONFIGURACIÓN:
                    - Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
                    - Probabilidad Mínima Exigida: {prob_min}%.
                    - Monto planificado para apostar: ${monto_apuesta:.2f} USD.

                    INSTRUCCIONES DE FORMATO Y CONTENIDO:
                    1. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas de última hora, lesiones, estado de forma y contexto actual de este evento específico.
                    2. Analiza las capturas de mercados adjuntas (si las hay) y evalúa si conviene la apuesta directa, una apuesta combinada o mercados alternativos/protectores (ej. Doble Oportunidad, Hándicap Asiático).
                    3. Genera el informe estructurado:
                       - 📌 **EVENTO Y MERCADOS EVALUADOS**
                       - 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
                       - 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI {retencion}%)**
                       - 💡 **VEREDICTO FINAL Y GESTIÓN DE RIESGO (STAKE)**
                       - 🔀 **MEJORES COMBINACIONES O MERCADOS ALTERNATIVOS**
                    """
                    
                    contents = [audit_prompt] + st.session_state.detail_images_list
                    
                    audit_response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}]
                        )
                    )

                    st.session_state.audit_result = audit_response.text

                except Exception as e:
                    st.error(f"Ocurrió un error al procesar la auditoría: {str(e)}")

# Mostrar resultados de la auditoría individual
if st.session_state.audit_result:
    st.markdown("---")
    st.subheader("📊 Informe de Auditoría Quirúrgica")
    st.markdown(st.session_state.audit_result)

    # Botón exclusivo para descartar la auditoría fallida/rechazada y elegir otro partido
    if st.button("🔄 Descartar esta auditoría y probar otro partido del Radar", type="secondary"):
        st.session_state.audit_result = None
        st.session_state.detail_images_list = []
        st.rerun()
