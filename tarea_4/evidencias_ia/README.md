# Evidencias del uso de inteligencia artificial

Todo el proyecto se desarrolló conversando con **Claude Code** (CLI, modelo Claude Opus) en una sola sesión, el 5 de
noviembre de 2026. Las ejecuciones del agente y de la evaluación usaron Claude Code en modo no interactivo
(`claude -p`) con Claude Sonnet. Antes de publicar, `scripts/exportar_conversaciones.py` reemplazó correos, claves con
formato conocido y la carpeta del usuario de Windows; el razonamiento interno del modelo no se exporta.

| Carpeta | Qué hay | Etapa |
|---|---|---|
| [`conversaciones/`](conversaciones/) | La sesión de desarrollo completa: [`.md` legible](conversaciones/7cafa22b-3eb1-4c02-93af-a5c7f5f482bd.md) (pedidos, respuestas, cada herramienta con sus argumentos y resultados) y el `.jsonl` original | Todas: lectura del enunciado, servidor MCP, skills, integración, pruebas, correcciones, evaluación e informe |
| [`mcp/`](mcp/) | `pruebas.txt`: `pytest -v` con 10 passed y la comprobación de que `test_server.py` es idéntico al de la sesión 04 | Parte 1 |
| [`skills/`](skills/) | `validacion.txt` (23/23) y `comparacion_mapa.csv` (25/25 contra la sesión 16) | Parte 2 |
| [`integracion/`](integracion/) | Cada ejecución del agente: registro `stream-json` completo y bitácora legible con cada herramienta MCP y skill en orden; `ejecuciones.csv` las resume | Partes 2 y 3 |
| [`evaluacion/`](evaluacion/) | El registro de cada una de las 10 preguntas en cada modo, corridas 2 a 4 (la 1 solo dejó `resultados_corrida1.csv`) | Parte 4 |

## Las ejecuciones del agente

| Bitácora | Qué demuestra |
|---|---|
| [`skills_mapa_sin_base`](integracion/skills_mapa_sin_base_bitacora.md) | Con la base apartada, «Haz un mapa de la pobreza monetaria por departamento con ENAHO 2024» activa `mapeando-enaho`, que llama primero a `limpiando-enaho` |
| [`investigacion_intento1`](integracion/investigacion_intento1_bitacora.md) | **Intento descartado:** el agente usó 4 herramientas MCP pero leyó salidas de pruebas anteriores en vez de invocar las skills. Su informe quedó en [`informe_intento1.md`](integracion/informe_intento1.md) |
| [`investigacion_final`](integracion/investigacion_final_bitacora.md) | **La ejecución del informe final:** desde cero, 3 herramientas MCP (`comparar_series`, `resumen`, `grafico`), el recurso `bcrp://series-clave` y 3 skills (`limpiando-enaho`, `graficando-enaho`, `mapeando-enaho`) |
| [`skill_invocada_directo`](integracion/skill_invocada_directo_bitacora.md) | Una skill invocada individualmente con su comando: `/graficando-enaho sexo` ejecuta su script y devuelve el gráfico por sexo |
| [`mcp_prompt_y_recurso`](integracion/mcp_prompt_y_recurso_bitacora.md) | El prompt MCP `/mcp__bcrp__interpretar_inflacion` invocado desde Claude Code, que lee el recurso y llama a dos herramientas |

## Correcciones registradas en la conversación

- La primera sumaria encontrada en el zip era la de 12 grupos: la lectura pasó a buscar el nombre exacto.
- La pobreza por departamento con `facpob07` difería hasta 0.5 pp de la referencia; se adoptó el método INEI
  (`factor07 × mieperho`) para lo territorial, y entonces la referencia coincidió en los 25.
- Ajustes de los gráficos y del mapa después de revisarlos como imagen: títulos cortados, cifras sobre la línea
  punteada, rótulos de Callao y Lima en el recuadro.
- El primer intento del agente no invocó las skills: se agregó `--limpio` a `ejecutar_agente.py`.
- La evaluación se corrió cuatro veces hasta aislar el modo B de las respuestas ya escritas
  ([`evaluacion/comparacion.md`](../evaluacion/comparacion.md)).
- Un archivo escrito en `informes/` mientras corría la evaluación pudo quedar visible para el modo B: se retiró, y la
  corrida afectada (la 1) se repitió con un diseño más estricto.
