import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import os
import json
import re
from collections import Counter
import pandas as pd

# Configuración inicial de la página
st.set_page_config(
    page_title="Value Radar - Auditor de Apuestas Pro",
    page_icon="⚽",
    layout="wide"
)

# Archivo local para persistir el historial de apuestas
HISTORY_FILE = "historial_apuestas.json"

def cargar_historial():
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

def calcular_metricas_avanzadas(historial):
    """Calcula ROI, Curva de Bankroll, Rachas y Métricas por Categoría con Python."""
    if not historial:
        return None, "Aún no hay historial suficiente para métricas avanzadas."
    
    total_inversion = 0.0
    ganancia_neta_total = 0.0
    balance_acumulado = []
    
    cat_stats = {}
    racha_actual = 0  
    max_racha_ganadora = 0
    max_racha_perdedora = 0
    temp_g = 0
    temp_p = 0
    
    for idx, h in enumerate(historial):
        monto = float(h.get("monto", 0.0))
        res = h.get("resultado", "")
        cat = h.get("categoria", "BetBuilder Mixto")
        
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "ganadas": 0, "perdidas": 0, "inversion": 0.0}
        
        cat_stats[cat]["total"] += 1
        cat_stats[cat]["inversion"] += monto
        total_inversion += monto
        
        if res == "Ganada":
            ganancia_neta = monto * 0.85 
            ganancia_neta_total += ganancia_neta
            cat_stats[cat]["ganadas"] += 1
            
            temp_g += 1
            temp_p = 0
            if temp_g > max_racha_ganadora: max_racha_ganadora = temp_g
            racha_actual = temp_g if racha_actual >= 0 else 1

        elif res == "Perdida":
            ganancia_neta = -monto
            ganancia_neta_total += ganancia_neta
            cat_stats[cat]["perdidas"] += 1
            
            temp_p += 1
            temp_g = 0
            if temp_p > max_racha_perdedora: max_racha_perdedora = temp_p
            racha_actual = -temp_p if racha_actual <= 0 else -1

        else: 
            ganancia_neta = 0.0
        
        balance_acumulado.append({
            "Apuesta #": idx + 1,
            "Balance Acumulado ($)": round(ganancia_neta_total, 2),
            "Partido": h.get("partido", "")
        })

    roi = (ganancia_neta_total / total_inversion * 100) if total_inversion > 0 else 0.0
    
    resumen_txt = f"""
    📊 RESUMEN CUANTITATIVO (PYTHON):
    - Inversión Total: ${total_inversion:.2f} USD \vert{} Ganancia Neta:${ganancia_neta_total:.2f} USD
    - ROI: {roi:.2f}% | Racha: {'🟢 ' + str(racha_actual) + ' G' if racha_actual > 0 else '🔴 ' + str(abs(racha_actual)) + ' P'}
    """
    for cat, d in cat_stats.items():
        wr = (d['ganadas'] / d['total'] * 100) if d['total'] > 0 else 0.0
        resumen_txt += f"  * [{cat}] -> Winrate: {wr:.1f}% ({d['ganadas']}G / {d['perdidas']}P)\n"

    df_bankroll = pd.DataFrame(balance_acumulado)
    
    return {
        "roi": roi,
        "total_inversion": total_inversion,
        "ganancia_neta": ganancia_neta_total,
        "racha_actual": racha_actual,
        "df_bankroll": df_bankroll,
        "resumen_txt": resumen_txt
    }, resumen_txt

# ---------------------------------------------------------
# CONTROL DE ACCESO
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

# Inicialización robusta del historial
if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()
else:
    disk_history = cargar_historial()
    if len(disk_history) > len(st.session_state.historial):
        st.session_state.historial = disk_history

# Inicializar estados de sesión
for key in ["images_list", "scan_result", "detected_matches", "detail_images_list", "audit_result", "direct_images_list", "direct_audit_result"]:
    if key not in st.session_state:
        st.session_state[key] = [] if "list" in key or "matches" in key else None

# Encabezado principal
st.title("⚽ Value Radar: Panel de Decisión Rápida")
st.markdown("Sistema inteligente: **1)** Radar de Oportunidades. **2)** Auditoría Clara y Sin Rodeos. **3)** Control Financiero.")

# ---------------------------------------------------------
# BARRA LATERAL
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if api_key:
        st.success("✔ API Key Lista")
    else:
        st.error("❌ Falta GEMINI_API_KEY en Secrets.")

    st.markdown("---")
    retencion = st.number_input("Retención SRI (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0)
    prob_min = st.number_input("Probabilidad Mínima (%)", min_value=0.0, max_value=100.0, value=85.0, step=1.0)
    
    st.markdown("---")
    st.subheader("📊 Rendimiento")
    metrics_data, resumen_mat = calcular_metricas_avanzadas(st.session_state.historial)
    total_apuestas = len(st.session_state.historial)
    ganadas = sum(1 for h in st.session_state.historial if h["resultado"] == "Ganada")
    perdidas = sum(1 for h in st.session_state.historial if h["resultado"] == "Perdida")
    winrate = (ganadas / total_apuestas * 100) if total_apuestas > 0 else 0.0
    
    st.metric("Total Registradas", total_apuestas)
    st.metric("Efectividad", f"{winrate:.1f}%", f"🟢 {ganadas} / 🔴 {perdidas}")
    
    if metrics_data:
        st.metric("ROI Estimado", f"{metrics_data['roi']:.2f}%", f"${metrics_data['ganancia_neta']:.2f} Netos")
        r_actual = metrics_data['racha_actual']
        if r_actual < 0:
            st.error(f"⚠️ Racha Perdedora: {abs(r_actual)}")
        elif r_actual > 0:
            st.success(f"🔥 Racha Ganadora: {r_actual}")

    st.markdown("---")
    st.subheader("💾 Respaldo")
    if st.session_state.historial:
        st.download_button("📥 Descargar JSON", data=json.dumps(st.session_state.historial, ensure_ascii=False, indent=4), file_name="historial_apuestas.json", mime="application/json")

    uploaded_backup = st.file_uploader("📂 Cargar JSON", type=["json"])
    if uploaded_backup:
        try:
            backup_data = json.load(uploaded_backup)
            if isinstance(backup_data, list):
                st.session_state.historial = backup_data
                guardar_historial(st.session_state.historial)
                st.success("✅ Historial restaurado con éxito!")
                st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")

    st.markdown("---")
    st.subheader("📥 Sincronizar Betano")
    historial_global_file = st.file_uploader("Captura historial Betano:", type=["png", "jpg", "jpeg"], key="historial_global_upload")
    if historial_global_file:
        hist_img = Image.open(historial_global_file)
        st.image(hist_img, caption="Historial cargado", use_container_width=True)
        if st.button("🤖 Procesar e Integrar"):
            if api_key:
                with st.spinner("Procesando..."):
                    try:
                        client_h = genai.Client(api_key=api_key)
                        prompt_h = """
                        Analiza esta captura del historial de Betano. Extrae cada apuesta:
                        - "partido", "tipo_apuesta", "mercado", "desglose_selecciones" (lista de {"seleccion": "...", "estado": "Ganada/Perdida"}), "categoria", "resultado" ('Ganada', 'Perdida', 'Nula', 'Cash Out'), "monto" (float).
                        Devuelve estrictamente un JSON array válido. Sin texto extra.
                        """
                        res_h = client_h.models.generate_content(model='gemini-3.8-flash', contents=[prompt_h, hist_img])
                        texto_json = res_h.text.strip().split("```json")[-1].split("```")[0].strip()
                        nuevos_registros = json.loads(texto_json)
                        if isinstance(nuevos_registros, list):
                            st.session_state.historial.extend(nuevos_registros)
                            guardar_historial(st.session_state.historial)
                            st.success(f"✅ {len(nuevos_registros)} apuestas agregadas!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

# Gráfica Bankroll
if metrics_data and not metrics_data["df_bankroll"].empty:
    with st.expander("📈 Ver Evolución de Capital"):
        st.line_chart(metrics_data["df_bankroll"], x="Apuesta #", y="Balance Acumulado ($)")

# ---------------------------------------------------------
# MODO DE OPERACIÓN
# ---------------------------------------------------------
st.markdown("---")
modo_operacion = st.radio("Modo de trabajo:", ["🎯 Modo Radar: Escanear cartelera", "⚡ Modo Directo: Auditar partido específico"], horizontal=True)

# ---------------------------------------------------------
# MODO 1: RADAR
# ---------------------------------------------------------
if modo_operacion == "🎯 Modo Radar: Escanear cartelera":
    st.subheader("Fase 1: Radar de Oportunidades")
    uploaded_files = st.file_uploader("Sube captura de cartelera:", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="uploader_fase1")

    if uploaded_files:
        st.session_state.images_list = [Image.open(f) for f in uploaded_files]

    if st.session_state.images_list:
        cols = st.columns(min(len(st.session_state.images_list), 4))
        for idx, img in enumerate(st.session_state.images_list):
            with cols[idx % 4]:
                st.image(img, use_container_width=True)

        if st.button("🗑️ Limpiar Radar"):
            st.session_state.images_list = []
            st.session_state.scan_result = None
            st.session_state.detected_matches = []
            st.rerun()

        if st.button("🎯 Escanear Oportunidades +EV", type="primary"):
            if api_key:
                with st.spinner("Escaneando el mercado..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        scan_prompt = """
                        Analiza la cartelera de partidos y detecta 5 o 6 mejores oportunidades con valor (+EV).
                        Usa estrictamente este formato limpio, visual y directo para cada oportunidad (sin lenguaje técnico enredado):

                        ### 1. [Nombre del Partido]
                        - ⚽ **Mercado Recomendado:** ...
                        - 📊 **Cuota:** ... | **Probabilidad Estimada:** ...% (Implícita: ...%)
                        - 💡 **Por qué hay valor:** (Explica en 1 sola frase sencilla)

                        (Repite para cada partido)

                        Al final, incluye obligatoriamente una línea exacta con:
                        LISTA_PARTIDOS: Partido 1, Partido 2, Partido 3
                        """
                        response = client.models.generate_content(model='gemini-3.8-flash', contents=[scan_prompt] + st.session_state.images_list)
                        st.session_state.scan_result = response.text
                        
                        if "LISTA_PARTIDOS:" in response.text:
                            raw_line = response.text.split("LISTA_PARTIDOS:")[1].strip().split("\n")[0]
                            parts = [p.strip(" *-•") for p in raw_line.split(",") if p.strip()]
                            st.session_state.detected_matches = parts if parts else ["Manual"]
                        else:
                            st.session_state.detected_matches = ["Manual"]
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    if st.session_state.scan_result:
        st.markdown("---")
        st.subheader("🎯 Panel de Oportunidades Detectadas")
        st.markdown(st.session_state.scan_result)

        st.markdown("---")
        st.subheader("Fase 2: Auditoría Quirúrgica")
        options = st.session_state.detected_matches + ["Otro (Escribir manualmente)"]
        selected_option = st.selectbox("Elige el partido a auditar:", options)
        target_match = st.text_input("Nombre del partido:") if selected_option == "Otro (Escribir manualmente)" else selected_option

        detail_files = st.file_uploader("Capturas de mercados específicos (Opcional):", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="uploader_fase2")
        if detail_files:
            st.session_state.detail_images_list = [Image.open(f) for f in detail_files]

        monto_apuesta = st.number_input("Monto a apostar ($):", min_value=1.0, value=10.0, step=5.0)
        instruccion_extra = st.text_area("💡 Nota adicional (Opcional):", placeholder="Ej: Considera que hay bajas...")

        if st.button("🚀 Auditar Decisión (Panel Rápido)", type="primary"):
            if not target_match:
                st.warning("Selecciona un partido.")
            else:
                with st.spinner("Analizando con IA y Web..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        audit_prompt = f"""
                        Eres un experto en apuestas. Audita el partido: "{target_match}".
                        {resumen_mat}
                        - Impuesto SRI: {retencion}% | Monto: ${monto_apuesta:.2f}
                        
                        Usa estrictamente este formato de Panel de Decisión Rápida (sin lenguaje técnico complejo):

                        ### 🚦 Veredicto: [🟢 APTO / 🟡 RIESGOSO / 🔴 EVITAR]
                        - **Partido:** {target_match}
                        - **Mercado Evaluado:** [Indicar mercado]
                        - **Cuota:** [...]

                        ### 💡 ¿Por qué tomar esta decisión?
                        - **Bajas / Claves Web:** [Dato clave en 1 línea]
                        - **Historial del usuario:** [Advertencia basada en sus categorías previas]

                        ### 💰 Cuentas Claras (Post-SRI {retencion}%)
                        - **Inversión:** ${monto_apuesta:.2f} - **Ganancia Neta Estimada:**$[...]
                        - **Stake Recomendado:** [Ej: Bajo / Moderado / Alto]

                        ### 🔀 Alternativa más segura
                        - [Sugerencia rápida si aplica]
                        """
                        res = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[audit_prompt] + st.session_state.detail_images_list,
                            config=types.GenerateContentConfig(tools=[{"google_search": {}}])
                        )
                        st.session_state.audit_result = res.text
                    except Exception as e:
                        st.error(f"Error: {str¡Totalmente de acuerdo! Cuando estás frente a la pantalla evaluando una cartelera o a punto de confirmar un boleto en Betano, lo que menos necesitas es leer párrafos largos o explicaciones llenas de jerga técnica que te hagan dudar. 

Para solucionar la variabilidad en los reportes y hacerlos ultra-rápidos de digerir, la mejor estrategia es implementar una **"Plantilla Maestra de Decisión"**. Esto obligará al agente a usar siempre el mismo formato estructurado, priorizando un sistema de **semáforo visual** y datos directos al grano.

---

### 📋 El Formato Óptimo Recomendado (Estructura Estándar)

Cada vez que el agente te entregue un resultado (en el Radar, Auditoría Directa o Validación de Boleto), usará estrictamente esta estructura visual:

#### **🚦 1. Veredicto Directo (Lo primero que debes leer)**
* **Estado:** `🟢 APTO PARA APOSTAR` | `🟡 RIESGO MODERADO (AJUSTAR)` | `🔴 EVITAR / TRAMPA DE CASA`
* **Acción sugerida:** Una frase de una sola línea indicando qué hacer (ej. *"Apuesta simple recomendada"* o *"Demasiadas selecciones, recorta los córners"*).

#### **🎯 2. Resumen de la Jugada**
* **Partido:** [Ej. Inter de Milán vs Como]
* **Mercado:** [Ej. Victoria de Inter de Milán]
* **Cuota:** `2.07` | **Probabilidad Estimada:** `58%` (vs `48%` implícita de la casa $\rightarrow$ **+EV Positivo**)

#### **🔍 3. ¿Por qué sí o por qué no? (En cristiano)**
* Explicación libre de tecnicismos en 2 viñetas sencillas (ej. *"El Inter es sólido de local y el Como tiene 2 bajas clave en defensa"*, o *"Cuidado: el historial muestra que fallas mucho en este tipo de combinadas"*).

#### **💰 4. Gestión del Dinero (Stake)**
* **Monto sugerido:** `$` [Cantidad exacta basada en tu bankroll]
* **Advertencia de racha:** [Si estás en racha perdedora, el agente te dirá aquí: *"Usa la mitad de tu stake habitual por disciplina"*].

#### **✂️ 5. Plan B / Ajuste del Boleto**
* Si estás validando un boleto que tiene mucho riesgo, aquí te indicará exactamente qué borrar (ej. *"Borra la selección de córners y deja solo la doble oportunidad"*).

---

### 🛠️ ¿Cómo lo aplicamos en el código?

Con este formato estandarizado, ya no tendrás que adivinar dónde están los números importantes; tu vista irá directo a los colores del semáforo, la probabilidad y el veredicto en menos de 5 segundos.

¿Te parece bien si actualizamos los *prompts* internos del código en la próxima revisión para que el agente imprima **siempre** los resultados bajo esta plantilla visual y amigable?
