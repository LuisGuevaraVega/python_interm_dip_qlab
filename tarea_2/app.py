"""Tarea 2 · Parte 3: dashboard de los documentos y audios procesados.

Solo lee los CSV que generan los notebooks (no corre OCR, ASR ni LLM en vivo):

    streamlit run app.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "datos"
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#52514e"
COLOR_TIPO = {"impreso": AZUL, "foto": NARANJA, "manuscrito": GRIS}
OCR_BASE, OCR_ALT = "PaddleOCR", "EasyOCR"
ASR_BASE, ASR_ALT = "faster-whisper small", "Qwen3-ASR 0.6B"
COLOR_MODELO = {OCR_BASE: AZUL, OCR_ALT: NARANJA, ASR_BASE: AZUL, ASR_ALT: NARANJA}

st.set_page_config(page_title="Voces y documentos peruanos", page_icon="📜", layout="wide")


# ───────────────────────────────────────────────────────── datos
@st.cache_data
def cargar():
    docs = pd.read_csv(DATOS / "documentos.csv")
    clips = pd.read_csv(DATOS / "transcripciones.csv")
    fuentes = pd.read_csv(DATOS / "fuentes.csv")
    llm = pd.read_csv(DATOS / "extraccion_llm.csv")
    metricas = pd.read_csv(DATOS / "metricas.csv")
    corpus = pd.read_csv(DATOS / "metricas_corpus.csv")
    alternativos = pd.read_csv(DATOS / "modelos_alternativos.csv")
    auditoria = pd.read_csv(DATOS / "auditoria_llm.csv")
    ejemplos = pd.read_csv(DATOS / "ejemplos" / "ejemplos.csv")

    # todos los textos en formato largo: un registro por (archivo, modelo)
    alternativos["modelo_corto"] = alternativos.modalidad.map({"documento": OCR_ALT, "audio": ASR_ALT})
    textos = pd.concat([
        docs.assign(modalidad="documento", modelo_corto=OCR_BASE, texto=docs.texto_ocr)[["id", "modalidad", "modelo_corto", "texto"]],
        clips.assign(modalidad="audio", modelo_corto=ASR_BASE, texto=clips.texto_asr)[["id", "modalidad", "modelo_corto", "texto"]],
        alternativos[["id", "modalidad", "modelo_corto", "texto"]],
    ], ignore_index=True).rename(columns={"modelo_corto": "modelo"})
    meta = pd.concat([
        docs[["id", "tipo", "descripcion"]].assign(duracion_seg=float("nan")),
        clips[["id", "descripcion", "duracion_seg"]].assign(tipo="audio"),
    ])
    textos = textos.merge(meta, on="id", how="left").merge(fuentes[["id", "licencia"]], on="id", how="left")
    llm["campos"] = llm.campos_json.map(json.loads)
    return docs, clips, fuentes, llm, metricas, corpus, alternativos, auditoria, ejemplos, textos


docs, clips, fuentes, llm, metricas, corpus, alternativos, auditoria, ejemplos, textos = cargar()
PUBLICABLES = dict(zip(ejemplos.id, ejemplos.archivo))
CAMPOS_LLM = dict(zip(llm.id, llm.campos))
valor_corpus = lambda m: corpus.set_index("modelo").loc[m, "valor (corpus)"]


def fragmento(texto: str, consulta: str, ancho: int = 70) -> str:
    """El trozo de texto alrededor de la primera coincidencia, para la tabla de resultados."""
    texto = re.sub(r"\s+", " ", str(texto))
    if not consulta:
        return texto[:2 * ancho] + ("…" if len(texto) > 2 * ancho else "")
    m = re.search(re.escape(consulta), texto, re.IGNORECASE)
    if not m:
        return ""
    a, b = max(0, m.start() - ancho), min(len(texto), m.end() + ancho)
    return ("…" if a else "") + texto[a:m.start()] + "**" + m.group() + "**" + texto[m.end():b] + ("…" if b < len(texto) else "")


def tabla_campos(id_: str) -> pd.DataFrame:
    campos = CAMPOS_LLM.get(id_, {})
    filas = []
    for k, v in campos.items():
        if isinstance(v, list):
            v = " · ".join(f"“{x}”" for x in v)
        filas.append({"campo": k, "valor": "null" if v is None else str(v)})
    return pd.DataFrame(filas)


# ───────────────────────────────────────────────────────── barra lateral: búsqueda y filtros
with st.sidebar:
    st.header("Buscar y filtrar")
    consulta = st.text_input("Palabra o frase en los textos OCR y ASR", placeholder="Ej.: Lima, fiesta, Palma")
    tipos = st.multiselect("Tipo de documento", ["impreso", "foto", "manuscrito"], default=["impreso", "foto", "manuscrito"])
    modelo_ocr = st.radio("Modelo OCR", [OCR_BASE, OCR_ALT], horizontal=True,
                          help="PaddleOCR procesó los 25 documentos; EasyOCR también, como modelo alternativo.")
    modelo_asr = st.radio("Modelo ASR", [ASR_BASE, ASR_ALT], horizontal=True,
                          help="Qwen3-ASR solo se corrió sobre los 10 clips de evaluación y el clip con música (clip_014).")
    condiciones = sorted(clips.descripcion.unique())
    cond_sel = st.multiselect("Condición de grabación", condiciones, default=condiciones)
    dur_min, dur_max = float(clips.duracion_seg.min()), float(clips.duracion_seg.max())
    rango = st.slider("Duración del clip (s)", dur_min, dur_max, (dur_min, dur_max), step=1.0)
    st.caption("Todos los textos están seudonimizados: los nombres de personas privadas aparecen como [ENTREVISTADA_1], [PERSONA_1], etc.")

# filtros aplicados a la vista larga de textos
vista = textos[
    ((textos.modalidad == "documento") & textos.tipo.isin(tipos) & (textos.modelo == modelo_ocr))
    | ((textos.modalidad == "audio") & textos.descripcion.isin(cond_sel) & (textos.modelo == modelo_asr)
       & textos.duracion_seg.between(*rango))
].copy()
if consulta:
    vista = vista[vista.texto.str.contains(re.escape(consulta), case=False, na=False)]
vista["coincidencias"] = vista.texto.str.count(re.escape(consulta), flags=re.IGNORECASE) if consulta else 0
docs_f = docs[docs.id.isin(vista.id)]
clips_f = clips[clips.id.isin(vista.id)]

# ───────────────────────────────────────────────────────── encabezado e indicadores
st.title("¿Podemos convertir documentos escaneados y entrevistas en audio en un archivo de texto buscable?")
st.markdown(
    "Un pipeline de IA sobre **25 documentos peruanos** (impresos, fotos de celular y manuscritos de los siglos XIX al XXI) "
    "y **23 clips de audio** en español peruano (entrevistas en la calle, marchas, fiestas patronales y lecturas), todos de "
    "Wikimedia Commons con licencia libre. **OCR** con PaddleOCR, **ASR** con faster-whisper + VAD + diarización, "
    "**seudonimización** de personas privadas y **extracción de campos** con Gemini. Cada modelo se comparó con una "
    "alternativa (EasyOCR, Qwen3-ASR) sobre 10 documentos y 10 clips transcritos a mano por el autor.")

correctas = int(auditoria.completa.sum())
k = st.columns(5)
k[0].metric("Documentos procesados", f"{len(docs)}", help="8 impresos, 8 fotos y 9 manuscritos")
k[1].metric("Minutos de audio transcritos", f"{clips.duracion_seg.sum() / 60:.1f}", help=f"{len(clips)} clips")
k[2].metric(f"CER {OCR_BASE}", f"{valor_corpus(OCR_BASE):.3f}",
            delta=f"{valor_corpus(OCR_BASE) - valor_corpus(OCR_ALT):+.3f} vs {OCR_ALT}", delta_color="inverse",
            help="Tasa de error por carácter sobre los 10 documentos de evaluación (menor es mejor)")
k[3].metric(f"WER {ASR_BASE}", f"{valor_corpus(ASR_BASE):.3f}",
            delta=f"{valor_corpus(ASR_BASE) - valor_corpus(ASR_ALT):+.3f} vs Qwen3-ASR", delta_color="inverse",
            help="Tasa de error por palabra sobre los 10 clips de evaluación (menor es mejor)")
k[4].metric("Concordancia LLM vs. auditoría humana", f"{correctas / len(auditoria):.0%}",
            help=f"{correctas} de {len(auditoria)} extracciones completamente correctas según la revisión manual")

tab_buscar, tab_docs, tab_audio, tab_eval, tab_fuentes = st.tabs(
    ["Búsqueda", "Explorador de documentos", "Explorador de audios", "Evaluación de modelos", "Fuentes y método"])

# ───────────────────────────────────────────────────────── búsqueda
with tab_buscar:
    n_doc, n_aud = (vista.modalidad == "documento").sum(), (vista.modalidad == "audio").sum()
    st.subheader(f"{len(vista)} registros" + (f" contienen «{consulta}»" if consulta else " con los filtros actuales"))
    st.caption(f"{n_doc} documentos ({modelo_ocr}) · {n_aud} clips ({modelo_asr})")
    c1, c2 = st.columns(2)
    por_grupo = (vista.assign(grupo=vista.tipo.where(vista.modalidad == "documento", vista.descripcion))
                 .groupby(["modalidad", "grupo"]).agg(registros=("id", "size"), coincidencias=("coincidencias", "sum")).reset_index())
    with c1:
        y = "coincidencias" if consulta else "registros"
        fig = px.bar(por_grupo.sort_values(y), x=y, y="grupo", color="modalidad", orientation="h",
                     color_discrete_map={"documento": AZUL, "audio": NARANJA},
                     title=f"Dónde aparece «{consulta}»" if consulta else "Registros por tipo de documento y condición de grabación",
                     labels={"grupo": "", y: y.capitalize()})
        fig.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with c2:
        largo = vista.assign(largo=vista.texto.str.len())
        fig = px.histogram(largo, x="largo", color="modalidad", nbins=20, barmode="overlay",
                           color_discrete_map={"documento": AZUL, "audio": NARANJA},
                           title="Longitud de los textos filtrados: los manuscritos y clips cortos dan menos texto",
                           labels={"largo": "Caracteres", "count": "Registros"})
        fig.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")

    resultados = vista.assign(fragmento=[fragmento(t, consulta) for t in vista.texto])
    resultados["tipo o condición"] = resultados.tipo.where(resultados.modalidad == "documento", resultados.descripcion)
    columnas = ["id", "modalidad", "tipo o condición", "modelo", "coincidencias", "fragmento", "licencia"]
    st.dataframe(resultados[columnas], width="stretch", hide_index=True,
                 column_config={"fragmento": st.column_config.TextColumn("fragmento", width="large")})
    st.download_button("Descargar resultados (CSV)", resultados[columnas[:-2] + ["texto", "licencia"]].to_csv(index=False).encode("utf-8"),
                       file_name="resultados_busqueda.csv", mime="text/csv",
                       help="Textos revisados y seudonimizados, con el modelo que los produjo")

# ───────────────────────────────────────────────────────── documentos
with tab_docs:
    c1, c2 = st.columns([1, 2])
    with c1:
        por_tipo = docs_f.groupby("tipo").agg(documentos=("id", "size"), confianza=("confianza_media", "mean")).reset_index()
        fig = px.bar(por_tipo, x="tipo", y="documentos", color="tipo", color_discrete_map=COLOR_TIPO,
                     text=por_tipo.confianza.map(lambda c: f"confianza {c:.2f}"),
                     title="El OCR duda en los manuscritos", labels={"tipo": "", "documentos": "Documentos"})
        fig.update_layout(showlegend=False, height=330, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with c2:
        opciones = docs_f.id.tolist() or docs.id.tolist()
        etiqueta = dict(zip(docs.id, docs.id + " · " + docs.tipo + " · " + docs.descripcion))
        doc_id = st.selectbox("Documento", opciones, format_func=etiqueta.get)
        d = docs.set_index("id").loc[doc_id]
        f = fuentes.set_index("id").loc[doc_id]
        st.markdown(f"**{d.descripcion}** · {d.tipo} · {f.licencia} · autor: {f.autor} · [ver en Wikimedia Commons]({f.fuente_url})")

    izq, der = st.columns([2, 3])
    with izq:
        if doc_id in PUBLICABLES:
            st.image(str(CARPETA / PUBLICABLES[doc_id]), caption=f"{doc_id} · {f.licencia} · {f.autor}")
        else:
            st.info("La imagen de este documento no se muestra porque contiene datos de personas privadas. "
                    "El texto está disponible ya seudonimizado.")
    with der:
        modelo_doc = st.radio("Texto de", [OCR_BASE, OCR_ALT], horizontal=True, key="modelo_doc",
                              index=[OCR_BASE, OCR_ALT].index(modelo_ocr))
        texto = d.texto_ocr if modelo_doc == OCR_BASE else alternativos.set_index("id").loc[doc_id, "texto"]
        st.text_area(f"Texto OCR ({modelo_doc})", texto, height=260, key=f"ocr_{doc_id}_{modelo_doc}")
        st.caption(f"{d.lineas} líneas · confianza media {d.confianza_media:.2f} · {d.segundos_ocr:.0f} s de proceso (PaddleOCR)")
        st.markdown("**Campos extraídos por el LLM** (Gemini 3.5 Flash-Lite)")
        st.dataframe(tabla_campos(doc_id), width="stretch", hide_index=True)
        if isinstance(d.texto_referencia, str):
            m = metricas[(metricas.id == doc_id)].set_index("modelo").valor
            st.markdown("**Documento de la muestra de evaluación**: transcripción manual y CER de cada modelo")
            a, b = st.columns(2)
            a.metric(f"CER {OCR_BASE}", f"{m[OCR_BASE]:.3f}")
            b.metric(f"CER {OCR_ALT}", f"{m[OCR_ALT]:.3f}")
            with st.expander("Transcripción manual de referencia"):
                st.text(d.texto_referencia)

# ───────────────────────────────────────────────────────── audios
with tab_audio:
    c1, c2 = st.columns([1, 2])
    with c1:
        dur = clips_f.sort_values("duracion_seg")
        fig = px.bar(dur, x="duracion_seg", y="id", color="descripcion", orientation="h",
                     title="Duración por clip y condición", labels={"duracion_seg": "Segundos", "id": "", "descripcion": ""})
        fig.update_layout(height=max(300, 22 * len(dur) + 120), legend=dict(orientation="h", y=-0.15), margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with c2:
        opciones = clips_f.id.tolist() or clips.id.tolist()
        etiqueta = dict(zip(clips.id, clips.id + " · " + clips.descripcion + " · " + clips.duracion_seg.map(lambda s: f"{s:.0f} s")))
        clip_id = st.selectbox("Clip", opciones, format_func=etiqueta.get)
        c = clips.set_index("id").loc[clip_id]
        f = fuentes.set_index("id").loc[clip_id]
        st.markdown(f"**{c.descripcion}** · {c.duracion_seg:.0f} s ({c.voz_seg:.0f} s con voz) · {c.n_hablantes:.0f} hablante(s) "
                    f"según la diarización · {f.licencia} · [ver en Wikimedia Commons]({f.fuente_url})")
        if clip_id in PUBLICABLES:
            st.audio(str(CARPETA / PUBLICABLES[clip_id]), format="audio/ogg")
        else:
            st.info("El audio de este clip no se reproduce aquí porque en él se oyen o se nombran personas privadas. "
                    "La transcripción está disponible ya seudonimizada.")

        alt = alternativos[(alternativos.id == clip_id) & (alternativos.modalidad == "audio")]
        if len(alt):
            m = metricas[metricas.id == clip_id].set_index("modelo").valor
            a, b = st.columns(2)
            with a:
                st.markdown(f"**{ASR_BASE}** (con marcas de hablante)")
                st.text_area("ASR base", c.texto_asr, height=300, label_visibility="collapsed", key=f"asr_b_{clip_id}")
                if ASR_BASE in m:
                    st.metric(f"WER {ASR_BASE}", f"{m[ASR_BASE]:.3f}")
            with b:
                st.markdown(f"**{ASR_ALT}** (sin diarización)")
                st.text_area("ASR alternativo", alt.texto.iloc[0], height=300, label_visibility="collapsed", key=f"asr_a_{clip_id}")
                if ASR_ALT in m:
                    st.metric(f"WER {ASR_ALT}", f"{m[ASR_ALT]:.3f}")
        else:
            st.text_area(f"Transcripción ({ASR_BASE}, con marcas de hablante)", c.texto_asr, height=300, key=f"asr_{clip_id}")
        st.markdown("**Campos extraídos por el LLM**")
        st.dataframe(tabla_campos(clip_id), width="stretch", hide_index=True)
        if isinstance(c.texto_referencia, str):
            with st.expander("Transcripción manual de referencia (seudonimizada)"):
                st.text(c.texto_referencia)

# ───────────────────────────────────────────────────────── evaluación
with tab_eval:
    st.subheader("Mismos 10 documentos y 10 clips para todos los modelos")
    t = corpus[["modalidad", "modelo", "métrica", "valor (corpus)", "segundos por documento", "factor de tiempo real"]]
    st.dataframe(t.round(3), width="stretch", hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        dm = metricas[metricas.modalidad == "documento"]
        dm = dm[dm.tipo.isin(tipos)] if tipos else dm
        fig = px.bar(dm, x="id", y="valor", color="modelo", barmode="group", color_discrete_map=COLOR_MODELO,
                     hover_data=["tipo"], title="CER por documento: PaddleOCR gana en todos, EasyOCR se hunde en manuscritos",
                     labels={"valor": "CER", "id": ""})
        fig.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with c2:
        am = metricas[metricas.modalidad == "audio"]
        fig = px.bar(am, x="id", y="valor", color="modelo", barmode="group", color_discrete_map=COLOR_MODELO,
                     hover_data=["tipo", "factor_tiempo_real"],
                     title="WER por clip: Whisper gana con habla limpia, Qwen3-ASR con ruido", labels={"valor": "WER", "id": ""})
        fig.update_layout(height=380, legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    fig = px.scatter(am, x="factor_tiempo_real", y="valor", color="modelo", color_discrete_map=COLOR_MODELO, text="id",
                     title="Precisión frente a latencia en CPU: Qwen3-ASR tarda 2,3 veces más sin ser más preciso",
                     labels={"factor_tiempo_real": "Factor de tiempo real (cómputo / duración)", "valor": "WER"})
    fig.update_traces(textposition="top center").update_layout(height=380, legend_title_text="")
    st.plotly_chart(fig, width="stretch")

    st.subheader(f"Auditoría humana del LLM: {correctas}/{len(auditoria)} extracciones completamente correctas")
    st.caption("20 extracciones sorteadas (semilla 2026), 10 documentos y 10 audios, revisadas campo por campo contra el texto y el original.")
    cols_ok = [col for col in auditoria.columns if col.startswith("ok_")]
    errores = (auditoria[cols_ok] == False).sum().rename(lambda col: col[3:])
    a, b = st.columns([1, 2])
    a.dataframe(errores[errores > 0].rename("errores").to_frame(), width="stretch")
    b.dataframe(auditoria.loc[~auditoria.completa.astype(bool), ["id", "modalidad", "comentario"]], width="stretch", hide_index=True)

# ───────────────────────────────────────────────────────── fuentes
with tab_fuentes:
    st.markdown(
        "- **Fuentes:** todos los archivos vienen de Wikimedia Commons, con su licencia y autor (tabla de abajo). Se descargaron el 22 de octubre de 2026.\n"
        "- **Seudonimización:** los nombres de personas privadas (entrevistadas, homenajeados) se cambiaron por etiquetas. "
        "Las figuras históricas y los funcionarios en ejercicio público se conservan. Solo se muestran las imágenes y los audios sin personas privadas.\n"
        "- **Evaluación:** el CER y el WER se calculan contra transcripciones manuales hechas desde el original. Las configuraciones se fijaron antes de medir.\n"
        "- **Código y notebooks:** `01_extraccion.ipynb` (OCR, ASR, limpieza y EDA) y `02_evaluacion.ipynb` (métricas, LLM y comparativa).")
    st.dataframe(fuentes[["id", "modalidad", "licencia", "autor", "fuente_url", "fecha_descarga"]], width="stretch", hide_index=True,
                 column_config={"fuente_url": st.column_config.LinkColumn("fuente")})
    st.download_button("Descargar fuentes (CSV)", fuentes.to_csv(index=False).encode("utf-8"), file_name="fuentes.csv", mime="text/csv")
