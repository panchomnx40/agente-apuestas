import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# Configuración inicial de la página
st.set_page_config(
    page_title="Agente Auditor de Apuestas",
    page_icon="⚽",
    layout="wide"
)

# Inicializar estado para guardar las imágenes en sesión
if "images_list" not in st.session_state:
    st.session_state.images_list = []

# Encabezado principal
st.title("⚽ Agente Auditor de Apuestas Deportivas")
st.markdown("Sube tus capturas de pantalla para que el agente busque automáticamente noticias en la web y audite la jugada (+EV) descontando el SRI.")

# ---------------------------------------------------------
# BARRA LATERAL (Configuración)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración del Agente")
    
    # Obtener API Key de Secrets o Entorno
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if api_key:
        genai.configure(api_key=api_key)
        st.success("✔ Clave API cargada automáticamente")
    else:
        st.error("❌ No se encontró GEMINI_API_KEY en los Secrets.")

    st.markdown("---")
    
    # Casilleros numéricos editables (+ / -)
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
# SECCIÓN 1: AGREGAR Y GESTIONAR CAPTURAS
# ---------------------------------------------------------
st.subheader("1. Agregar capturas de pantalla")

uploaded_files = st.file_uploader(
    "Sube tus capturas (PNG, JPG, JPEG):",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
    help="Puedes arrastrar tus imágenes aquí o seleccionarlas desde tu PC/Celular."
)

if uploaded_files:
    for file in uploaded_files:
        img = Image.open(file)
        if img not in st.session_state.images_list:
            st.session_state.images_list.append(img)

# Mostrar previsualización y opción de eliminar imágenes
if st.session_state.images_list:
    st.markdown("### 🖼️ Capturas cargadas para la auditoría:")
    cols = st.columns(min(len(st.session_state.images_list), 4))
    
    indices_to_remove = []
    for idx, img in enumerate(st.session_state.images_list):
        with cols[idx % 4]:
            st.image(img, use_container_width=True)
            if st.button(f"🗑️ Eliminar #{idx+1}", key=f"del_{idx}"):
                indices_to_remove.append(idx)
    
    if indices_to_remove:
        for index in sorted(indices_to_remove, reverse=True):
            st.session_state.images_list.pop(index)
        st.rerun()

# ---------------------------------------------------------
# SECCIÓN 2: MONTO Y PARÁMETROS DE APUESTA
# ---------------------------------------------------------
st.subheader("2. Monto de Inversión")

monto_apuesta = st.number_input(
    "Monto a apostar ($ USD):",
    min_value=1.0,
    value=10.0,
    step=5.0,
    help="Monto simulado para calcular ganancias y gestión de riesgo (Stake)"
)

# ---------------------------------------------------------
# BOTÓN DE PROCESAMIENTO
# ---------------------------------------------------------
if st.button("🚀 Auditar Apuesta con Gemini", type="primary"):
    if not st.session_state.images_list:
        st.warning("⚠️ Agrega al menos una captura de pantalla antes de realizar la auditoría.")
    elif not api_key:
        st.error("❌ No se puede continuar sin la clave de API.")
    else:
        with st.spinner("Buscando en la web noticias, alineaciones, analizando mercados y valor (+EV)..."):
            try:
                # Inicializar modelo con herramienta de búsqueda web automática (Google Search Grounding)
                model = genai.GenerativeModel(
                    model_name="gemini-3.8-flash",
                    tools=["google_search"]
                )

                # System Prompt autónomo con búsqueda web
                system_prompt = f"""
Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV).
1. Analiza detalladamente CADA UNA de las imágenes adjuntas para identificar los equipos, cuotas y mercados ofertados.
2. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas de última hora, lesiones, estado de forma y contexto actual de los equipos involucrados en el evento deportivo.

PARÁMETROS DE CONFIGURACIÓN:
- Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
- Probabilidad Mínima Exigida: {prob_min}%.
- Monto planificado para apostar: ${monto_apuesta:.2f} USD.

INSTRUCCIONES DE FORMATO Y CONTENIDO (Explica todo en un lenguaje claro, directo y fácil de entender para el usuario):

1. 📌 **EVENTO Y MERCADO IDENTIFICADO**
   - Nombre del partido y cuotas observadas.
   - Mercado específico recomendado para la apuesta (ej: Resultado Final, Ambos Anotan, Hándicap Asiático, etc.).

2. 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
   - Resumen breve de lo que encontraste en internet sobre el partido (lesionados clave, rachas recientes, motivación o declaraciones importantes).
   - Probabilidad real estimada cruzando las estadísticas con las noticias web (¿Supera el {prob_min}%?).

3. 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI)**
   - Si se invierten ${monto_apuesta:.2f} USD:
     * Ganancia Bruta Estimada: $[Calcular] USD.
     * Retención SRI ({retencion}% sobre la ganancia neta): $[Calcular] USD.
     * Ganancia Neta Final en mano: $[Calcular] USD.

4. 💡 **VEREDICTO FINAL Y GESTIÓN DE RIESGO (STAKE)**
     * Veredicto claro: **APROBADA** o **RECHAZADA**.
     * Sugerencia de Stake: ¿Conviene arriesgar los ${monto_apuesta:.2f} USD completos o es mejor bajar el monto (ej. arriesgar solo el 50%) debido a factores de riesgo encontrados en la web?

5. 🔀 **COMBINACIONES Y MERCADOS ALTERNATIVOS**
   - Sugiere combinaciones o mercados alternativos (ej: doble oportunidad o hándicap protector) para asegurar de mejor manera el capital.
"""

                inputs = [system_prompt] + st.session_state.images_list
                response = model.generate_content(inputs)

                st.markdown("---")
                st.subheader("📋 Informe de Auditoría y Búsqueda Web")
                st.markdown(response.text)

            except Exception as e:
                st.error(f"Ocurrió un error al procesar la auditoría: {str(e)}")
