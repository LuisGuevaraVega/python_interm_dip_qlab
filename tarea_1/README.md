# 🗞️ Tarea 1 – Noticias peruanas: del titular al clasificador

**Estudiante:** [@LuisGuevaraVega](https://github.com/LuisGuevaraVega) · Python Intermedio – Diplomado de Ciencia de Datos (QLab)

## 1. Pregunta del proyecto

> **¿Pueden convertir titulares peruanos en un clasificador de noticias?**

Sí. Con 458 titulares de La República etiquetados por un LLM (supervisión débil) se afinó un
DistilBERT multilingüe que clasifica titulares nuevos en `politica`, `economia`, `deportes` o
`ciencia_tecnologia` con **F1 macro de 0.913** en un test reservado, frente a 0.672 del enfoque
zero-shot sin entrenamiento.

| Enfoque | Evaluado sobre | Accuracy | F1 macro | Latencia (CPU) |
| :--- | :--- | :---: | :---: | :---: |
| Zero-shot `Recognai/bert-base-spanish-wwm-cased-xnli` | 40 titulares | 0.675 | 0.672 | ~200 ms/titular |
| LLM `gemini-3.5-flash-lite` (prompt estructurado) | test (69) | 0.942 | 0.942 | 1–3 s por lote (API) |
| **DistilBERT fine-tuned (elegido)** | **test (69)** | **0.913** | **0.913** | **~17 ms/titular** |

Auditoría humana de 20 predicciones del LLM: **20/20 de acuerdo**.

## 2. Medio y fechas de extracción

* **Medio:** Opción A – **La República** (`larepublica.pe`).
* **Fecha de descarga:** 14 de octubre de 2026 (474 peticiones, todas HTTP 200, en 14 minutos).
* **Fechas de publicación:** del 2020-03-15 al 2026-10-14; el 63 % de las noticias es de septiembre–octubre de 2026.
* **Volumen final:** 458 noticias (politica 115 · economia 115 · deportes 114 · ciencia_tecnologia 114) con las
  7 columnas obligatorias. Se descartaron 202 registros crudos: 60 URLs duplicadas, 2 titulares repetidos y
  140 noticias de secciones fuera de las 4 categorías (sociedad, espectáculos, mundo, opinión…).
* **Cómo se extrajo:** `robots.txt` permite `/rss/*` y `/sitemap/*` pero prohíbe la paginación de secciones.
  Se usaron como semillas el RSS, los news sitemaps y las portadas de sección, y luego se siguieron los
  **enlaces relacionados** de cada artículo (round-robin por categoría). Cada URL se valida contra
  `robots.txt` antes de pedirla, con `User-Agent` descriptivo, pausas de 1–2 s y máximo 1 reintento.
  Respaldo crudo en `datos/raw/`.

## 3. Hallazgos analíticos

1. **Un LLM barato basta como anotador para entrenar un buen clasificador.** Gemini Flash-Lite coincidió con
   la sección editorial en el 95 % del dataset y con mi revisión manual en 20/20 casos. Entrenado solo con esas
   etiquetas, DistilBERT sube el F1 macro de 0.672 (zero-shot) a 0.913, queda a 3 puntos del propio LLM
   (2 titulares de 69) y clasifica un titular en ~17 ms en CPU, frente a 1–3 s de una llamada a la API.
2. **La frontera difícil es economía ↔ política, y es la misma para el LLM y para el modelo.** La economía
   peruana se cuenta a través de actores del Estado (*"Julio Velarde es ratificado por el Senado"*,
   *"presidente de Petroperú…"*): 11 de los 23 desacuerdos LLM–sección y 3 de los 6 errores del modelo en test
   son de este tipo. En cambio, deportes tiene un léxico casi exclusivo (recall 1.00) y ciencia y tecnología
   titula con un estilo propio, largo y narrativo (mediana de 118 caracteres frente a 94 en política).

## 4. Limitaciones técnicas

1. **Muestra pequeña y sesgada al presente.** El test tiene 69 titulares, así que cada error mueve el F1 en
   ~1.4 puntos y la diferencia entre el LLM y DistilBERT no es concluyente. Además, el 63 % de las noticias es de
   septiembre–octubre de 2026 (el rastreo favorece notas recientes y coincide con las elecciones regionales):
   el modelo puede rendir peor con la agenda de otros meses y conviene reentrenarlo periódicamente.
2. **Las etiquetas de referencia son la sección del diario, no el tema "verdadero".** La sección *tecnología*
   incluye notas comerciales (ofertas de Cyber Wow, reseñas de celulares) y el modelo, entrenado con etiquetas
   del LLM, hereda sus errores: en 2 de los 6 fallos en test el LLM ya discrepaba de la sección. La `confianza`
   del LLM es autodeclarada, no una probabilidad calibrada.

## 5. Cómo ejecutarlo en local

Requisitos: Anaconda/Miniconda y unos 3 GB de RAM libres para el fine-tuning.

```bash
# 1) Entorno (Python 3.11 de conda-forge: trae librerías de Visual C++ actuales, necesarias para torch en Windows)
conda create -n tarea1 -c conda-forge python=3.11 -y
conda activate tarea1
pip install -r tarea_1/requirements.txt   # incluye torch CPU desde el índice oficial de PyTorch

# 2) Ir a la carpeta del trabajo
cd tarea_1

# 3) (Solo para volver a etiquetar con el LLM) crear .env con tu API key de Google AI Studio
copy .env.example .env        # en Linux/Mac: cp .env.example .env

# 4) Ejecutar los notebooks (el 01 reutiliza el respaldo crudo; el 02 entrena y guarda el modelo en modelo/)
jupyter nbconvert --to notebook --execute --inplace 01_recoleccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_clasificacion.ipynb

# 5) Levantar el dashboard
streamlit run app.py
```

* Los pesos del modelo (`modelo/model.safetensors`, ~540 MB) **no se suben a GitHub** por el límite de 100 MB.
  Hay una copia pública en Hugging Face:
  [`LuisGGV/distilbert-titulares-larepublica`](https://huggingface.co/LuisGGV/distilbert-titulares-larepublica).
  Si `modelo/` no tiene los pesos, la app los descarga de ahí automáticamente (así funciona en Streamlit Cloud);
  el paso 4 también los regenera en ~2 minutos en CPU. Sin pesos ni internet, el probador cae al zero-shot y
  lo indica en pantalla.
* `datos/etiquetas_llm.csv` y `datos/auditoria_llm.csv` ya están en el repo, así que el notebook 02 **no** llama a
  la API de Gemini salvo que se borren.

El dashboard incluye filtros por medio, categoría y fecha; métricas clave (total de noticias, F1 macro en test,
concordancia LLM–humano); gráfico de distribución; tabla con descarga en CSV y un **probador en vivo** que
devuelve la categoría y la probabilidad de cada clase para cualquier titular.

## Estructura

```text
tarea_1/
├── 01_recoleccion.ipynb     # robots.txt, scraping, limpieza, mapeo de secciones, EDA (ejecutado)
├── 02_clasificacion.ipynb   # zero-shot, LLM + auditoría, split, fine-tuning, test, comparativa (ejecutado)
├── app.py                   # dashboard Streamlit
├── requirements.txt         # dependencias con versiones exactas
├── .env.example             # plantilla para la API key de Gemini (.env no se versiona)
├── datos/
│   ├── noticias.csv         # 458 x 7
│   ├── etiquetas_llm.csv    # titular, etiqueta_llm, confianza, modelo_llm, fecha
│   ├── auditoria_llm.csv    # 20 casos revisados manualmente
│   └── raw/                 # robots.txt, RSS, sitemaps, artículos crudos, log de peticiones, respuestas del LLM
└── modelo/                  # config, tokenizer y metrics.json (los pesos se regeneran con el notebook 02)
```
