import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import json
import re

# Configuración inicial de la página
st.set_page_config(
    page_title="Value Radar - Auditor de Apuestas",
    page_icon="⚽",
    layout="wide"
)

# Archivo local para persistir el historial de apuestas
HISTORY_FILE = "historial_apuestas.json"

def cargar_historial():
    # Intentar cargar desde el archivo local si existe
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except:
            pass
    return []

def guardar_historial(historial):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Error al guardar el historial: {str(e)}")

# ---------------------------------------------------------
# CONTROL DE ACCESO (Persistente y optimizado para móviles)
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

app_password = st.secrets.get("APP_PASSWORD", "")
if app_password and not st.session_state.authenticated:
    st.title("🔒 Acceso Restringido")
    with st.form("form_login"):
        pwd_input = st.text_input("Ingrese la contraseña de acceso:", type="password")
        submit_pwd = st.form_submit_button("Ingresar")
        if submit_pwd:
            if pwd_input == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()

# Inicialización robusta del historial en st.session_state sincronizado con disco
if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()
else:
    # Asegurar sincronización bidireccional por si el archivo local se actualiza
    disk_history = cargar_historial()
    if len(disk_history) > len(st.session_state.historial):
        st.session_state.historial = disk_history

# Inicializar otros estados en sesión
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

# Encabezado principal
st.title("⚽ Value Radar: Escáner, Auditor y Memoria de Aprendizaje")
st.markdown("Sistema inteligente: **1)** Radar o Modo Directo. **2)** Validación interactiva de boleto. **3)** Historial global persistente.")

# ---------------------------------------------------------
# BARRA LATERAL (Configuración, Resumen y Sincronización)
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

    st.markdown("---")
    st.subheader("📥 Sincronizar Historial Global")
    st.caption("Sube tu captura del historial de ganancias/pérdidas de Betano para alimentar la base de datos.")
    
    historial_global_file = st.file_uploader("Captura de historial Betano:", type=["png", "jpg", "jpeg"], key="historial_global_upload")
    
    if historial_global_file:
        hist_img = Image.open(historial_global_file)
        st.image(hist_img, caption="Historial Betano cargado", use_container_width=True)
        if st.button("🤖 Procesar e Integrar al Historial", key="btn_proc_hist"):
            if not api_key:
                st.error("Falta la clave API.")
            else:
                with st.spinner("Leyendo historial y actualizando base de datos..."):
                    try:
                        client_h = genai.Client(api_key=api_key)
                        prompt_h = """
                        Analiza esta captura de pantalla del historial de apuestas de Betano.
                        Extrae cada apuesta mostrada con su respectivo partido/evento, el mercado o tipo de apuesta, 
                        el resultado exacto ('Ganada', 'Perdida' o 'Nula') y el monto invertido.
                        Devuelve estrictamente una lista en formato JSON válido (un array de objetos):
                        [
                          {"partido": "Nombre del partido", "mercado": "Tipo de mercado", "resultado": "Ganada", "monto": 10.0}
                        ]
                        No agregues texto adicional fuera del formato JSON.
                        """
                        res_h = client_h.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[prompt_h, hist_img]
                        )
                        texto_json = res_h.text.strip()
                        if "```json" in texto_json:
                            texto_json = texto_json.split("```json")[1].split("```")[0].strip()
                        elif "```" in texto_json:
                            texto_json = texto_json.split("```")[1].split("```")[0].strip()
                            
                        nuevos_registros = json.loads(texto_json)
                        if isinstance(nuevos_registros, list):
                            for reg in nuevos_registros:
                                st.session_state.historial.append(reg)
                            guardar_historial(st.session_state.historial)
                            st.success(f"✅ ¡Se han integrado {len(nuevos_registros)} apuestas al historial!")
                            st.rerun()
                        else:
                            st.error("El formato extraído no es una lista válida.")
                    except Exception as e:
                        st.error(f"No se pudo procesar la imagen del historial: {str(e)}")

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
        st.session_state.images_list = []
        for file in uploaded_files:
            img = Image.open(file)
            st.session_state.images_list.append(img)

    if st.session_state.images_list:
        cols = st.columns(min(len(st.session_state.images_list), 4))
        for idx, img in enumerate(st.session_state.images_list):
            with cols[idx % 4]:
                st.image(img, use_container_width=True)

        if st.button("🗑️ Quitar Imágenes", key="clear_f1"):
            st.session_state.images_list = []
            st.session_state.scan_result = None
            st.session_state.detected_matches = []
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
                        2. Al final de tu respuesta, INCLUYE OBLIGATORIAMENTE un bloque etiquetado exactamente como `LISTA_PARTIDOS:` seguido de los partidos separados por comas o saltos de línea (Ejemplo: `LISTA_PARTIDOS: Liverpool FC vs Chelsea FC, Manchester City vs Brighton, AC Monza vs SSC Napoli`).
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
                            raw_line = response.text.split("LISTA_PARTIDOS:")[1].strip().split("\n")[0]
                            parts = [p.strip(" *-•") for p in raw_line.split(",") if p.strip()]
                            if len(parts) <= 1:
                                matches = [m.strip(" *-•") for m in raw_line.split("\n") if m.strip()]
                            else:
                                matches = parts
                            st.session_state.detected_matches = matches if matches else ["Ingresar partido manualmente..."]
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
            st.session_state.detail_images_list = []
            for file in detail_files:
                img = Image.open(file)
                st.session_state.detail_images_list.append(img)

        if st.session_state.detail_images_list:
            d_cols = st.columns(min(len(st.session_state.detail_images_list), 4))
            for idx, img in enumerate(st.session_state.detail_images_list):
                with d_cols[idx % 4]:
                    st.image(img, use_container_width=True)

            if st.button("❌ Quitar Capturas de Mercado", key="clear_f2"):
                st.session_state.detail_images_list = []
                st.rerun()

        monto_apuesta = st.number_input(
            "Monto a apostar ($ USD):",
            min_value=1.0,
            value=10.0,
            step=5.0,
            key="monto_f2",
            help="Monto simulado para calcular ganancias y riesgo"
        )

        instruccion_extra = st.text_area(
            "💡 Instrucción o nota adicional para el agente (Opcional):",
            placeholder="Ej: Ten en cuenta que el equipo local tiene 3 bajas en defensa, o prioriza hándicaps asiáticos...",
            key="extra_prompt_f2"
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

                        nota_usuario = f"\nNOTA EXTRA DEL USUARIO: {instruccion_extra}\n" if instruccion_extra else ""

                        audit_prompt = f"""
                        Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV) con memoria analítica.
                        El usuario va a auditar el siguiente partido: "{target_match}".
                        {resumen_historial}
                        {nota_usuario}
                        PARÁMETROS DE CONFIGURACIÓN:
                        - Impuesto SRI (Ecuador): {retencion}% sobre la ganancia neta.
                        - Probabilidad Mínima Exigida: {prob_min}%.
                        - Monto planificado para apostar: ${monto_apuesta:.2f} USD.
                        INSTRUCCIONES DE FORMATO Y CONTENIDO:
                        1. UTILIZA OBLIGATORIAMENTE Google Search para buscar noticias recientes, bajas y lesiones de este evento.
                        2. Analiza las capturas de mercados evaluando combinadas o alternativas y toma muy en cuenta la nota extra del usuario.
                        3. Genera el informe estructurado:
                           - 📌 **EVENTO Y MERCADOS EVALUADOS**
                           - 🧠 **ANÁLISIS DE APRENDIZAJE BASADO EN TU HISTORIAL**
                           - 🌐 **INVESTIGACIÓN Y NOTICIAS DE LA WEB (ÚLTIMO MINUTO)**
                           - 💰 **CÁLCULO FINANCIERO Y GANANCIA NETA (POST-SRI {retencion}%)**
                           - 💡 **VEREDICTO FINAL Y RECOMENDACIÓN DE STAKE (GESTIÓN DE RIESGO)**
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
                        st.error(f"Ocurrió un error en el escaneo/auditoría: {str(e)}")

    if st.session_state.audit_result:
        st.markdown("---")
        st.subheader("📊 Informe de Auditoría Quirúrgica")
        st.markdown(st.session_state.audit_result)

        st.markdown("---")
        st.subheader("☑️ Selección Modular de Apuesta (Directa y/o Combinada)")
        
        sel_directa = st.checkbox("✅ Registrar Opción Directa / Principal Aprobada", key="chk_dir_f2")
        sel_alt_1 = st.checkbox("🔀 Combinada / Alternativa 1", key="chk_alt1_f2")
        sel_alt_2 = st.checkbox("🔀 Combinada / Alternativa 2", key="chk_alt2_f2")
        sel_alt_3 = st.checkbox("🔀 Combinada / Alternativa 3", key="chk_alt3_f2")
        custom_mercado = st.text_input("Detalle o notas adicionales de tu selección:", placeholder="Ej: Doble Oportunidad + Más de 1.5 Goles", key="txt_custom_f2")

        mercados_seleccionados = []
        if sel_directa: mercados_seleccionados.append("Principal Aprobada")
        if sel_alt_1: mercados_seleccionados.append("Alternativa 1")
        if sel_alt_2: mercados_seleccionados.append("Alternativa 2")
        if sel_alt_3: mercados_seleccionados.append("Alternativa 3")
        if custom_mercado: mercados_seleccionados.append(custom_mercado)

        if len(mercados_seleccionados) > 1:
            tipo_jugada_str = "Combinada (Parley): " + " + ".join(mercados_seleccionados)
        elif len(mercados_seleccionados) == 1:
            tipo_jugada_str = f"Directa: {mercados_seleccionados[0]}"
        else:
            tipo_jugada_str = "Apuesta General"

        st.info(f"📌 **Estructura detectada para registro:** {tipo_jugada_str}")

        st.markdown("#### 🎫 Validación de Boleto y Re-chequeo de Cambios en Betano")
        st.caption("Sube tu boleto. Si el agente te recomienda un cambio, ajústalo en Betano, sube la nueva captura aquí y vuelve a validar hasta que quede perfecto.")
        
        boleto_file = st.file_uploader("Sube captura del boleto de apuesta:", type=["png", "jpg", "jpeg"], key="boleto_f2")
        
        if boleto_file:
            boleto_img = Image.open(boleto_file)
            st.image(boleto_img, caption="Boleto de Betano cargado", width=300)
            if st.button("🔍 Validar Boleto y Evaluar Cambios con Agente", key="val_bol_btn_f2"):
                with st.spinner("Analizando cuotas, riesgos y posibles mejoras..."):
                    try:
                        client_val = genai.Client(api_key=api_key)
                        val_resp = client_val.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[f"""
                            Eres un analista experto en gestión de riesgo y optimización de apuestas deportivas.
                            Analiza esta captura de boleto de Betano en relación con la jugada seleccionada ('{tipo_jugada_str}').
                            Por favor evalúa detalladamente y entrega:
                            1. 🔍 **Verificación de Cuotas y Retorno:** Confirma si la cuota total y el retorno son coherentes.
                            2. ⚠️ **Análisis de Riesgo y Sugerencia de Cambio:** Revisa si hay selecciones con alto riesgo. Si notas que falta o sobra algún mercado para asegurar rentabilidad, **recomienda un cambio analítico exacto**.
                            3. 💡 **Veredicto de Validación:** Indica claramente si el boleto está LISTO PARA APOSTAR o si requiere un ajuste adicional.
                            """, boleto_img]
                        )
                        st.success("✔ Auditoría Analítica del Boleto:")
                        st.markdown(val_resp.text)
                    except Exception as e:
                        st.error(f"Error al validar el boleto: {str(e)}")

        st.markdown("---")
        st.subheader("🏁 Cierre Post-Partido (Lectura Automática de Resultado)")
        resultado_file = st.file_uploader("Sube captura del resultado final del partido:", type=["png", "jpg", "jpeg"], key="resultado_f2")
        monto_apostado_final = st.number_input("Monto invertido en esta jugada ($):", value=monto_apuesta, key="monto_inv_f2")
        
        if resultado_file:
            res_img = Image.open(resultado_file)
            st.image(res_img, caption="Captura de resultado final", width=300)
            if st.button("🤖 Analizar Resultado y Registrar en Historial Automáticamente", key="auto_res_btn_f2"):
                with st.spinner("Leyendo resultado final y actualizando historial..."):
                    try:
                        client_res = genai.Client(api_key=api_key)
                        analisis_res = client_res.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[f"""
                            Analiza esta imagen de resultado final del partido '{target_match}' donde se apostó '{tipo_jugada_str}'.
                            Determina estrictamente si la apuesta fue 'Ganada', 'Perdida' o 'Nula'.
                            Responde en el formato exacto:
                            ESTADO: [Ganada / Perdida / Nula]
                            MOTIVO: [Breve explicación]
                            """, res_img]
                        )
                        texto_analisis = analisis_res.text
                        estado_detectado = "Perdida"
                        if "ESTADO: Ganada" in texto_analisis or "Ganada" in texto_analisis:
                            estado_detectado = "Ganada"
                        elif "ESTADO: Nula" in texto_analisis or "Nula" in texto_analisis:
                            estado_detectado = "Nula"
                            
                        nuevo_registro = {
                            "partido": target_match,
                            "mercado": tipo_jugada_str,
                            "resultado": estado_detectado,
                            "monto": monto_apostado_final
                        }
                        st.session_state.historial.append(nuevo_registro)
                        guardar_historial(st.session_state.historial)
                        st.success(f"✅ ¡Resultado procesado con éxito! Detectado como: **{estado_detectado}**.")
                        st.markdown(texto_analisis)
                    except Exception as e:
                        st.error(f"Error al procesar la imagen de resultado: {str(e)}")

        with st.expander("📝 Registrar resultado manualmente (Sin subir foto de resultado)"):
            with st.form("form_manual_f2"):
                res_manual = st.selectbox("Resultado real:", ["Ganada", "Perdida", "Nula"], key="rm_f2")
                sub_manual = st.form_submit_button("💾 Guardar Manualmente")
                if sub_manual:
                    reg_man = {
                        "partido": target_match,
                        "mercado": tipo_jugada_str,
                        "resultado": res_manual,
                        "monto": monto_apostado_final
                    }
                    st.session_state.historial.append(reg_man)
                    guardar_historial(st.session_state.historial)
                    st.success("✅ ¡Registrado manualmente con éxito!")
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
    st.markdown("¿Tienes un partido en mente? Sube directamente la captura del encuentro o mercado para auditarlo con búsqueda web, SRI y Stake.")

    direct_match_name = st.text_input("Nombre del partido (opcional):", placeholder="Ej: Barcelona SC vs LDU")
    
    direct_files = st.file_uploader(
        "Sube la captura de pantalla del partido o mercados:",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="uploader_modo_directo"
    )

    if direct_files:
        st.session_state.direct_images_list = []
        for file in direct_files:
            img = Image.open(file)
            st.session_state.direct_images_list.append(img)

    if st.session_state.direct_images_list:
        d_cols = st.columns(min(len(st.session_state.direct_images_list), 4))
        for idx, img in enumerate(st.session_state.direct_images_list):
            with d_cols[idx % 4]:
                st.image(img, use_container_width=True)

        if st.button("❌ Quitar Capturas Directas", key="clear_direct"):
            st.session_state.direct_images_list = []
            st.rerun()

    monto_directo = st.number_input(
        "Monto a apostar ($ USD):",
        min_value=1.0,
        value=10.0,
        step=5.0,
        key="monto_directo",
        help="Monto simulado para calcular ganancias y riesgo"
    )

    instruccion_extra_d = st.text_area(
        "💡 Instrucción o nota adicional para el agente (Opcional):",
        placeholder="Ej: Ten en cuenta bajas en defensa, o prioriza hándicaps...",
        key="extra_prompt_d"
    )

    if st.button("🚀 Auditar Partido Directo (Web Search + SRI + Stake)", type="primary"):
        if not st.session_state.direct_images_list:
            st.warning("⚠️ Sube al menos una captura del partido o mercado.")
        else:
            partido_ref = direct_match_name if direct_match_name else "Partido analizado por imagen"
            with st.spinner(f"Analizando partido, buscando en la web y evaluando Stake óptimo..."):
                try:
                    client = genai.Client(api_key=api_key)
                    resumen_historial = "Historial reciente del apostador:\n"
                    if st.session_state.historial:
                        for h in st.session_state.historial[-10:]:
                            resumen_historial += f"- Partido: {h['partido']} | Apuesta: {h['mercado']} | Resultado: {h['resultado']}\n"
                    else:
                        resumen_historial += "Aún no hay historial registrado.\n"

                    nota_usuario_d = f"\nNOTA EXTRA DEL USUARIO: {instruccion_extra_d}\n" if instruccion_extra_d else ""

                    direct_prompt = f"""
                    Eres un agente autónomo experto en auditoría de apuestas deportivas de alto valor (+EV) con memoria analítica.
                    El usuario va a auditar directamente un partido/mercado. Referencia: "{partido_ref}".
                    {resumen_historial}
                    {nota_usuario_d}
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
                       - 💡 **VEREDICTO FINAL Y RECOMENDACIÓN DE STAKE (GESTIÓN DE RIESGO)**
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
                    st.error(f"Ocurrió un error en la auditoría directa: {str(e)}")

    if st.session_state.direct_audit_result:
        st.markdown("---")
        st.subheader("📊 Informe de Auditoría Directa")
        st.markdown(st.session_state.direct_audit_result)

        st.markdown("---")
        st.subheader("☑️ Selección Modular de Apuesta (Directa y/o Combinada)")
        
        sel_directa_d = st.checkbox("✅ Registrar Opción Directa / Principal Aprobada", key="chk_dir_d")
        sel_alt_1_d = st.checkbox("🔀 Combinada / Alternativa 1", key="chk_alt1_d")
        sel_alt_2_d = st.checkbox("🔀 Combinada / Alternativa 2", key="chk_alt2_d")
        sel_alt_3_d = st.checkbox("🔀 Combinada / Alternativa 3", key="chk_alt3_d")
        custom_mercado_d = st.text_input("Detalle o notas adicionales de tu selección:", placeholder="Ej: Doble Oportunidad + Más de 1.5 Goles", key="txt_custom_d")

        mercados_seleccionados_d = []
        if sel_directa_d: mercados_seleccionados_d.append("Principal Aprobada")
        if sel_alt_1_d: mercados_seleccionados_d.append("Alternativa 1")
        if sel_alt_2_d: mercados_seleccionados_d.append("Alternativa 2")
        if sel_alt_3_d: mercados_seleccionados_d.append("Alternativa 3")
        if custom_mercado_d: mercados_seleccionados_d.append(custom_mercado_d)

        if len(mercados_seleccionados_d) > 1:
            tipo_jugada_str_d = "Combinada (Parley): " + " + ".join(mercados_seleccionados_d)
        elif len(mercados_seleccionados_d) == 1:
            tipo_jugada_str_d = f"Directa: {mercados_seleccionados_d[0]}"
        else:
            tipo_jugada_str_d = "Apuesta General"

        st.info(f"📌 **Estructura detectada para registro:** {tipo_jugada_str_d}")

        nombre_reg = direct_match_name if direct_match_name else "Partido Directo"

        st.markdown("#### 🎫 Validación de Boleto y Re-chequeo de Cambios en Betano")
        st.caption("Sube tu boleto. Si el agente te sugiere algún cambio, modifícalo en Betano, sube la nueva captura y vuelve a validar.")
        
        boleto_file_d = st.file_uploader("Sube captura del boleto de apuesta:", type=["png", "jpg", "jpeg"], key="boleto_d")
        
        if boleto_file_d:
            boleto_img_d = Image.open(boleto_file_d)
            st.image(boleto_img_d, caption="Boleto de Betano cargado", width=300)
            if st.button("🔍 Validar Boleto y Evaluar Cambios con Agente", key="val_bol_btn_d"):
                with st.spinner("Analizando cuotas, riesgos y posibles mejoras..."):
                    try:
                        client_val_d = genai.Client(api_key=api_key)
                        val_resp_d = client_val_d.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[f"""
                            Eres un analista experto en gestión de riesgo y optimización de apuestas deportivas.
                            Analiza esta captura de boleto de Betano en relación con la jugada seleccionada ('{tipo_jugada_str_d}').
                            Por favor evalúa detalladamente y entrega:
                            1. 🔍 **Verificación de Cuotas y Retorno:** Confirma si la cuota total y el retorno son coherentes.
                            2. ⚠️ **Análisis de Riesgo y Sugerencia de Cambio:** Revisa si hay selecciones con alto riesgo. Si notas que falta o sobra algún mercado para asegurar rentabilidad, **recomienda un cambio analítico exacto**.
                            3. 💡 **Veredicto de Validación:** Indica claramente si el boleto está LISTO PARA APOSTAR o si requiere un ajuste adicional.
                            """, boleto_img_d]
                        )
                        st.success("✔ Auditoría Analítica del Boleto:")
                        st.markdown(val_resp_d.text)
                    except Exception as e:
                        st.error(f"Error al validar el boleto: {str(e)}")

        st.markdown("---")
        st.subheader("🏁 Cierre Post-Partido (Lectura Automática de Resultado)")
        resultado_file_d = st.file_uploader("Sube captura del resultado final del partido:", type=["png", "jpg", "jpeg"], key="resultado_d")
        monto_apostado_final_d = st.number_input("Monto invertido en esta jugada ($):", value=monto_directo, key="monto_inv_d")
        
        if resultado_file_d:
            res_img_d = Image.open(resultado_file_d)
            st.image(res_img_d, caption="Captura de resultado final", width=300)
            if st.button("🤖 Analizar Resultado y Registrar en Historial Automáticamente", key="auto_res_btn_d"):
                with st.spinner("Leyendo resultado final y actualizando historial..."):
                    try:
                        client_res_d = genai.Client(api_key=api_key)
                        analisis_res_d = client_res_d.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[f"""
                            Analiza esta imagen de resultado final del partido '{nombre_reg}' donde se apostó '{tipo_jugada_str_d}'.
                            Determina estrictamente si la apuesta fue 'Ganada', 'Perdida' o 'Nula'.
                            Responde en el formato exacto:
                            ESTADO: [Ganada / Perdida / Nula]
                            MOTIVO: [Breve explicación]
                            """, res_img_d]
                        )
                        texto_analisis_d = analisis_res_d.text
                        estado_detectado_d = "Perdida"
                        if "ESTADO: Ganada" in texto_analisis_d or "Ganada" in texto_analisis_d:
                            estado_detectado_d = "Ganada"
                        elif "ESTADO: Nula" in texto_analisis_d or "Nula" in texto_analisis_d:
                            estado_detectado_d = "Nula"
                            
                        nuevo_registro_d = {
                            "partido": nombre_reg,
                            "mercado": tipo_jugada_str_d,
                            "resultado": estado_detectado_d,
                            "monto": monto_apostado_final_d
                        }
                        st.session_state.historial.append(nuevo_registro_d)
                        guardar_historial(st.session_state.historial)
                        st.success(f"✅ ¡Resultado procesado con éxito! Detectado como: **{estado_detectado_d}**.")
                        st.markdown(texto_analisis_d)
                    except Exception as e:
                        st.error(f"Error al procesar la imagen de resultado: {str(e)}")

        with st.expander("📝 Registrar resultado manualmente (Sin subir foto de resultado)"):
            with st.form("form_manual_d"):
                res_manual_d = st.selectbox("Resultado real:", ["Ganada", "Perdida", "Nula"], key="rm_d")
                sub_manual_d = st.form_submit_button("💾 Guardar Manualmente")
                if sub_manual_d:
                    reg_man_d = {
                        "partido": nombre_reg,
                        "mercado": tipo_jugada_str_d,
                        "resultado": res_manual_d,
                        "monto": monto_apostado_final_d
                    }
                    st.session_state.historial.append(reg_man_d)
                    guardar_historial(st.session_state.historial)
                    st.success("✅ ¡Registrado manualmente con éxito!")
                    st.rerun()

        if st.button("🔄 Descartar esta auditoría y probar otro partido", type="secondary"):
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
