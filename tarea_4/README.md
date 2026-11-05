# Tarea 4 · Agente de investigación socioeconómica: MCP del BCRP + Skills de la ENAHO

**Pregunta de investigación:** ¿Cuánto subieron los precios de los alimentos frente al resto de la canasta en Lima
Metropolitana entre 2020 y 2024, y qué tan expuestos estaban a esa alza —por el peso de los alimentos en su gasto—
los hogares pobres, rurales y de cada departamento del Perú en 2024?

**Informe final:** [`informes/informe_final.md`](informes/informe_final.md) · **Verificación de cifras:**
[`informes/verificacion_cifras.md`](informes/verificacion_cifras.md) · **Evaluación:**
[`evaluacion/comparacion.md`](evaluacion/comparacion.md)

Curso Python Intermedio (QLab, PUCP), Tarea 4 ([enunciado: issue #201](https://github.com/d2cml-ai/Data-Science-Python/issues/201)).

## 1. Objetivo

Construir un agente con Claude Code que **no responda de memoria**: que consulte series oficiales del BCRP con un
servidor MCP propio, procese los microdatos de la ENAHO 2024 del INEI con tres Skills que validan cada paso, y escriba
un informe en el que cada cifra se puede rastrear hasta la herramienta, el archivo o la serie de donde salió. Después,
medir si el MCP y las Skills mejoran las respuestas frente a Claude Code sin ellos.

## 2. Arquitectura

```text
                         pregunta en lenguaje natural
                                     │
                         ┌───────────▼────────────┐
                         │  Claude Code (agente)  │  plan → herramientas → informe
                         └──┬──────────────────┬──┘
           MCP (stdio, .mcp.json)              Skills (.claude/skills/)
   ┌──────────────▼──────────────┐   ┌──────────────────▼───────────────────────────┐
   │ mcp/server.py (FastMCP)     │   │ limpiando-enaho → salidas/*.parquet,          │
   │ buscar_series · serie ·     │   │                   validacion.txt, indicadores │
   │ resumen · transformar ·     │   │ graficando-enaho → figuras/enaho_*.png + .csv │
   │ comparar_series · grafico   │   │ mapeando-enaho  → mapas/mapa_*.png + .csv     │
   │ recursos · prompts          │   │ (gráficos y mapas llaman a limpieza si falta) │
   └──────────────┬──────────────┘   └──────────────────┬───────────────────────────┘
        API del BCRP (JSON)               datos/966-Modulo34.zip, 966-Modulo02.zip,
     estadisticas.bcrp.gob.pe             GeoJSON departamental del curso
                                     │
                    informes/informe_final.md  (+ bitácora de la ejecución)
```

Las cuentas las hace Python, no el modelo: el MCP devuelve variaciones y extremos ya calculados, y las Skills corren
siempre el mismo script, que se detiene si una validación esencial falla.

## 3. Servidor MCP del BCRP (`mcp/server.py`)

Basado en el proyecto de la sesión 04 y en mi servidor [bcrp-mcp](https://github.com/LuisGuevaraVega/bcrp-mcp).

| Tipo | Nombre | Qué hace |
|---|---|---|
| Herramienta | `buscar_series` | Busca entre las ~17 mil series del catálogo oficial por palabras (sin tildes), prioriza las vigentes |
| Herramienta | `serie` | Descarga una serie entre dos fechas (diaria, mensual, trimestral o anual), con la URL de la fuente y avisos si está descontinuada o no llega a lo pedido |
| Herramienta | `resumen` | Primero, último, cambio, variación %, promedio, máximo y mínimo con su periodo |
| Herramienta | `transformar` | Variación interanual, mensual o acumulada, promedio anual, índice base 100 o valores reales |
| **Herramienta propia** | **`comparar_series`** | Compara 2 a 5 índices **en los mismos periodos**: los alinea y descarta faltantes (y lo dice), calcula la variación acumulada y la promedio anual geométrica de cada uno, la **brecha en pp** frente a la primera serie y la correlación de sus variaciones. Rechaza tasas (var%) y frecuencias distintas con un error claro |
| Herramienta | `grafico` | Guarda en `figuras/` un PNG de hasta 5 series con fuente y fecha |
| Recurso | `bcrp://serie/{codigo}` | Ficha de una serie: nombre, frecuencia, inicio, última actualización |
| Recurso | `bcrp://series-clave` | Las series de precios del proyecto (IPC total, alimentos y bebidas, sin alimentos…) |
| Prompt | `informe(tema)` | Informe breve con cifras citadas por código y periodo |
| Prompt | `interpretar_inflacion(desde, hasta)` | Interpreta alimentos frente al resto con `comparar_series` y `resumen`, sin afirmar causalidad |

**Pruebas:** `mcp/test_server.py` son las 8 pruebas originales **sin cambios** (idéntico byte a byte al de la sesión
04); `mcp/test_comparar_series.py` son las 2 propias: (1) la variación acumulada y la brecha de `comparar_series`
coinciden con una cuenta independiente hecha con los datos crudos de `serie`; (2) rechaza una tasa, frecuencias
distintas y un código inexistente. Resultado: **10 passed** ([`evidencias_ia/mcp/pruebas.txt`](evidencias_ia/mcp/pruebas.txt)).

## 4. Skills de la ENAHO (`.claude/skills/`)

| Skill | Qué hace | Salida |
|---|---|---|
| [`limpiando-enaho`](.claude/skills/limpiando-enaho/SKILL.md) | Lee los `.dta` dentro de los zip con llaves como texto, normaliza nombres, filtra residentes habituales `((p204==1)&(p205==2))\|((p204==2)&(p206==1))`, une personas→hogares con `merge(validate="m:1")`, construye departamento (`ubigeo[:2]`), área (`estrato<=5`), pobreza y peso de los alimentos en el gasto, y valida. Si una validación esencial falla, sale con error y no escribe la base | `salidas/personas_2024.parquet`, `hogares_2024.parquet`, `indicadores.csv`, [`validacion.txt`](salidas/validacion.txt) |
| [`graficando-enaho`](.claude/skills/graficando-enaho/SKILL.md) | Gráficos ponderados por área, sexo, edad, departamento, dominio y peso de los alimentos; título con el hallazgo, unidades, fuente y ponderador; deja al lado un `.csv` con los valores dibujados | `figuras/enaho_*.png` |
| [`mapeando-enaho`](.claude/skills/mapeando-enaho/SKILL.md) | Coroplético departamental (pobreza, pobreza extrema o peso de los alimentos) unido por `ubigeo[:2]` = `FIRST_IDDP` con `validate="one_to_one"`; exige 25 unidades, Lima y Callao separados (recuadro ampliado); compara con la referencia de la sesión 16 | `mapas/mapa_*_departamento.png`, `salidas/comparacion_mapa.csv` |

**Ponderación.** La pobreza territorial (nacional, área, departamento) usa el método del INEI: hogares de la sumaria
ponderados por `factor07 × mieperho`. Las características de la persona (sexo, edad) usan residentes habituales con
`facpob07`. Los dos métodos están en `indicadores.csv` y se explican en
[`reference.md`](.claude/skills/limpiando-enaho/reference.md).

**Validación ENAHO 2024** ([`salidas/validacion.txt`](salidas/validacion.txt), 23/23 aprobadas):

| Indicador | Calculado | Referencia |
|---|---|---|
| Pobreza monetaria nacional | **27.58 %** (método INEI) · 27.53 % (`facpob07`) | 27.6 % (±0.1) |
| Residentes habituales | **108,664** | 108,664 |
| Unidades territoriales | **25/25**, las 25 a 0.00 pp de la sesión 16 | 25 |
| Pobreza urbana / rural | 24.81 % / 39.30 % | 24.8 % / 39.3 % |
| Pobreza extrema | 5.50 % | 5.5 % |
| Promedio simple sin factores (no se usa) | 25.61 % | — |

**Coordinación.** Las skills de gráficos y mapas comprueban si existe la base; si no, activan primero
`limpiando-enaho`. Ejemplo real: con la base apartada, el pedido *«Haz un mapa de la pobreza monetaria por
departamento con ENAHO 2024»* activó `mapeando-enaho` → `limpiando-enaho` → mapa (25/25)
([bitácora](evidencias_ia/integracion/skills_mapa_sin_base_bitacora.md)). También se invocan individualmente:
`/graficando-enaho sexo` ([bitácora](evidencias_ia/integracion/skill_invocada_directo_bitacora.md)); y en la
ejecución del informe el agente cargó las tres, una por una, con la herramienta Skill.

## 5. Fuentes y descarga de datos

| Fuente | Archivo | Enlace |
|---|---|---|
| INEI, ENAHO 2024, módulo 34 (sumaria) | `datos/966-Modulo34.zip` (16 MB) | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip |
| INEI, ENAHO 2024, módulo 02 (miembros) | `datos/966-Modulo02.zip` (6 MB) | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip |
| Límites departamentales (curso) | `datos/peru_departamental_simple.geojson` | https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson |
| BCRP, series estadísticas | API JSON (sin clave) y catálogo `datos/catalogo_bcrp.csv` | https://estadisticas.bcrp.gob.pe/estadisticas/series/ |

`datos/` está en `.gitignore`: no se suben microdatos. `limpiar.py --descargar` baja los zip del INEI; el GeoJSON y el
catálogo del BCRP se bajan solos la primera vez.

## 6. Instalación con `uv`

```bash
git clone https://github.com/LuisGuevaraVega/python_interm_dip_qlab
cd python_interm_dip_qlab/tarea_4
uv sync                      # Python ≥ 3.11, fastmcp 4, pandas, pyarrow, geopandas, matplotlib, pytest
```

## 7. Conectar el MCP a Claude Code

El servidor ya está declarado en [`.mcp.json`](.mcp.json) (`uv run mcp/server.py`, por stdio). Abran `claude` dentro
de `tarea_4/` y aprueben el servidor `bcrp`; `/mcp` debe mostrarlo conectado con 6 herramientas. Para agregarlo a
mano: `claude mcp add --scope project bcrp -- uv run mcp/server.py`. Pruebas rápidas dentro de Claude Code:

- Recurso: `@bcrp:bcrp://series-clave ¿qué series de precios tiene el proyecto?`
- Prompt: `/mcp__bcrp__interpretar_inflacion 2019-12 2024-12`
- Skills: `/skills` lista las tres; `/mapeando-enaho gasto_alimentos` la llama directamente.

Demostración registrada: `/mcp__bcrp__interpretar_inflacion 2019-12 2024-12` desde `claude -p` usó el prompt, leyó el
recurso `bcrp://series-clave` y llamó a `comparar_series` y `resumen`
([bitácora](evidencias_ia/integracion/mcp_prompt_y_recurso_bitacora.md)).

## 8. Reproducir el procesamiento y las pruebas

**Interfaz web (la forma más amigable de usarlo):** `uv run streamlit run app/app.py` abre en el navegador una app con cinco pestañas: un **chat con el agente** (muestra en vivo cada herramienta MCP y skill que usa, y los gráficos que genera; requiere Claude Code con sesión iniciada), **precios del BCRP en vivo**, **pobreza de la ENAHO** con gráficos y mapa interactivos, la **evaluación** y el **informe**.

**Demo guiada (recomendada para empezar):** `uv run scripts/demo.py` recorre en ~2 minutos las pruebas, el MCP por dentro, la limpieza validada, un gráfico, un mapa y una pregunta al agente que usa el MCP y una skill (pausa con Enter entre pasos; `--sin-agente` omite la llamada a Claude, `--sin-pausas` la corre de seguido).

```bash
uv run pytest                                                         # 10 passed
uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --descargar  # bases + validacion.txt
uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo todos
uv run .claude/skills/mapeando-enaho/scripts/mapear.py                # pobreza (compara con la sesión 16)
uv run .claude/skills/mapeando-enaho/scripts/mapear.py --indicador gasto_alimentos

# el agente completo, desde cero (aparta las salidas previas fuera del proyecto)
uv run scripts/ejecutar_agente.py --nombre investigacion_final --limpio --prompt-archivo agente/pregunta_investigacion.md

# la evaluación
uv run evaluacion/verdades.py      # respuestas esperadas, sin MCP ni skills
uv run evaluacion/evaluar.py       # 10 preguntas × 2 modos -> evaluacion/resultados.csv
```

## 9. Resultados de la evaluación

10 preguntas (4 BCRP, 4 ENAHO, 2 mixtas) con respuestas esperadas calculadas sin el MCP ni las skills
([`verdades.py`](evaluacion/verdades.py)), las mismas para dos modos de `claude -p` con Sonnet, una sesión nueva por
pregunta. Detalle y análisis en [`evaluacion/comparacion.md`](evaluacion/comparacion.md); datos en
[`evaluacion/resultados.csv`](evaluacion/resultados.csv).

| Modo | Correctas | Incorrectas | «No sé» | Tiempo promedio |
|---|:---:|:---:|:---:|:---:|
| A · sin MCP ni Skills (sin herramientas, carpeta vacía) | **3/10** | 0 | 7 | 7.2 s |
| B · con MCP y Skills (respuestas y salidas previas apartadas) | **10/10** | 0 | 0 | 32.5 s |

Mejoraron 7 preguntas y no empeoró ninguna. El modo A solo acierta las cifras muy publicadas; el B calcula las demás con
`comparar_series`, `resumen`, `serie` y `transformar`, y con la skill `limpiando-enaho` desde los microdatos. Se
necesitaron **cuatro corridas** para aislar el experimento: en las primeras el modo B copiaba cifras ya escritas (tablas
calculadas, el README, la documentación de la skill). Cada atajo y su corrección están en `comparacion.md`.

## 10. Limitaciones y problemas encontrados

- **Cobertura distinta de las fuentes.** El IPC del BCRP es de Lima Metropolitana; la ENAHO es nacional y de un solo
  año. El informe describe una asociación (dónde pesan más los alimentos), no el efecto de la inflación sobre la
  pobreza.
- **Dos métodos de ponderación.** `facpob07` sobre residentes da 27.53 % y difiere hasta 0.5 pp por departamento del
  método INEI (`factor07 × mieperho`), que reproduce exactamente la referencia. Se usa cada uno según la unidad de
  análisis y ambos están documentados.
- **Primer intento del agente descartado.** Con salidas de pruebas anteriores en el proyecto, el agente las leyó en
  vez de invocar las skills. Se agregó `--limpio` a `scripts/ejecutar_agente.py` (aparta las salidas fuera del
  proyecto) y una regla en el pedido; la segunda ejecución usó 3 skills y 3 herramientas MCP.
- **El zip del módulo 34 trae dos sumarias** (`sumaria-2024.dta` y `sumaria-2024-12g.dta`): la lectura busca el nombre
  exacto.
- **Límite de pedidos del BCRP:** si la API responde HTML en vez de JSON, el servidor reintenta con espera y guarda en
  caché lo descargado.
- **Error muestral** de las cifras departamentales no reportado (la ENAHO tiene diseño complejo; se reportan
  estimaciones puntuales).

## 11. Ejemplo de una ejecución completa

`scripts/ejecutar_agente.py --limpio` con el pedido de [`agente/pregunta_investigacion.md`](agente/pregunta_investigacion.md)
([bitácora completa](evidencias_ia/integracion/investigacion_final_bitacora.md), 95 s, 19 turnos, Sonnet):

| Paso | Herramienta | Qué produjo |
|---|---|---|
| 1 | Plan en texto | Qué dato de cada fuente y con qué herramienta |
| 2 | Skill `limpiando-enaho` → `limpiar.py` | Bases y validación 23/23 |
| 3 | MCP: recurso `bcrp://series-clave` | Códigos de las series de precios |
| 4 | MCP `comparar_series` (PN38705PM, PN39445PM, PN38706PM) | Alimentos +31.94 %, total +23.91 %, resto +18.69 % (dic. 2019-dic. 2024) |
| 5 | MCP `resumen` ×2 (PN01273PM, PN09822PM) | Picos: 8.81 % (jun. 2022) y 13.16 % (feb. 2023) |
| 6 | MCP `grafico` | `figuras/bcrp_PN01273PM_PN09822PM_niveles_2020-01_2024-12.png` |
| 7 | Skill `graficando-enaho` | Peso de los alimentos y pobreza por área |
| 8 | Skill `mapeando-enaho` | Mapas de pobreza (25/25 contra la sesión 16) y del peso de los alimentos |
| 9 | Write | `informes/informe_final.md` con 9 hallazgos y tabla de trazabilidad |

## 12. Evidencias del uso de IA

Todo el proyecto se desarrolló con **Claude Code** (Opus como asistente de desarrollo; Sonnet como modelo del agente y
de la evaluación). En [`evidencias_ia/`](evidencias_ia/):

| Carpeta | Contenido |
|---|---|
| [`conversaciones/`](evidencias_ia/conversaciones/) | Exportación completa de la sesión de desarrollo (Markdown legible + JSONL), con correo, claves y rutas personales ocultos (`scripts/exportar_conversaciones.py`) |
| [`mcp/`](evidencias_ia/mcp/) | Salida de `pytest` (10 passed) |
| [`skills/`](evidencias_ia/skills/) | Validación de la ENAHO y comparación del mapa con la sesión 16 |
| [`integracion/`](evidencias_ia/integracion/) | Registro stream-json y bitácora legible de cada ejecución del agente, incluido el intento descartado |
| [`evaluacion/`](evidencias_ia/evaluacion/) | Salida de la evaluación en ambos modos |
