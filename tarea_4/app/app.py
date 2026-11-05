"""Interfaz web del agente de investigación socioeconómica (Streamlit).

    uv run streamlit run app/app.py        # se abre en http://localhost:8604 (puerto fijado en .streamlit/config.toml)

Pestañas:
  💬 Preguntar al agente   chat con Claude Code (claude -p) con el MCP del BCRP y las skills de la ENAHO; muestra en vivo
                           cada herramienta y skill que usa. Requiere Claude Code instalado y con sesión iniciada.
  📈 Precios (BCRP)        series en vivo con las funciones del servidor MCP (serie, comparar_series)
  🏠 Pobreza (ENAHO)       indicadores ponderados y mapa por departamento desde las bases de limpiando-enaho
  🧪 Evaluación            resultados con y sin MCP/Skills
  📄 Informe               el informe final del agente
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp"))
import server as bcrp  # noqa: E402  (el mismo servidor MCP: sus herramientas son funciones de Python)

AZUL, NARANJA, AQUA, AMARILLO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
RAMPA = ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"]
FUENTE_ENAHO = "Fuente: INEI, ENAHO 2024 (módulos 34 y 02). Estimaciones ponderadas."
PERMITIDAS = ["mcp__bcrp", "Skill", "ToolSearch", "Read", "Glob", "Grep", "Bash(uv run:*)", "Bash(uv:*)",
              "Bash(python:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)"]
CONTEXTO = ("Eres el agente de investigación socioeconómica de este proyecto y respondes a un usuario desde una "
            "interfaz web. Responde en español, claro y breve (máximo ~12 líneas salvo que pidan más). Usa el servidor "
            "MCP bcrp para cualquier cifra del BCRP y las skills limpiando-enaho, graficando-enaho y mapeando-enaho "
            "para la ENAHO 2024; no calcules a mano ni cites de memoria. Cita el origen de cada cifra (código de serie y "
            "periodo, o archivo y columna). Si generas un gráfico o mapa, di su ruta. No modifiques archivos del proyecto "
            "salvo las salidas que generan las skills. Describe asociaciones, no causas.")

st.set_page_config(page_title="Agente socioeconómico · Perú", page_icon="🇵🇪", layout="wide")


def estilo(fig, alto=420):
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.15), font=dict(size=13))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zeroline=False)
    return fig


# ─────────────────────────────── datos ───────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def serie_df(codigo, desde, hasta):
    s = bcrp.serie(codigo, desde, hasta)
    d = pd.DataFrame(s["datos"])
    d["fecha"] = pd.to_datetime(d.periodo)
    return d, s["nombre"], s["fuente"]


@st.cache_data(ttl=3600, show_spinner=False)
def comparar(codigos, desde, hasta):
    return bcrp.comparar_series(codigos, desde, hasta)


@st.cache_data(show_spinner=False)
def bases(_marca):
    p = pd.read_parquet(RAIZ / "salidas" / "personas_2024.parquet")
    h = pd.read_parquet(RAIZ / "salidas" / "hogares_2024.parquet")
    h["peso"] = h.factor07 * h.mieperho
    return p, h


@st.cache_data(show_spinner=False)
def geojson():
    from importlib import util
    ruta = RAIZ / "datos" / "peru_departamental_simple.geojson"
    if not ruta.exists():
        spec = util.spec_from_file_location("mapear", RAIZ / ".claude/skills/mapeando-enaho/scripts/mapear.py")
        mapear = util.module_from_spec(spec)
        spec.loader.exec_module(mapear)
        mapear.geometrias()
    return json.loads(ruta.read_text(encoding="utf-8"))


def tasa(df, col, peso, var):
    escala = 1 if var == "gasto_alimentos_pct" else 100
    filas = [{"grupo": g, "valor": escala * np.average(d[var].astype(float), weights=d[peso]), "muestra": len(d)}
             for g, d in df.groupby(col, observed=True)]
    return pd.DataFrame(filas)


# ─────────────────────────────── agente ───────────────────────────────

def etiqueta_herramienta(c):
    nombre, entrada = c["name"], c.get("input", {})
    if nombre.startswith("mcp__bcrp__"):
        args = ", ".join(f"{v}" for v in entrada.values())[:90]
        return f"🔌 **MCP BCRP · `{nombre.removeprefix('mcp__bcrp__')}`** ({args})"
    if nombre == "Skill":
        return f"🧩 **Skill · `{entrada.get('skill')}`**"
    if nombre == "ReadMcpResourceTool":
        return f"📚 **Recurso MCP** `{entrada.get('uri')}`"
    if nombre == "Bash":
        cmd = entrada.get("command", "")
        script = re.search(r"skills/([\w-]+)/scripts/(\w+\.py)([^;&|]*)", cmd)
        if script:
            opciones = re.sub(r"\s*\d?>.*", "", script[3]).strip()[:40]
            return f"⚙️ Script de `{script[1]}`: `{script[2]}{' ' + opciones if opciones else ''}`"
        return f"⚙️ `{cmd[:90]}`"
    if nombre in ("Read", "Glob", "Grep"):
        return f"📄 {nombre} `{str(entrada.get('file_path') or entrada.get('pattern', ''))[-70:]}`"
    if nombre == "ToolSearch":
        return "🔎 Carga las herramientas del MCP"
    return f"🔧 {nombre}"


def preguntar(prompt, modelo, sesion, caja):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", modelo,
           "--mcp-config", str(RAIZ / ".mcp.json"), "--strict-mcp-config", "--max-turns", "40",
           "--append-system-prompt", CONTEXTO, "--allowedTools", *PERMITIDAS]
    if sesion:
        cmd += ["--resume", sesion]
    antes = {p: p.stat().st_mtime for p in [*RAIZ.glob("figuras/*.png"), *RAIZ.glob("mapas/*.png")]}
    pasos, final, t = [], {}, time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {"error": "No encontré el comando `claude`. Instala Claude Code e inicia sesión."}
    for linea in proc.stdout:
        if not linea.strip().startswith("{"):
            continue
        e = json.loads(linea)
        if e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use" and c["name"] != "StructuredOutput":
                    pasos.append(etiqueta_herramienta(c))
                    caja.write(pasos[-1])
                    caja.update(label=f"Trabajando… {len(pasos)} pasos · {time.time() - t:.0f} s")
        elif e.get("type") == "result":
            final = e
    proc.wait()
    nuevas = [p for p in [*RAIZ.glob("figuras/*.png"), *RAIZ.glob("mapas/*.png")]
              if p.stat().st_mtime > antes.get(p, 0) + 0.5]
    if not final:
        return {"error": (proc.stderr.read() or "Claude Code no devolvió respuesta.")[-800:], "pasos": pasos}
    return {"texto": final.get("result", ""), "pasos": pasos, "figuras": [str(p) for p in nuevas],
            "sesion": final.get("session_id"), "segundos": time.time() - t,
            "costo": final.get("total_cost_usd") or 0, "error": final.get("result") if final.get("is_error") else None}


def pestaña_agente(modelo):
    st.subheader("Pregúntale al agente")
    st.caption("El agente es Claude Code con el servidor MCP del BCRP y las skills de la ENAHO. Debajo de cada respuesta "
               "ves qué herramientas usó. Las cifras salen de las herramientas, no de la memoria del modelo.")
    if "chat" not in st.session_state:
        st.session_state.chat, st.session_state.sesion = [], None
    ejemplos = ["¿Cuánto más subieron los alimentos que el IPC total en Lima entre dic. 2019 y dic. 2024?",
                "¿Cuál fue la pobreza monetaria en Cusco en 2024?",
                "Haz un mapa del peso de los alimentos en el gasto por departamento",
                "¿Qué hogares quedaron más expuestos a la inflación de alimentos? Usa el BCRP y la ENAHO"]
    elegido = None
    if not st.session_state.chat:
        st.markdown("**Prueba con alguna de estas:**")
        for i, (col, ej) in enumerate(zip(st.columns(2) * 2, ejemplos)):
            if col.button(ej, key=f"ej{i}", width="stretch"):
                elegido = ej
    for m in st.session_state.chat:
        with st.chat_message(m["rol"]):
            st.markdown(m["texto"])
            for f in m.get("figuras", []):
                st.image(f)
            if m.get("pasos"):
                with st.expander(f"🔧 {len(m['pasos'])} herramientas usadas · {m.get('pie', '')}"):
                    st.markdown("\n\n".join(m["pasos"]))
    pregunta = st.chat_input("Escribe tu pregunta sobre precios (BCRP) o pobreza (ENAHO 2024)…") or elegido
    if pregunta:
        st.session_state.chat.append({"rol": "user", "texto": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            caja = st.status("El agente está trabajando…", expanded=True)
            r = preguntar(pregunta, modelo, st.session_state.sesion, caja)
            if r.get("error") and not r.get("texto"):
                caja.update(label="Error", state="error")
                texto = f"⚠️ {r['error']}"
            else:
                caja.update(label=f"Listo en {r['segundos']:.0f} s", state="complete", expanded=False)
                texto = r["texto"]
                st.session_state.sesion = r.get("sesion") or st.session_state.sesion
            st.markdown(texto)
            for f in r.get("figuras", []):
                st.image(f)
        st.session_state.chat.append({"rol": "assistant", "texto": texto, "pasos": r.get("pasos", []),
                                      "figuras": r.get("figuras", []),
                                      "pie": f"{r.get('segundos', 0):.0f} s · US$ {r.get('costo', 0):.2f}"})
        st.rerun()
    if st.session_state.chat and st.button("🗑️ Nueva conversación"):
        st.session_state.chat, st.session_state.sesion = [], None
        st.rerun()


# ─────────────────────────────── BCRP ───────────────────────────────

def pestaña_bcrp():
    st.subheader("Precios en Lima Metropolitana · BCRP en vivo")
    st.caption("Consulta la API del BCRP con las mismas funciones del servidor MCP (`serie` y `comparar_series`).")
    c1, c2, c3 = st.columns([2, 1, 1])
    tasas = {"PN01273PM": "IPC total", "PN09822PM": "Alimentos y bebidas", "PN09823PM": "Sin alimentos y bebidas"}
    elegidas = c1.multiselect("Inflación a 12 meses", list(tasas), default=["PN01273PM", "PN09822PM"],
                              format_func=lambda c: f"{tasas[c]} ({c})")
    desde = c2.text_input("Desde (AAAA-MM)", "2019-12")
    hasta = c3.text_input("Hasta (AAAA-MM)", "2024-12")
    try:
        with st.spinner("Consultando el BCRP…"):
            fig = go.Figure()
            for codigo, color in zip(elegidas, [AZUL, NARANJA, AQUA]):
                d, _, _ = serie_df(codigo, desde, hasta)
                fig.add_scatter(x=d.fecha, y=d.valor, name=f"{tasas[codigo]} ({codigo})", line=dict(color=color, width=2),
                                hovertemplate="%{x|%b %Y}: %{y:.2f} %<extra></extra>")
            estilo(fig).update_layout(title="Inflación a 12 meses (%)", yaxis_ticksuffix=" %")
            st.plotly_chart(fig, width="stretch")
            r = comparar("PN38705PM,PN39445PM,PN38706PM", desde, hasta)
    except Exception as e:
        st.error(f"El BCRP no respondió o el periodo no es válido: {e}")
        return
    st.markdown(f"**Cuánto subió cada índice entre {r['periodo_comun']['desde']} y {r['periodo_comun']['hasta']}** "
                "(herramienta propia `comparar_series`)")
    cols = st.columns(3)
    for col, s, nombre in zip(cols, r["series"], ["IPC total", "Alimentos y bebidas", "Sin alimentos y bebidas"]):
        col.metric(f"{nombre} ({s['codigo']})", f"{s['variacion_acumulada_pct']:.1f} %",
                   None if s["codigo"] == r["referencia"] else f"{s['brecha_vs_referencia_pp']:+.1f} pp vs IPC total",
                   delta_color="inverse")
    st.caption("Fuentes: " + " · ".join(r["fuentes"]))


# ─────────────────────────────── ENAHO ───────────────────────────────

def pestaña_enaho():
    st.subheader("Pobreza y peso de los alimentos · ENAHO 2024")
    if not (RAIZ / "salidas" / "hogares_2024.parquet").exists():
        st.warning("Todavía no existe la base procesada de la ENAHO.")
        if st.button("Preparar datos con la skill limpiando-enaho (descarga del INEI si faltan, ~1 min)"):
            with st.spinner("Limpiando y validando la ENAHO…"):
                out = subprocess.run(["uv", "run", ".claude/skills/limpiando-enaho/scripts/limpiar.py", "--descargar"],
                                     cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
            st.code(out.stdout[-1500:] or out.stderr[-1500:])
            st.cache_data.clear()
        return
    marca = (RAIZ / "salidas" / "hogares_2024.parquet").stat().st_mtime
    p, h = bases(marca)
    indicadores = {"pobre": "Pobreza monetaria (% de personas)", "pobre_extremo": "Pobreza extrema (% de personas)",
                   "gasto_alimentos_pct": "Peso de los alimentos en el gasto (%)"}
    cortes = {"Área": ("area", "h"), "Departamento": ("departamento", "h"), "Dominio": ("dominio_nombre", "h"),
              "Condición de pobreza": ("pobreza_nombre", "p"), "Sexo": ("sexo", "p"), "Grupo de edad": ("grupo_edad", "p")}
    c1, c2 = st.columns(2)
    var = c1.selectbox("Indicador", list(indicadores), format_func=indicadores.get)
    corte = c2.selectbox("Comparar por", list(cortes))
    col, base = cortes[corte]
    if corte == "Condición de pobreza" and var != "gasto_alimentos_pct":
        st.info("La pobreza por condición de pobreza es trivial (0 % o 100 %): elige el peso de los alimentos.")
        return
    df, peso = (h, "peso") if base == "h" else (p, "facpob07")
    t = tasa(df, col, peso, var)
    t = t.sort_values("grupo") if corte == "Grupo de edad" else t.sort_values("valor")
    nacional = (100 if var != "gasto_alimentos_pct" else 1) * np.average(df[var].astype(float), weights=df[peso])
    k1, k2, k3 = st.columns(3)
    k1.metric("Perú", f"{nacional:.1f} %")
    k2.metric(f"Más alto: {t.iloc[-1].grupo}", f"{t.valor.max():.1f} %")
    k3.metric(f"Más bajo: {t.iloc[0].grupo}", f"{t.valor.min():.1f} %")
    horizontal = len(t) > 6
    fig = px.bar(t, x="valor" if horizontal else "grupo", y="grupo" if horizontal else "valor",
                 orientation="h" if horizontal else "v", text=t.valor.map(lambda v: f"{v:.1f}"),
                 color_discrete_sequence=[AZUL], custom_data=["muestra"])
    plantilla = ("%{y}: %{x:.1f} %" if horizontal else "%{x}: %{y:.1f} %") + "<br>muestra: %{customdata[0]:,}<extra></extra>"
    fig.update_traces(hovertemplate=plantilla, textposition="outside", cliponaxis=False)
    linea = dict(line_dash="dot", line_color="gray", annotation_text=f"Perú {nacional:.1f}")
    if horizontal:   # (un if/else de una línea se mostraría dos veces: Streamlit dibuja toda expresión suelta)
        fig.add_vline(x=nacional, **linea)
    else:
        fig.add_hline(y=nacional, **linea)
    estilo(fig, 720 if horizontal else 420).update_layout(title=f"{indicadores[var]} por {corte.lower()}, 2024",
                                                          xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    ponderador = "factor07 × mieperho (método INEI)" if base == "h" else "facpob07 (residentes habituales)"
    st.caption(f"{FUENTE_ENAHO} Ponderador: {ponderador}.")

    st.markdown("#### Mapa por departamento")
    var_mapa = st.radio("Indicador del mapa", list(indicadores), format_func=indicadores.get, horizontal=True)
    m = tasa(h, "ccdd", "peso", var_mapa).rename(columns={"grupo": "ccdd"})
    m["departamento"] = m.ccdd.map(h.groupby("ccdd").departamento.first())
    mapa = px.choropleth(m, geojson=geojson(), locations="ccdd", featureidkey="properties.FIRST_IDDP", color="valor",
                         color_continuous_scale=RAMPA, range_color=(0, m.valor.max()), hover_name="departamento",
                         hover_data={"ccdd": False, "valor": ":.1f", "muestra": ":,"},
                         labels={"valor": "%", "muestra": "hogares en la muestra"})
    mapa.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    estilo(mapa, 620).update_layout(title=indicadores[var_mapa] + " · 25 departamentos (ubigeo[:2] = FIRST_IDDP)",
                                    coloraxis_colorbar=dict(title="%"))
    st.plotly_chart(mapa, width="stretch")
    st.caption(f"{FUENTE_ENAHO} Ponderador: factor07 × mieperho. Límites departamentales del repositorio del curso.")


# ─────────────────────────────── evaluación e informe ───────────────────────────────

def pestaña_evaluacion():
    st.subheader("¿Mejoran el MCP y las Skills las respuestas?")
    r = pd.read_csv(RAIZ / "evaluacion" / "resultados.csv")
    c1, c2 = st.columns(2)
    for col, modo, nombre in [(c1, "A_sin_mcp_skills", "Sin MCP ni Skills"), (c2, "B_con_mcp_skills", "Con MCP y Skills")]:
        d = r[r.modo == modo]
        col.metric(nombre, f"{(d.resultado == 'acierta').sum()}/10 correctas")
        col.caption(f"{(d.resultado == 'no sabe').sum()} sin respuesta · {d.segundos.mean():.0f} s promedio por pregunta")
    tabla = r.pivot(index="id", columns="modo", values="resultado")
    tabla.insert(0, "esperado", r.drop_duplicates("id").set_index("id").respuesta_esperada)
    st.dataframe(tabla, width="stretch")
    with st.expander("Detalle: respuesta, fuente y herramientas de cada pregunta"):
        st.dataframe(r[["id", "modo", "respuesta_generada", "respuesta_generada_2", "categoria_generada", "resultado",
                        "herramientas_usadas", "fuente_utilizada", "segundos"]], width="stretch")
    analisis = (RAIZ / "evaluacion" / "comparacion.md").read_text(encoding="utf-8")
    for seccion in ("## Cómo llegamos al diseño final", "## Conclusión"):
        if seccion in analisis:
            st.markdown(seccion + analisis.split(seccion, 1)[1].split("\n## ", 1)[0])
    st.caption("Análisis completo: evaluacion/comparacion.md")


def pestaña_informe():
    texto = (RAIZ / "informes" / "informe_final.md").read_text(encoding="utf-8")
    for trozo in re.split(r"(!\[[^\]]*\]\([^)]+\))", texto):
        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", trozo)
        if img:
            st.image(str((RAIZ / "informes" / img[2]).resolve()), caption=img[1])
        elif trozo.strip():
            st.markdown(trozo)


# ─────────────────────────────── página ───────────────────────────────

with st.sidebar:
    st.markdown("## 🇵🇪 Agente socioeconómico")
    st.markdown("Precios de los alimentos (**BCRP**) y pobreza de los hogares (**ENAHO 2024**, INEI), con un servidor "
                "MCP y tres skills de Claude Code.")
    modelo = st.selectbox("Modelo del agente", ["sonnet", "haiku", "opus"],
                          help="Sonnet: buen equilibrio. Haiku: más rápido y barato. Opus: el más capaz.")
    st.divider()
    base_ok = (RAIZ / "salidas" / "hogares_2024.parquet").exists()
    st.markdown(f"{'✅' if base_ok else '⚠️'} Base ENAHO procesada")
    st.markdown("✅ Servidor MCP: `buscar_series`, `serie`, `resumen`, `transformar`, `comparar_series`, `grafico`")
    st.markdown("✅ Skills: `limpiando-enaho`, `graficando-enaho`, `mapeando-enaho`")
    st.divider()
    st.caption("Tarea 4 · Python Intermedio · QLab PUCP")

st.title("Precios de los alimentos y pobreza en el Perú")
st.markdown("¿Cuánto subieron los alimentos frente al resto de la canasta entre 2020 y 2024, y qué hogares estaban más "
            "expuestos por el peso de la comida en su gasto?")
tabs = st.tabs(["💬 Preguntar al agente", "📈 Precios (BCRP)", "🏠 Pobreza (ENAHO)", "🧪 Evaluación", "📄 Informe"])
with tabs[0]:
    pestaña_agente(modelo)
with tabs[1]:
    pestaña_bcrp()
with tabs[2]:
    pestaña_enaho()
with tabs[3]:
    pestaña_evaluacion()
with tabs[4]:
    pestaña_informe()
