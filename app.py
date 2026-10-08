import PIL.Image
import google.generativeai as genai
import streamlit as st
from streamlit_paste_button import paste_image_button

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA WEB
# ==========================================
st.set_page_config(
    page_title="Auditor de Apuestas +EV",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("⚽ Agente Auditor de Apuestas Deportivas")
st.write(
    "Toma capturas con `Win + Shift + S` y pégalas directamente con el botón"
    " verde para evaluar la jugada (+EV) descontando la retención del SRI."
)

# Inicializar estados de memoria de la sesión
if "lista_imagenes" not in st.session_state:
  st.session_state.lista_imagenes = []

if "last_seen_paste" not in st.session_state:
  st.session_state.last_seen_paste = None

# ==========================================
# 2. PANEL LATERAL (CONFIGURACIÓN)
# ==========================================
st.sidebar.header("⚙️ Configuración del Agente")

api_key = st.sidebar.text_input(
    "Clave API de Gemini:",
    type="password",
    help="Ingresa tu API Key de Google AI Studio.",
)

sri_impuesto = (
    st.sidebar.slider(
        "Retención de impuesto SRI (%)",
        min_value=0,
        max_value=25,
        value=15,
        step=1,
    )
    / 100
)

prob_minima = st.sidebar.slider(
    "Probabilidad Mínima Exigida (%)",
    min_value=50,
    max_value=95,
    value=85,
    step=1,
)

# ==========================================
# 3. ÁREA DE PEGAR Y SUBIR IMÁGENES
# ==========================================
st.subheader("1. Adjuntar capturas de pantalla")

col1, col2 = st.columns(2)

with col1:
  paste_result = paste_image_button(
      label="📋 Pegar captura del portapapeles",
      text_color="#ffffff",
      background_color="#2e7d32",
      hover_background_color="#1b5e20",
  )

  # Control de flujo para evitar repetición al limpiar
  if (
      paste_result.image_data is not None
      and paste_result.image_data != st.session_state.last_seen_paste
  ):
    st.session_state.last_seen_paste = paste_result.image_data
    st.session_state.lista_imagenes.append(paste_result.image_data)
    st.success("¡Captura pegada con éxito!")

with col2:
  uploaded_files = st.file_uploader(
      "O sube archivos desde tu PC",
      type=["png", "jpg", "jpeg"],
      accept_multiple_files=True,
  )
  if uploaded_files:
    for file in uploaded_files:
      img = PIL.Image.open(file)
      if img not in st.session_state.lista_imagenes:
        st.session_state.lista_imagenes.append(img)

# ==========================================
# 4. GESTIÓN DE CAPTURAS (ELIMINACIÓN INDIVIDUAL O TOTAL)
# ==========================================
if st.session_state.lista_imagenes:
  st.markdown("---")
  col_head1, col_head2 = st.columns([3, 1])

  with col_head1:
    st.write(
        f"📷 **Capturas acumuladas:** {len(st.session_state.lista_imagenes)}"
    )

  with col_head2:
    if st.button("🗑️ Limpiar todo", type="secondary"):
      st.session_state.lista_imagenes = []
      if paste_result.image_data is not None:
        st.session_state.last_seen_paste = paste_result.image_data
      st.rerun()

  # Mostrar miniaturas con botón individual de borrado
  cols = st.columns(min(len(st.session_state.lista_imagenes), 3))
  i_to_delete = None

  for idx, img in enumerate(st.session_state.lista_imagenes):
    with cols[idx % 3]:
      st.image(img, caption=f"Captura {idx + 1}", use_container_width=True)
      if st.button(
          f"❌ Eliminar #{idx + 1}", key=f"btn_del_{idx}", use_container_width=True
      ):
        i_to_delete = idx

  # Si el usuario hace clic en el botón de eliminar de alguna captura
  if i_to_delete is not None:
    st.session_state.lista_imagenes.pop(i_to_delete)
    st.rerun()

  # ==========================================
  # 5. EJECUTAR AUDITORÍA
  # ==========================================
  st.subheader("2. Ejecutar Auditoría")

  if st.button("🔍 Analizar Apuestas con IA", type="primary"):
    if not api_key:
      st.error(
          "⚠️ Ingresa tu Clave API de Gemini en el panel izquierdo para"
          " continuar."
      )
    else:
      with st.spinner(
          "El agente está analizando TODAS las capturas y calculando el"
          " +EV..."
      ):
        try:
          genai.configure(api_key=api_key)

          try:
            model = genai.GenerativeModel("gemini-3.8-flash")
          except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")

          prompt_sistema = f"""
                    ERES UN ANALISTA CUANTITATIVO Y AUDITOR DE RIESGO DE APUESTAS DEPORTIVAS EXPERTO.

                    INSTRUCCIÓN CRÍTICA:
                    Se te han proporcionado {len(st.session_state.lista_imagenes)} CAPTURAS DE PANTALLA. 
                    DEBES EXAMINAR Y EXTRAER INFORMACIÓN DE CADA UNA DE ELLAS SIN EXCEPCIÓN.

                    PARÁMETROS DEL USUARIO:
                    - Impuesto SRI: {sri_impuesto * 100}%
                    - Probabilidad Mínima Exigida: {prob_minima}%

                    REGLAS DE CÁLCULO:
                    - Cuota Efectiva Post-SRI: C_efectiva = 1 + (C_nominal - 1) * {1 - sri_impuesto}
                    - Valor Esperado Neto (+EV): EV = (P_final / 100 * C_efectiva) - 1

                    FORMATO DE RESPUESTA OBLIGATORIO EN MARKDOWN:

                    ### ⚽ Partido: [Nombre del Evento / Equipos]

                    #### 📸 AUDITORÍA POR CAPTURA:

                    (Asegúrate de evaluar al menos 1 o 2 mercados clave y estadísticas visibles de CADA captura individual)

                    * **Captura 1:** [Resumen de lo observado, estadísticas e hilos de apuestas clave]
                      - **Mercado:** [Nombre Mercado] (Cuota: X.XX) | **P_final:** Z% | **C_efectiva:** X.XX | **+EV:** X.XX%
                    * **Captura 2:** [Resumen de lo observado, estadísticas e hilos de apuestas clave]
                      - **Mercado:** [Nombre Mercado] (Cuota: X.XX) | **P_final:** Z% | **C_efectiva:** X.XX | **+EV:** X.XX%
                    * **Captura 3 (si existe):** [Resumen de lo observado, estadísticas e hilos de apuestas clave]
                      - **Mercado:** [Nombre Mercado] (Cuota: X.XX) | **P_final:** Z% | **C_efectiva:** X.XX | **+EV:** X.XX%

                    #### 🏆 RESUMEN Y VEREDICTO FINAL:
                    - **Mejor opción identificada:** [Mercado y Cuota]
                    - **Veredicto:** **[APROBADA]** o **[RECHAZADA]** (Solo se aprueba si P_final >= {prob_minima}% Y +EV > 0).
                    - **Justificación detallada:** Explicación basada en las estadísticas cruzadas de todas las capturas.
                    """

          contenido = [prompt_sistema] + st.session_state.lista_imagenes
          response = model.generate_content(contenido)

          st.markdown("---")
          st.markdown("## 📋 Resultado del Análisis Global")
          st.markdown(response.text)

        except Exception as e:
          st.error(f"Ocurrió un error al procesar las imágenes: {e}")