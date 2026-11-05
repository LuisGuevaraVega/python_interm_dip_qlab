# Evaluación: Claude Code sin y con el MCP del BCRP y las Skills de la ENAHO

## Diseño

- **10 preguntas** ([`preguntas.csv`](preguntas.csv)): 4 del BCRP, 4 de la ENAHO 2024 y 2 que combinan ambas fuentes.
- **Respuestas esperadas** fijadas antes de correr los modos, con un cálculo independiente
  ([`verdades.py`](verdades.py) → [`verdades.txt`](verdades.txt)). Las cifras del BCRP se piden directo a la API oficial,
  sin el servidor MCP, y las de la ENAHO se calculan con código propio sobre los `.dta` del INEI, sin las skills. Se
  contrastan además con las cifras publicadas por el INEI y con la referencia de la sesión 16. Tolerancia definida por
  pregunta: 0.05 pp para tasas del BCRP, 0.1 para la variación acumulada, 0.15 pp para la pobreza y 0.3 a 0.5 pp para el
  peso de los alimentos.
- **Preguntas mixtas.** Piden dos cifras (una de cada fuente) y una **categoría de interpretación**: qué grupo queda más
  expuesto a la inflación de alimentos. Solo cuentan como acierto si las tres partes son correctas; si acierta en alguna,
  es «parcial». La interpretación en texto queda en `resultados.csv` para revisar su coherencia y que no afirme
  causalidad.
- **Mismo modelo y misma instrucción en ambos modos:** Claude Sonnet (`claude -p --model sonnet`), la misma instrucción
  y el mismo esquema JSON (`valor`, `valor_2`, `categoria`, `fuente`, `interpretacion`). Cada pregunta corre en una
  **sesión nueva** (`--no-session-persistence`). La instrucción permite responder `null` («no sé») en vez de estimar.

| | Modo A, sin MCP ni Skills | Modo B, con MCP y Skills |
|---|---|---|
| Herramientas habilitadas | Ninguna (`--tools ""`), sin servidores MCP (`--strict-mcp-config`), sin skills ni comandos (`--disable-slash-commands`) | Servidor `bcrp` (`.mcp.json`), skills de `.claude/skills/`, Read, Glob, Grep, Bash solo para `uv run`/`python`/`ls`; sin web, sin PowerShell; `git` bloqueado |
| Carpeta de trabajo | Carpeta temporal vacía fuera del proyecto: no puede leer ningún archivo | El proyecto, con las respuestas apartadas (ver abajo) |
| Paralelismo | 3 preguntas a la vez | Una a la vez; antes de cada una se borran `salidas/`, `figuras/` y `mapas/` |

Para que el modo B no copiara resultados, `evaluar.py` aparta durante la prueba `evaluacion/` (preguntas, verdades y
resultados), `README.md`, `informes/`, `evidencias_ia/` y todas las salidas calculadas. Cada pregunta del modo B parte
solo de los zip del INEI, el catálogo del BCRP y el GeoJSON, y tiene que usar el MCP y las skills para producir la cifra.

## Resultados (corrida final, la 4: [`resultados.csv`](resultados.csv))

| Modo | Correctas | Parciales | Incorrectas | Sin respuesta («no sé») | Tiempo promedio | Costo total |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| A · sin MCP ni Skills | **3/10** | 0 | 0 | 7 | 7.2 s | US$ 0.11 |
| B · con MCP y Skills | **10/10** | 0 | 0 | 0 | 32.5 s | US$ 0.90 |

| Pregunta | Esperado | Modo A | Modo B | Herramientas que usó el modo B |
|---|---|---|---|---|
| Inflación 12 meses, dic. 2024 | 1.97 % | ✅ 1.97 (memoria) | ✅ 1.97 | `transformar` |
| Pico de la inflación 2020-2024 | 8.81 % | ✅ 8.81 (memoria) | ✅ 8.81 (2022-06) | `buscar_series`, `resumen` |
| Alimentos y bebidas 12 meses, feb. 2023 | 13.16 % | ❔ no sabe | ✅ 13.16 | `buscar_series`, `serie`, `transformar` |
| Alimentos acumulado dic. 2019-dic. 2024 | 31.94 % | ❔ no sabe | ✅ 31.94 | `buscar_series`, `resumen` |
| Pobreza nacional 2024 | 27.58 % | ✅ 27.6 (memoria) | ✅ 27.58 | skill `limpiando-enaho` |
| Pobreza rural 2024 | 39.30 % | ❔ no sabe | ✅ 39.30 | skill `limpiando-enaho` |
| Pobreza de Cajamarca 2024 | 45.01 % | ❔ no sabe | ✅ 45.01 | skill `limpiando-enaho` |
| Pobreza de 0 a 14 años | 37.52 % | ❔ no sabe | ✅ 37.50 | skill `limpiando-enaho` + cálculo ponderado `facpob07` |
| Mixta: brecha alimentos − total y peso de los alimentos en pobres extremos | 8.03 pp · 49.25 % · pobres extremos | ❔ no sabe | ✅ 8.03 · 49.27 · pobres extremos | `comparar_series` + skill `limpiando-enaho` |
| Mixta: alza anual de alimentos y brecha rural − urbana del peso de los alimentos | 5.70 % · 14.35 pp · rural | ❔ no sabe (eligió «rural» sin cifras) | ✅ 5.70 · 14.35 · rural | `resumen`, `serie` + script de `limpiando-enaho` |

**Preguntas que mejoraron:** 7 de 10 (las que el modo A no sabía). **Empeoraron:** ninguna. Las 3 que el modo A acertó
son cifras muy publicadas (la inflación de cierre de 2024, el pico de 2022 y la pobreza nacional): las recuerda. Pero
la pobreza nacional la dio como 27.6 «de memoria», sin poder decir de dónde exactamente; el modo B la calculó (27.58).

**Interpretación de las mixtas.** En ambas el modo B eligió el grupo correcto y lo sustentó con las cifras, sin afirmar
causalidad. En la primera escribió que los pobres extremos destinan «cerca de la mitad de su gasto (49.27 %) a alimentos,
frente a 33.26 % de los no pobres, así que son los más expuestos a esa alza. Es una asociación descriptiva, no causal.
La ENAHO es nacional y el IPC es de Lima». El modo A eligió «rural» en la segunda por razonamiento general («destinan
una parte mayor del gasto a alimentos»), pero sin ninguna cifra que lo sustente: por eso cuenta como «no sabe».

## Cómo llegamos al diseño final: cuatro corridas

El experimento se corrió cuatro veces. Cada corrida reveló un atajo del modo B, que se cerró en la siguiente. Los
resultados de las cuatro están en [`resultados_corrida1.csv`](resultados_corrida1.csv) a [`resultados.csv`](resultados.csv)
y los registros completos de las corridas 2 a 4, pregunta por pregunta, en
[`evidencias_ia/evaluacion/`](../evidencias_ia/evaluacion/).

| Corrida | Modo A | Modo B | Qué se descubrió y qué se cambió |
|---|:---:|:---:|---|
| 1 | 3 ✅ · 7 ❔ | 10 ✅ | El modo B respondió la ENAHO **leyendo `salidas/indicadores.csv`**, ya calculado, sin cargar ninguna skill. → Se apartan las tablas, figuras y mapas |
| 2 | 3 ✅ · 1 ❌ · 6 ❔ | 8 ✅ · 2 ½ | Tomó la pobreza rural **del borrador del README**. Las dos mixtas quedaron a medias: quiso calcular con **PowerShell**, que pedía permiso y se bloqueó. Intentó `git show` para leer versiones guardadas. → Se aparta el README y toda `salidas/`, se quita PowerShell y se bloquea git |
| 3 | 3 ✅ · 7 ❔ | 9 ✅ · 1 ½ | Copió cifras de la **documentación de la skill** (`reference.md`, el CSV de referencia de la sesión 16). Cuando quiso calcular, usó `.venv/Scripts/python.exe` y no `uv run`, y se le negó. → Se agrega a la instrucción común «úsalas para calcular la cifra a partir de los datos; no copies cifras de documentación», se permite el Python del entorno y se aparta `verdades.py` |
| **4 (final)** | **3 ✅ · 7 ❔** | **10 ✅** | Las 6 preguntas que necesitan la ENAHO se calcularon desde los microdatos: 5 cargando la skill `limpiando-enaho` y 1 siguiendo su `SKILL.md` y corriendo su script |

El modo A fue estable en las cuatro corridas: 3 aciertos y, salvo un error en la corrida 2 (pobreza rural 39.8 % en vez
de 39.3 %), reconoce que no sabe en vez de inventar.

## Principales errores encontrados

1. **Sin herramientas, Claude no inventa, pero tampoco responde.** El modo A dijo «no sé» en 7 de 10, porque la
   instrucción le da esa salida. La única vez que estimó (corrida 2) se equivocó por medio punto.
2. **Con herramientas, el agente busca el camino más corto.** Si encuentra la cifra escrita en algún archivo (tablas ya
   calculadas, el README, la documentación de la skill), la copia en vez de calcularla. La respuesta es correcta, pero no
   demuestra que el sistema funciona. Eso obligó a aislar el experimento.
3. **Los permisos importan tanto como las herramientas.** En la corrida 2 las mixtas fallaron porque el modelo eligió
   una herramienta sin permiso (PowerShell), no porque le faltara el dato. En la corrida 3 pasó lo mismo con el Python
   del entorno.
4. **Las skills no siempre se cargan solas.** Con la base ya procesada, el modelo prefería calcular directamente. Sin
   base, en la corrida 4 sí cargó `limpiando-enaho` en 5 de 6 preguntas de la ENAHO.

## Tiempo

El modo B tarda **4.5 veces más** (32.5 s frente a 7.2 s en promedio): 25 s las del BCRP, 31 s las de la ENAHO (incluye
procesar 108,664 personas desde los zip) y 50 s las mixtas. Cuesta unas 8 veces más (US$ 0.90 frente a 0.11 las 10
preguntas).

## Conclusión

El MCP y las Skills **mejoraron la exactitud de 3/10 a 10/10**: 7 preguntas que Claude no podía responder pasaron a
respuestas correctas, cada una con su código de serie o su archivo de origen, y ninguna empeoró. La ganancia se
concentra en lo que no está en la memoria del modelo: cifras de meses o departamentos específicos, variaciones
acumuladas y cualquier dato de la ENAHO que no sea el titular nacional. El costo es tiempo (4.5 veces) y dinero. La
lección metodológica es que, para medir el aporte de las herramientas, hay que impedir que el agente encuentre la
respuesta ya escrita: sin ese aislamiento, el 10/10 de la corrida 1 medía la lectura de archivos, no el sistema.
