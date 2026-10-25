# Voces y documentos peruanos: del archivo escaneado al texto buscable

**Pregunta:** ¿podemos convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?

**Dashboard público:** https://tarea-2-texto-audio.streamlit.app/

Tarea 2 del curso Data Science con Python. Es un pipeline de IA que extrae texto de documentos peruanos con OCR, transcribe entrevistas en español peruano con ASR, seudonimiza a las personas privadas, extrae campos estructurados con un LLM y publica los resultados en un dashboard de Streamlit.

## Corpus y fuentes

Todos los archivos vienen de **Wikimedia Commons** y se descargaron el **22 de octubre de 2026** con `corpus.py`, usando un User-Agent descriptivo y pausas de 2 s entre solicitudes. La URL, la licencia, el autor y la forma de recuperar cada archivo están en [`datos/fuentes.csv`](datos/fuentes.csv).

| Corpus | Volumen | Composición | Licencias |
|---|---|---|---|
| **A. Documentos** | 25 imágenes | 8 impresos, 8 fotos con sombra o inclinación, 9 manuscritos (siglos XVII–XXI) | 10 dominio público, 5 CC0, 7 CC BY-SA 4.0, 2 CC BY-SA 3.0, 1 CC BY 4.0 |
| **B. Audio** | 23 clips · 42,4 min | entrevistas en la calle, en marchas, en fiestas patronales de Áncash y de estudiantes de la UNMSM, conferencias de prensa y lecturas de artículos; 13 clips con 2 o más hablantes según la diarización | 23 CC BY-SA 4.0 |

- **Seudonimización:** 19 personas privadas (entrevistadas, entrevistadores, un homenajeado) se reemplazaron por etiquetas como `[ENTREVISTADA_1]` en todos los textos publicados. Las figuras históricas y los funcionarios en ejercicio público se conservan. El mapa con los nombres reales no se versiona.
- **Muestra publicable** (`datos/ejemplos/`): 23 imágenes reducidas y 9 audios en OGG, solo de los archivos donde no aparecen personas privadas. El resto se consulta como texto y metadatos.
- **No se versionan** los originales, las salidas crudas ni los pesos de los modelos (`datos/raw/`, ver `.gitignore`).

## Método

| Etapa | Modelo base | Modelo alternativo |
|---|---|---|
| OCR | PaddleOCR 3.7 · PP-OCRv6 medium (CPU, sin preprocesamiento) | EasyOCR 1.7.2 · CRAFT + latin_g2 |
| ASR | faster-whisper `small` (CPU int8, VAD Silero, diarización con WeSpeaker) | Qwen3-ASR 0.6B (CPU float32, mismo VAD) |
| Extracción | Gemini 3.5 Flash-Lite, temperatura 0, JSON validado con esquema | — |

La evaluación usa **10 documentos y 10 clips** del corpus, transcritos a mano por el autor desde el original. Las configuraciones se fijaron y se versionaron antes de calcular cualquier métrica (`modelos/configuracion.json`).

## Resultados

| Modalidad | Modelo | Métrica (10 archivos) | Latencia en CPU |
|---|---|---|---|
| Documentos | **PaddleOCR** | **CER 0,091** | 28 s por documento |
| Documentos | EasyOCR | CER 0,300 | 17 s por documento |
| Audio | **faster-whisper small** | **WER 0,218** | factor de tiempo real 0,36 |
| Audio | Qwen3-ASR 0,6B | WER 0,228 | factor de tiempo real 0,84 |
| Extracción LLM | Gemini 3.5 Flash-Lite | acuerdo con la auditoría humana: **10/20** fichas completamente correctas (impresos y fotos 5/5, manuscritos 0/5, audios 5/10) | — |

### Hallazgos

1. **El tipo de documento importa más que el modelo de OCR.** PaddleOCR lee impresos y fotos casi sin errores (CER 0,04 y 0,03), pero en manuscritos el error sube a 0,24, de 6 a 8 veces más. EasyOCR triplica el error en todos los tipos y en manuscritos devuelve más ruido que texto (CER 0,68).
2. **En audio, el modelo más pequeño es la mejor opción.** faster-whisper `small` y Qwen3-ASR tienen un WER casi igual (0,22 frente a 0,23), pero Whisper gana en 6 de los 10 clips y transcribe 2,3 veces más rápido. Qwen solo mejora con ruido fuerte de fondo, como en un partido o una fiesta patronal. Con VAD, ninguno de los dos inventó frases sobre la música (clip_014).

### Limitaciones

1. **Manuscritos y multitudes siguen necesitando revisión humana.** Ningún OCR baja de CER 0,16 en cursiva del siglo XIX, y la diarización automática confunde voces en multitudes: detectó 12 "hablantes" en 54 s de una marcha. El LLM hereda los dos errores, porque cuenta las etiquetas de hablante y copia cantidades mal leídas por el OCR.
2. **La muestra de evaluación es pequeña y la transcribió una sola persona.** Diez archivos por modalidad alcanzan para comparar modelos, no para dar intervalos de confianza estrechos. Las referencias de un único transcriptor, que incluyen las muletillas, también fijan un criterio que los modelos, más cercanos a una transcripción limpia, no comparten. Las latencias se midieron solo en CPU (laptop de 8 GB de RAM).

## Estructura

```
tarea_2/
├── 01_extraccion.ipynb      # OCR, ASR, seudonimización, limpieza y EDA (Parte 1)
├── 02_evaluacion.ipynb      # CER/WER, modelos alternativos, LLM y auditoría (Parte 2)
├── app.py                   # dashboard de Streamlit (Parte 3)
├── requirements.txt         # dependencias del dashboard
├── corpus.py                # descarga del corpus y muestra publicable
├── extraccion.py            # OCR y ASR base por tandas (con caché)
├── evaluacion.py            # modelos alternativos, métricas y extracción con el LLM
├── voz.py                   # utilidades de audio de la Sesión 13 (VAD, diarización, WER)
├── modelos/configuracion.json
├── evidencias_ia/           # conversaciones con Claude Code
└── datos/
    ├── documentos.csv · transcripciones.csv · fuentes.csv
    ├── extraccion_llm.csv · auditoria_llm.csv
    ├── metricas.csv · metricas_corpus.csv · modelos_alternativos.csv
    └── ejemplos/            # imágenes y audios publicables
```

## Cómo ejecutarlo

**Dashboard en local** (solo lee los CSV):

```bash
git clone https://github.com/LuisGuevaraVega/python_interm_dip_qlab.git
cd python_interm_dip_qlab/tarea_2
python -m venv .venv-app
.venv-app\Scripts\activate          # Windows; en macOS/Linux: source .venv-app/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

**Pipeline completo** (opcional; descarga ~2 GB de modelos y corre en CPU), con [uv](https://docs.astral.sh/uv/):

```bash
uv sync                                    # entorno de los notebooks (PaddleOCR, faster-whisper, transformers...)
uv run python corpus.py                    # descarga los 25 documentos y 23 audios a datos/raw/
uv run python extraccion.py ocr            # PaddleOCR sobre los 25 documentos
uv run python extraccion.py asr            # faster-whisper + VAD + diarización sobre los 23 clips
uv run python evaluacion.py easyocr doc_001 doc_002 ...   # EasyOCR (sin ids: los 10 de la muestra)
uv run python evaluacion.py qwen           # Qwen3-ASR sobre los 10 clips de la muestra
uv run python evaluacion.py llm            # Gemini (requiere GEMINI_API_KEY en .env)
uv run python corpus.py ejemplos           # muestra publicable para el dashboard
```

Después se ejecutan `01_extraccion.ipynb` y `02_evaluacion.ipynb` (kernel del entorno uv). Las transcripciones manuales de referencia (`datos/referencias/`) y el mapa de seudónimos (`datos/raw/seudonimos.json`) son locales.
