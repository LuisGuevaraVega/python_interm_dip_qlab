"""Dashboard Streamlit – Tarea 1: clasificador de titulares peruanos (La República).

Ejecutar desde la carpeta tarea_1/:
    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
RUTA_DATOS = BASE / "datos" / "noticias.csv"
RUTA_MODELO = BASE / "modelo"
MODELO_HUB = "LuisGGV/distilbert-titulares-larepublica"   # copia pública de los pesos entrenados
CATEGORIAS = ["politica", "economia", "deportes", "ciencia_tecnologia"]
NOMBRES = {
    "politica": "Política",
    "economia": "Economía",
    "deportes": "Deportes",
    "ciencia_tecnologia": "Ciencia y tecnología",
}
COLORES = {
    "Política": "#4C78A8",
    "Economía": "#F58518",
    "Deportes": "#54A24B",
    "Ciencia y tecnología": "#B279A2",
}

st.set_page_config(page_title="Clasificador de titulares peruanos", page_icon="🗞️", layout="wide")


# --------------------------------------------------------------------------- datos
@st.cache_data
def cargar_datos():
    df = pd.read_csv(RUTA_DATOS, parse_dates=["fecha"])
    df["categoria"] = df["etiqueta"].map(NOMBRES)
    return df


@st.cache_data
def cargar_metricas():
    return json.loads((RUTA_MODELO / "metrics.json").read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Cargando el clasificador…")
def cargar_clasificador():
    """Carga el DistilBERT entrenado. Los pesos (~540 MB) no se suben a GitHub, así que:
    1) se usan los de modelo/ si existen (ejecución local tras el notebook 02);
    2) si no, se descargan del Hugging Face Hub (así funciona en Streamlit Cloud);
    3) si tampoco hay acceso al Hub, se cae al zero-shot para que la app siga respondiendo."""
    import torch
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              pipeline)

    if (RUTA_MODELO / "model.safetensors").exists():
        fuentes = [(str(RUTA_MODELO), "DistilBERT fine-tuned (modelo/ local)")]
    else:
        fuentes = [(MODELO_HUB, f"DistilBERT fine-tuned (Hugging Face: {MODELO_HUB})")]

    for fuente, nombre in fuentes:
        try:
            tokenizer = AutoTokenizer.from_pretrained(fuente)
            modelo = AutoModelForSequenceClassification.from_pretrained(fuente).eval()
        except OSError:
            continue

        def predecir(texto, tokenizer=tokenizer, modelo=modelo):
            entradas = tokenizer(texto, truncation=True, max_length=64, return_tensors="pt")
            with torch.no_grad():
                probs = torch.softmax(modelo(**entradas).logits, dim=-1)[0].tolist()
            return {modelo.config.id2label[i]: p for i, p in enumerate(probs)}

        return nombre, predecir

    zero_shot = pipeline("zero-shot-classification",
                         model="Recognai/bert-base-spanish-wwm-cased-xnli")
    hipotesis = {"política y gobierno": "politica", "economía y negocios": "economia",
                 "deportes": "deportes", "ciencia y tecnología": "ciencia_tecnologia"}

    def predecir(texto):
        r = zero_shot(texto, candidate_labels=list(hipotesis),
                      hypothesis_template="Esta noticia trata sobre {}.")
        return {hipotesis[e]: p for e, p in zip(r["labels"], r["scores"])}

    return "Zero-shot BETO-XNLI (respaldo: no se pudo cargar el modelo entrenado)", predecir


df = cargar_datos()
metricas = cargar_metricas()

# --------------------------------------------------------------------------- encabezado
st.title("🗞️ ¿Pueden convertir titulares peruanos en un clasificador de noticias?")
st.markdown(
    f"""
Se recolectaron **{len(df)} titulares de La República** (RSS, news sitemaps y rastreo de enlaces
relacionados, respetando `robots.txt`), se etiquetaron con un LLM (**{metricas['modelo_llm']}**) como
supervisión débil, validada con una auditoría humana de 20 casos, y con esas etiquetas se afinó
**DistilBERT multilingüe**. El modelo se evaluó sobre un **test reservado del 15 %** contra la sección
editorial del diario. Abajo puedes explorar los datos y **probar el clasificador con cualquier titular**.
"""
)

# --------------------------------------------------------------------------- filtros
st.sidebar.header("Filtros")
medios = st.sidebar.multiselect("Medio", sorted(df["medio"].unique()),
                                default=sorted(df["medio"].unique()))
categorias = st.sidebar.multiselect("Categoría", list(NOMBRES.values()),
                                    default=list(NOMBRES.values()))
desde, hasta = df["fecha"].min().date(), df["fecha"].max().date()
rango = st.sidebar.date_input("Fecha de publicación", value=(desde, hasta),
                              min_value=desde, max_value=hasta)
st.sidebar.caption("Los filtros actualizan el gráfico y la tabla.")

filtrado = df[df["medio"].isin(medios) & df["categoria"].isin(categorias)]
if isinstance(rango, tuple) and len(rango) == 2:
    filtrado = filtrado[filtrado["fecha"].dt.date.between(*rango)]

# --------------------------------------------------------------------------- métricas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Noticias recolectadas", f"{len(df)}",
          delta=f"{len(filtrado)} con los filtros actuales", delta_color="off")
c2.metric("F1 macro en test", f"{metricas['f1_macro_test']:.3f}",
          delta=f"+{metricas['f1_macro_test'] - metricas['f1_zero_shot']:.3f} vs zero-shot")
aciertos, total = map(int, metricas["acuerdo_llm_humano"].split("/"))
c3.metric("Concordancia LLM vs. humano", f"{aciertos / total:.0%}",
          delta=f"{metricas['acuerdo_llm_humano']} casos auditados", delta_color="off")
c4.metric("Accuracy en test", f"{metricas['accuracy_test']:.3f}")

# --------------------------------------------------------------------------- probador
st.subheader("🔮 Probador en vivo")
nombre_modelo, predecir = cargar_clasificador()
st.caption(f"Clasificador activo: **{nombre_modelo}**")

col_texto, col_resultado = st.columns([3, 2])
with col_texto:
    titular = st.text_area(
        "Escribe o pega un titular:",
        value="BCR mantiene la tasa de referencia en 4,25 % por tercer mes consecutivo",
        height=110,
    )
    clasificar = st.button("Clasificar titular", type="primary")

with col_resultado:
    if clasificar:
        if not titular.strip():
            st.warning("Escribe un titular primero.")
        else:
            probs = predecir(titular.strip())
            ganadora = max(probs, key=probs.get)
            st.success(f"**{NOMBRES[ganadora]}** — probabilidad {probs[ganadora]:.1%}")
            tabla = pd.DataFrame({"categoria": [NOMBRES[c] for c in CATEGORIAS],
                                  "probabilidad": [probs[c] for c in CATEGORIAS]})
            fig_p = px.bar(tabla, x="probabilidad", y="categoria", orientation="h",
                           color="categoria", color_discrete_map=COLORES,
                           range_x=[0, 1], text_auto=".1%")
            fig_p.update_layout(showlegend=False, height=230, margin=dict(l=0, r=0, t=10, b=0),
                                xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_p, width="stretch")
            if probs[ganadora] < 0.6:
                st.info("Confianza baja: el titular mezcla temas de varias categorías.")
    else:
        st.info("Presiona **Clasificar titular** para ver la categoría y su probabilidad.")

# --------------------------------------------------------------------------- exploración
st.subheader("📊 Exploración del dataset")
if filtrado.empty:
    st.warning("Ningún titular coincide con los filtros.")
else:
    conteo = (filtrado["categoria"].value_counts()
              .reindex([c for c in NOMBRES.values() if c in categorias]).fillna(0)
              .rename_axis("categoria").reset_index(name="noticias"))
    fig = px.bar(conteo, x="categoria", y="noticias", color="categoria", text="noticias",
                 color_discrete_map=COLORES,
                 title=f"Distribución por categoría ({len(filtrado)} noticias filtradas)")
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Noticias")
    st.plotly_chart(fig, width="stretch")

    columnas = ["titular", "categoria", "seccion_original", "fecha", "bajada", "url"]
    st.dataframe(
        filtrado[columnas].sort_values("fecha", ascending=False),
        width="stretch", hide_index=True,
        column_config={
            "fecha": st.column_config.DateColumn("fecha", format="YYYY-MM-DD"),
            "url": st.column_config.LinkColumn("url", display_text="abrir"),
        },
    )
    st.download_button(
        "⬇️ Descargar CSV filtrado",
        data=filtrado.drop(columns="categoria").to_csv(index=False).encode("utf-8"),
        file_name="noticias_filtradas.csv", mime="text/csv",
    )

# --------------------------------------------------------------------------- comparativa
with st.expander("Comparación de enfoques (test reservado)"):
    st.table(pd.DataFrame([
        {"Enfoque": "Zero-shot BETO-XNLI (40 titulares)", "F1 macro": metricas["f1_zero_shot"]},
        {"Enfoque": f"LLM {metricas['modelo_llm']}", "F1 macro": metricas["f1_llm_test"]},
        {"Enfoque": "DistilBERT fine-tuned (elegido)", "F1 macro": metricas["f1_macro_test"]},
    ]).set_index("Enfoque").style.format("{:.3f}"))
    st.caption("Se eligió DistilBERT: precisión cercana al LLM, ~17 ms por titular en CPU, "
               "sin depender de una API externa. Detalles en 02_clasificacion.ipynb.")
