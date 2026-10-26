import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import json

# Configuración inicial de la página
st.set_page_config(
    page_title="Value Radar - Auditor de Apuestas",
    page_icon="⚽",
    layout="wide"
)

# Archivo local para persistir el historial de apuestas
HISTORY_FILE = "historial_apuestas.json"

def cargar_historial():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_historial(historial):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

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
if "direct_images_list" not in st.session_state:
    st.session_state.direct_images_list = []
if "direct_audit_result" not in st.session_state:
    st.session_state.direct_audit_result = None
if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()

# Encabezado principal
st.title("⚽ Value Radar: Escáner y Auditor de Apuestas")
st.markdown("Sistema inteligente con modo dual: **1)** Radar de cartelera o **2)** Auditoría directa de un partido específico con recomendación de Stake, Web Search y SRI.")

# ---------------------------------------------------------
# BARRA LATERAL (Configuración e Historial Rápido)
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
    
    st.markdown("---")
    st.subheader("📊 Resumen de Rendimiento")
    total_apuestas = len(st.session_state.historial)
    ganadas = sum(1 for h in st.session_state.historial if h["resultado"] == "Ganada")
    perdidas = sum(1 for h in st.session_state.historial if h["resultado"] == "Perdida")
    winrate = (ganadas / total_apuestas * 100) if total_apuestas > 0 else 0.0
    
    st.metric("Total Registradas", total_apuestas)
    st.metric("Efectividad (Winrate)", f"{winrate:.1f}%", f"🟢 {ganadas} G / 🔴 {perdidas} P")

# ---------------------------------------------------------
# SELECTOR DE MODO DE OPERACIÓN
# ---------------------------------------------------------
st.markdown("---")
modo_operacion = st.radio(
    "Selecciona el modo de trabajo que prefieres utilizar:",
    [
        "🎯 Modo Radar: Escanear cartelera completa de partidos",
        "⚡ Modo Directo: Auditar un partido específico de mi preferencia"
    ],
    horizontal=True
)

# ---------------------------------------------------------
# MODO 1: RADAR DE JORNADA (ESCANEO Y SELECCIÓN)
# ---------------------------------------------------------
if modo_operacion == "🎯 Modo Radar: Escanear cartelera completa de partidos":
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
                        2. Al final de tu respuesta, INCLUYE OBLIGATORIAMENTE un bloque etiquetado exactamente como `LISTA_PARTIDOS:` seguido de los nombres de los partidos filtrados separados por comas o saltos de línea (ejemplo: `LISTA_PARTIDOS: Equipo A vs Equipo B, Equipo C vs Equipo D`).
                        
                        Estructura tu reporte visual así:
                        - 📌 **Resumen de Oportunidades Detectadas**
                        """
                        contents = [scan_prompt] + st.session_state.images_list
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=contents
                        )
                        st.session_state.scan_result = response.text
                        
                        if "LISTA_PARTIDOS:" in response.text:
                            raw_matches = response.text.split("LISTA_PARTIDOS:")[1].strip().split("\n")[0]
                            matches = [m.strip(" *-•") for m in raw_matches.split(",") if m.strip()]
                            st.session_state.detected_matches = matches
                        else:
                            st.session_state.detected_matches = ["Ingresar partido manualmente..."]

                    except Exception as e:
                        st.error(f"Ocurrió un error en el escaneo: {str(e)}")

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

        st.markdown("---")
        st.subheader("Fase 2: Auditoría Quirúrgica con Memoria Histórica")
        
        options = st.session_state.detected_matches + ["Otro (Escribir manualmente)"]
        selected_option = st.selectbox("Elige el partido a auditar del radar:", options)
        
        if selected_option == "Otro (Escribir manualmente)":
            target_match = st.text_input("Escribe el nombre del partido (ej. Equipo A vs Equipo B):")
        else:
            target_match = selected_option

        st.markdown("#### 📸 Capturas específicas de mercados (Opcional)")
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
            key="monto_f2",
            help="Monto simulado para calcular ganancias y riesgo"
        )

        if st.button("🚀 Auditar con Aprendizaje Histórico (Web Search + SRI)", type="primary"):
            if not target_match:
                st.warning("⚠️ Selecciona o ingresa un partido para auditar.")
            else:
                with st.spinner(f"Analizando '{target_match}' cruzando datos con tu historial de aciertos y la web..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        resumen_historial = "Historial reciente del apostador:\n"
                        if st.session_state.historial:
                            for h in st.session_state.historial[-10:]:
                                resumen_historial += f"- Partido: {h['partido']} | Apuesta: {h['mercado']} | Resultado: {h['resultado']}\n"
                        else:
                            resumen_historial += "Aún no hay historial registrado. Esta es la primera auditoría.\n"

                        audit_prompt = f"""
                        Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV) con memoria analítica.
                        El usuario va a auditar el siguiente partido: "{target_match}".
                        
                        {resumen_historial}
                        
                        INSTRUCCIÓN DE APRENDIZAJE: Revisa el historial previo del usuario. Si detectas patrones de fallos en ciertos mercados o ligas similares, ajusta tus recomendaciones y advierte al usuario para evitar cometer los mismos errores.
                        
                        PARÁMETROS DE CONFIGURACIÓN:
                        - Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
                        - Probabilidad Mínima Exigida: {prob_min}%.
                        - Monto planificado para apostar: ${monto_apuesta:.2f} USD.

                        INSTRUCCIONES DE FORMATO Y CONTENIDO:
                        1. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas y lesiones de este evento.
                        2. Analiza las capturas de mercados (si las hay) evaluando combinadas o alternativas.
                        3. Genera el informe estructurado:
                           - 📌 **EVENTO Y MERCADOS EVALUADOS**
                           - 🧠 **ANÁLISIS DE APRENDIZAJE BASADO EN TU HISTORIAL**
                           - 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
                           - 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI {retencion}%)**
                           - 💡 **VEREDICTO FINAL Y RECOMENDACIÓN DE STAKE (GESTIÓN DE RIESGO)**: Da un veredicto claro (APROBADA / RECHAZADA) y una recomendación EXPLÍCITA de Stake (indica si se debe arriesgar el 100% de los ${monto_apuesta:.2f} o si debido al riesgo se sugiere usar solo una fracción, ej. 50% o 25%, con su debida justificación)[cite: 3].
                           - 🔀 **COMBINACIONES O MERCADOS ALTERNATIVOS**
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

    if st.session_state.audit_result:
        st.markdown("---")
        st.subheader("📊 Informe de Auditoría Quirúrgica")
        st.markdown(st.session_state.audit_result)

        st.markdown("---")
        st.subheader("📝 Registrar Resultado de esta Apuesta en el Historial")
        st.caption("Una vez que finalice el partido, ingresa aquí si fue favorable o no para que el agente aprenda para el futuro.")
        
        with st.form("form_registro_historial_f2"):
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                mercado_jugado = st.text_input("Mercado apostado (ej. Gana Local / +2.5 Goles):")
            with col_h2:
                res_apuesta = st.selectbox("Resultado real:", ["Ganada", "Perdida", "Nula"])
            with col_h3:
                monto_real = st.number_input("Monto invertido ($):", value=monto_apuesta)
                
            submitted_hist = st.form_submit_button("💾 Guardar en el Historial del Agente")
            
            if submitted_hist:
                nuevo_registro = {
                    "partido": target_match,
                    "mercado": mercado_jugado if mercado_jugado else "Apuesta General",
                    "resultado": res_apuesta,
                    "monto": monto_real
                }
                st.session_state.historial.append(nuevo_registro)
                guardar_historial(st.session_state.historial)
                st.success("✅ ¡Apuesta registrada con éxito! El agente ha incorporado este resultado a su memoria de aprendizaje.")
                st.rerun()

        if st.button("🔄 Descartar esta auditoría y probar otro partido del Radar", type="secondary"):
            st.session_state.audit_result = None
            st.session_state.detail_images_list = []
            st.rerun()

# ---------------------------------------------------------
# MODO 2: AUDITORÍA DIRECTA DE UN PARTIDO ESPECÍFICO
# ---------------------------------------------------------
else:
    st.subheader("⚡ Modo Directo: Auditoría de un Partido Específico")
    st.markdown("¿Tienes un partido en mente? Sube directamente la captura del encuentro o mercado y deja que el agente lo audite con búsqueda web, SRI y recomendación de Stake.")

    direct_match_name = st.text_input("Nombre del partido (opcional, el agente puede leerlo de la imagen):", placeholder="Ej: Barcelona SC vs LDU")
    
    direct_files = st.file_uploader(
        "Sube la captura de pantalla del partido o mercados:",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="uploader_modo_directo"
    )

    if direct_files:
        for file in direct_files:
            img = Image.open(file)
            if img not in st.session_state.direct_images_list:
                st.session_state.direct_images_list.append(img)

    if st.session_state.direct_images_list:
        d_cols = st.columns(min(len(st.session_state.direct_images_list), 4))
        d_indices_to_remove = []
        for idx, img in enumerate(st.session_state.direct_images_list):
            with d_cols[idx % 4]:
                st.image(img, use_container_width=True)
                if st.button(f"❌ Quitar #{idx+1}", key=f"del_direct_{idx}"):
                    d_indices_to_remove.append(idx)
        
        if d_indices_to_remove:
            for index in sorted(d_indices_to_remove, reverse=True):
                st.session_state.direct_images_list.pop(index)
            st.rerun()

    monto_directo = st.number_input(
        "Monto a apostar ($ USD):",
        min_value=1.0,
        value=10.0,
        step=5.0,
        key="monto_directo",
        help="Monto simulado para calcular ganancias y riesgo"
    )

    if st.button("🚀 Auditar Partido Directo (Web Search + SRI + Stake)", type="primary"):
        if not st.session_state.direct_images_list:
            st.warning("⚠️ Sube al menos una captura del partido o mercado.")
        else:
            partido_ref = direct_match_name if direct_match_name else "Partido analizado por imagen"
            with st.spinner(f"Analizando partido, buscando en la web, calculando SRI y evaluando Stake óptimo..."):
                try:
                    client = genai.Client(api_key=api_key)
                    
                    resumen_historial = "Historial reciente del apostador:\n"
                    if st.session_state.historial:
                        for h in st.session_state.historial[-10:]:
                            resumen_historial += f"- Partido: {h['partido']} | Apuesta: {h['mercado']} | Resultado: {h['resultado']}\n"
                    else:
                        resumen_historial += "Aún no hay historial registrado.\n"

                    direct_prompt = f"""
                    Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV) con memoria analítica.
                    El usuario ha seleccionado auditar directamente un partido/mercado a través de la(s) imagen(es) adjunta(s). Referencia ingresada: "{partido_ref}".
                    
                    {resumen_historial}
                    
                    INSTRUCCIÓN DE APRENDIZAJE: Revisa el historial previo del usuario. Si detectas patrones de fallos, ajusta tus recomendaciones y advierte al usuario.
                    
                    PARÁMETROS DE CONFIGURACIÓN:
                    - Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
                    - Probabilidad Mínima Exigida: {prob_min}%.
                    - Monto planificado para apostar: ${monto_directo:.2f} USD.

                    INSTRUCCIONES DE FORMATO Y CONTENIDO:
                    1. Identifica claramente los equipos y el mercado en la(s) imagen(es).
                    2. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas y lesiones de este evento.
                    3. Genera el informe estructurado:
                       - 📌 **EVENTO Y MERCADOS IDENTIFICADOS**
                       - 🧠 **ANÁLISIS DE APRENDIZAJE BASADO EN TU HISTORIAL**
                       - 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
                       - 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI {retencion}%)**
                       - 💡 **VEREDICTO FINAL Y RECOMENDACIÓN DE STAKE (GESTIÓN DE RIESGO)**: Da un veredicto claro (APROBADA / RECHAZADA) y una recomendación EXPLÍCITA de Stake (indica si se debe arriesgar el 100% de los ${monto_directo:.2f} o si debido al riesgo se sugiere usar solo una fracción, ej. 50% o 25%, con su debida justificación)[cite: 3].
                       - 🔀 **COMBINACIONES O MERCADOS ALTERNATIVOS**
                    """
                    
                    contents = [direct_prompt] + st.session_state.direct_images_list
                    direct_response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}]
                        )
                    )
                    st.session_state.direct_audit_result = direct_response.text

                except Exception as e:
                    st.error(f"Ocurrió un error al procesar la auditoría directa: {str(e)}")

    if st.session_state.direct_audit_result:
        st.markdown("---")
        st.subheader("📊 Informe de Auditoría Directa")
        st.markdown(st.session_state.direct_audit_result)

        st.markdown("---")
        st.subheader("📝 Registrar Resultado de esta Apuesta en el Historial")
        
        with st.form("form_registro_historial_directo"):
            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                mercado_jugado_d = st.text_input("Mercado apostado (ej. Gana Local / +2.5 Goles):")
            with col_d2:
                res_apuesta_d = st.selectbox("Resultado real:", ["Ganada", "Perdida", "Nula"], key="res_d")
            with col_d3:
                monto_real_d = st.number_input("Monto invertido ($):", value=monto_directo, key="monto_d")
                
            submitted_hist_d = st.form_submit_button("💾 Guardar en el Historial del Agente")
            
            if submitted_hist_d:
                nombre_reg = direct_match_name if direct_match_name else "Partido Directo"
                nuevo_registro = {
                    "partido": nombre_reg,
                    "mercado": mercado_jugado_d if mercado_jugado_d else "Apuesta General",
                    "resultado": res_apuesta_d,
                    "monto": monto_real_d
                }
                st.session_state.historial.append(nuevo_registro)
                guardar_historial(st.session_state.historial)
                st.success("✅ ¡Apuesta registrada con éxito! El agente ha incorporado este resultado a su memoria de aprendizaje.")
                st.rerun()

        if st.button("🔄 Limpiar y realizar otra auditoría directa", type="secondary"):
            st.session_state.direct_audit_result = None
            st.session_state.direct_images_list = []
            st.rerun()

# ---------------------------------------------------------
# SECCIÓN 3: VISUALIZACIÓN DEL HISTORIAL COMPLETO
# ---------------------------------------------------------
st.markdown("---")
with st.expander("📂 Ver y Administrar Historial Completo de Apuestas"):
    if st.session_state.historial:
        st.dataframe(st.session_state.historial, use_container_width=True)
        
        if st.button("🗑️ Borrar todo el Historial de Apuestas"):
            st.session_state.historial = []
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
            st.success("Historial reiniciado correctamente.")
            st.rerun()
    else:
        st.info("No hay apuestas registradas todavía.")
