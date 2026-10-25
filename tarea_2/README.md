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

<details>
<summary><b>Fuente, licencia y autor de cada archivo (48)</b></summary>

| id | Tipo o condición | Licencia | Autor | Fuente |
|---|---|---|---|---|
| doc_001 | impreso | CC BY-SA 4.0 | Elypress | [Commons](https://commons.wikimedia.org/wiki/File:Carta_Democr%C3%A1tica_Interamericana.jpg) |
| doc_002 | impreso | CC0 | Anderson Reyes Trillo | [Commons](https://commons.wikimedia.org/wiki/File:Carta_de_agradecimiento_del_secretario_de_la_Presidencia_de_la_Rep%C3%BAblica_Nazario_Ch%C3%A1vez_Aliaga_al_pintor_Segundo_Ciro_Gallardo_Gallo_en_nombre_del_presidente_Manuel_Prado_Ugarteche.jpg) |
| doc_003 | impreso | CC0 | Ing. Oswaldo Jiménez Salas | [Commons](https://commons.wikimedia.org/wiki/File:Otorgamiento_Municipal.jpg) |
| doc_004 | impreso | CC BY-SA 4.0 | El Peruano | [Commons](https://commons.wikimedia.org/wiki/File:NOMBRAMIENTO_JAVIER_DAVID_HABICH.pdf) |
| doc_005 | impreso | Public domain | Varios | [Commons](https://commons.wikimedia.org/wiki/File:Constituci%C3%B3n_Pol%C3%ADtica_del_Per%C3%BA_%281856%29.pdf) |
| doc_006 | impreso | Public domain | Palma, Clemente, dir. (Director).Moral, M. ed. (Editor). | [Commons](https://commons.wikimedia.org/wiki/File:Variedades_No._67.pdf) |
| doc_007 | impreso | Public domain | Ricardo Palma | [Commons](https://commons.wikimedia.org/wiki/File:Cachivaches.djvu) |
| doc_008 | impreso | CC0 | Bachmann, Carlos J., 1869- | [Commons](https://commons.wikimedia.org/wiki/File:4000004161-0016_-_Carta_de_Carlos_J._Bachmann._1914_julio_4%2C_Maldonado%3B_para_Ricardo_Palma%2C_Lima.pdf) |
| doc_009 | foto | CC BY-SA 3.0 | Miguel Angel Chong | [Commons](https://commons.wikimedia.org/wiki/File:LimaPlacaCatedral1988.JPG) |
| doc_010 | foto | CC BY-SA 4.0 | AlejandroFC | [Commons](https://commons.wikimedia.org/wiki/File:Placa_de_la_Casa_Federico_Elguera%2C_Calle_La_Virreyna%2C_Lima.jpg) |
| doc_011 | foto | CC BY-SA 4.0 | AlejandroFC | [Commons](https://commons.wikimedia.org/wiki/File:Pasaje_Acisclo_Villar%C3%A1n_-_Placa_conmemorativa.jpg) |
| doc_012 | foto | CC0 | El Surquillano | [Commons](https://commons.wikimedia.org/wiki/File:Placa_conmemorativa_Mercado_Minorista_La_Parada.jpg) |
| doc_013 | foto | CC BY-SA 4.0 | AlejandroFC | [Commons](https://commons.wikimedia.org/wiki/File:Centro_Espa%C3%B1ol%2C_Lima_01.jpg) |
| doc_014 | foto | CC BY 4.0 | Happa | [Commons](https://commons.wikimedia.org/wiki/File:Commemorative_plaque_to_Ioannes_Paulus_II_in_the_Cathedral_of_Lima.jpg) |
| doc_015 | foto | CC BY-SA 4.0 | Guillermo Carlos Gómez | [Commons](https://commons.wikimedia.org/wiki/File:Araucaria_patrimonial_de_San_Isidro_06.jpg) |
| doc_016 | foto | CC BY-SA 4.0 | Ciberprofe | [Commons](https://commons.wikimedia.org/wiki/File:Carta_de_Grau_a_viuda_de_Prat_en_monumento_chileno.JPG) |
| doc_017 | manuscrito | Public domain | Miguel Grau (1834-1879) | [Commons](https://commons.wikimedia.org/wiki/File:Miguel_Grau_-_Brev.jpg) |
| doc_018 | manuscrito | Public domain | Agustín Gamarra | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-53-2.jpg) |
| doc_019 | manuscrito | Public domain | Miguel de San Román | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-64.jpg) |
| doc_020 | manuscrito | Public domain | Nicolás de Piérola | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-69.jpg) |
| doc_021 | manuscrito | CC BY-SA 3.0 | Dtarazona | [Commons](https://commons.wikimedia.org/wiki/File:AAMSM_carta_a_hermano_31072010.jpg) |
| doc_022 | manuscrito | CC0 | Bachmann, Carlos J., 1869- | [Commons](https://commons.wikimedia.org/wiki/File:4000004161-0003_-_Carta_de_Carlos_J._Bachmann._1912_junio_10%2C_Riberalta%3B_para_Ricardo_Palma%2C_Lima.pdf) |
| doc_023 | manuscrito | Public domain | Manuel Menéndez | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-57.pdf) |
| doc_024 | manuscrito | Public domain | José Balta | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-67.jpg) |
| doc_025 | manuscrito | Public domain | Pedro de Toledo, 1st Marquis of Mancera, Juan de Cáceres y Ulloa | [Commons](https://commons.wikimedia.org/wiki/File:AR-ANH-EF-Secc.II-17.pdf) |
| clip_001 | entrevista en la calle | CC BY-SA 4.0 | JorgeFlores-pe | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_1_en_la_Av._Rivag%C3%BCero_-_El_Agustino.ogg) |
| clip_002 | entrevista en la calle, varias hablantes | CC BY-SA 4.0 | JorgeFlores-pe | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_2_en_la_Av._Rivag%C3%BCero_-_El_Agustino.ogg) |
| clip_003 | entrevista durante un partido, ruido de fondo | CC BY-SA 4.0 | Ariana Lucero De La Cruz Guerrero | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_en_el_medio_tiempo.opus) |
| clip_004 | entrevista grabada por estudiante UNMSM | CC BY-SA 4.0 | Gianpier Yair Venegas Ambia | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_1%2C.wav) |
| clip_005 | entrevista grabada por estudiante UNMSM | CC BY-SA 4.0 | Gianpier Yair Venegas Ambia | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_2.wav) |
| clip_006 | entrevista grabada por estudiante UNMSM | CC BY-SA 4.0 | Gianpier Yair Venegas Ambia | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_3.wav) |
| clip_007 | entrevista grabada por estudiante UNMSM | CC BY-SA 4.0 | Gianpier Yair Venegas Ambia | [Commons](https://commons.wikimedia.org/wiki/File:Entrevista_4.wav) |
| clip_008 | entrevista en una marcha, ruido de multitud | CC BY-SA 4.0 | Joaquin Canales | [Commons](https://commons.wikimedia.org/wiki/File:Audio_de_la_entrevista_a_una_chica_que_participaba_de_la_marcha.ogg) |
| clip_009 | entrevista en una marcha, ruido de multitud | CC BY-SA 4.0 | Hellloff233 | [Commons](https://commons.wikimedia.org/?curid=133964620) |
| clip_010 | entrevistas en una marcha, ruido de multitud | CC BY-SA 4.0 | Hellloff233 | [Commons](https://commons.wikimedia.org/?curid=133964621) |
| clip_011 | declaraciones en conferencia de prensa | CC BY-SA 4.0 | QM Keen | [Commons](https://commons.wikimedia.org/?curid=121219890) |
| clip_012 | declaraciones en conferencia de prensa | CC BY-SA 4.0 | QM Keen | [Commons](https://commons.wikimedia.org/?curid=121219891) |
| clip_013 | entrevista en una fiesta patronal (Áncash) | CC BY-SA 4.0 | Rashelley Perez | [Commons](https://commons.wikimedia.org/?curid=149433722) |
| clip_014 | entrevista en una fiesta patronal (Áncash) | CC BY-SA 4.0 | Rashelley Perez | [Commons](https://commons.wikimedia.org/?curid=149433723) |
| clip_015 | entrevista en una fiesta patronal (Áncash) | CC BY-SA 4.0 | GFSA01 | [Commons](https://commons.wikimedia.org/?curid=149445104) |
| clip_016 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Melvin Ramos Gonzales | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_El_Retablo-Comas-article2.oga) |
| clip_017 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Jhoe Pari | [Commons](https://commons.wikimedia.org/wiki/File:Huaca_Mateo_Salado%2C_cultura_Yschma_en_4_minutos_audio.ogg) |
| clip_018 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Jhon Manayay | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_Puente_Inca-article.ogg) |
| clip_019 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Ariana zafra | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_Santa_Rosa-article.ogg) |
| clip_020 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Yasser Toledo | [Commons](https://commons.wikimedia.org/wiki/File:Audio_de_la_Huaca_Sinchi_Roca.ogg) |
| clip_021 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Samanta Sahory | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_Garagay-article.ogg) |
| clip_022 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Sheyla F. Crovetto | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_El_Sauce-article.ogg) |
| clip_023 | lectura de artículo de Wikipedia | CC BY-SA 4.0 | Soto Caldas Cesar | [Commons](https://commons.wikimedia.org/wiki/File:Es-Huaca_Tambo_Inga_20-article.oga) |

</details>

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
