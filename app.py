import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_paste_button import paste_image_button

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Agente Auditor +EV",
    page_icon="⚽",
    layout="wide"
)

# --- CONTROL DE ACCESO CON CONTRASEÑA ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Acceso Restringido")
        pwd = st.text_input("Ingresa la contraseña para acceder:", type="password")
        if st.button("Ingresar"):
            expected_password = st.secrets.get("APP_PASSWORD", "1234")
            if pwd == expected_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
        return False
    return True

if not check_password():
    st.stop()

# --- OBTENER CLAVE API DE GEMINI DESDE SECRETS ---
api_key = st.secrets.get("GEMINI_API_KEY", "")

# --- BARRA LATERAL DE CONFIGURACIÓN ---
with st.sidebar:
    st.title("⚙️ Configuración del Agente")
    
    if not api_key:
        api_key = st.text_input("Clave API de Gemini:", type="password")
    else:
        st.success("✅ Clave API cargada automáticamente")
    
    retencion = st.slider("Retención de impuesto SRI (%)", 0, 25, 15)
    prob_min = st.slider("Probabilidad Mínima Exigida (%)", 50, 95, 85)

# --- CONTENIDO PRINCIPAL ---
st.title("⚽ Agente Auditor de Apuestas Deportivas")
st.write("Toma capturas con `Win + Shift + S` y pégalas directamente con el botón verde para evaluar la jugada (+EV) descontando la retención del SRI.")

# --- MANEJO DE IMÁGENES EN SESSION STATE ---
if "images" not in st.session_state:
    st.session_state.images = []

st.subheader("1. Agregar capturas de pantalla")

col_paste, col_upload = st.columns([1, 1])

with col_paste:
    paste_result = paste_image_button(
        label="📋 Pegar captura del portapapeles",
        background_color="#28a745",
        hover_background_color="#218838",
    )
    if paste_result.image_data is not None:
        st.session_state.images.append(paste_result.image_data)
        st.rerun()

with col_upload:
    uploaded_files = st.file_uploader(
        "O sube archivos desde tu PC/Celular", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    if uploaded_files:
        for file in uploaded_files:
            img = Image.open(file)
            if img not in st.session_state.images:
                st.session_state.images.append(img)

if st.session_state.images:
    st.write(f"**Imágenes cargadas ({len(st.session_state.images)}):**")
    
    if st.button("🗑️ Limpiar todas las imágenes"):
        st.session_state.images = []
        st.rerun()
        
    cols = st.columns(min(len(st.session_state.images), 4))
    idx_to_remove = None
    for i, img in enumerate(st.session_state.images):
        with cols[i % 4]:
            st.image(img, use_container_width=True)
            if st.button(f"❌ Eliminar #{i+1}", key=f"del_{i}"):
                idx_to_remove = i
                
    if idx_to_remove is not None:
        st.session_state.images.pop(idx_to_remove)
        st.rerun()

# --- SECCIÓN DE AUDITORÍA ---
st.subheader("2. Auditoría e Inteligencia de Apuestas")
prompt_user = st.text_area(
    "Notas o contexto adicional (opcional):", 
    placeholder="Ej: Es un partido de vuelta, el equipo local llega con bajas importantes..."
)

if st.button("🚀 Auditar Apuesta con Gemini", type="primary"):
    if not api_key:
        st.error("Por favor ingresa o configura la Clave API de Gemini.")
    elif not st.session_state.images:
        st.warning("Debes adjuntar al menos una imagen de la apuesta para auditar.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3.8-flash')
            
            system_prompt = f"""
            Eres un auditor experto en apuestas deportivas de alto valor (+EV).
            Analiza CADA UNA de las imágenes adjuntas detalladamente.
            
            Toma en cuenta los siguientes parámetros de configuración:
            - Retención de impuesto SRI (Ecuador): {retencion}%
            - Probabilidad Mínima Exigida: {prob_min}%
            
            Proporciona un desglose cuantitativo estructurado:
            1. Identificación del evento, cuotas y mercado ofertado.
            2. Análisis de probabilidad base e imparcial.
            3. Aplicación del filtro Red Teaming (riesgos, trampas o letra chica del mercado).
            4. Ajuste fiscal descontando el {retencion}% del SRI sobre la ganancia neta.
            5. Verificación de Valor Esperado Positivo (+EV) y veredicto final (APROBADA / RECHAZADA).
            
            Notas del usuario: {prompt_user if prompt_user else 'Ninguna'}
            """
            
            contents = [system_prompt] + st.session_state.images
            
            with st.spinner("Analizando jugada y calculando EV..."):
                response = model.generate_content(contents)
                st.markdown("### 📊 Informe de Auditoría")
                st.markdown(response.text)
                
        except Exception as e:
            st.error(f"Ocurrió un error al consultar el modelo: {str(e)}")
