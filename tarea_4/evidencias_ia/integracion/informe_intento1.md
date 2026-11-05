# Precios de los alimentos y exposición de los hogares peruanos, 2020-2024

## 1. Pregunta de investigación

**Tema.** Inflación de alimentos y peso de los alimentos en el gasto de los hogares.

**Pregunta.** ¿Cuánto subieron los precios de los alimentos frente al resto de la canasta en Lima Metropolitana entre 2020 y 2024? ¿Qué tan expuestos estaban a esa alza, por el peso de los alimentos en su gasto, los hogares pobres, rurales y de cada departamento en 2024?

**Objetivo.** Combinar una fuente de precios (BCRP) con una de hogares (ENAHO 2024) para describir quiénes destinan una mayor parte de su gasto a los alimentos.

**Delimitación.**

- Periodo de precios: dic. 2019 a dic. 2024, mensual.
- Territorio de precios: Lima Metropolitana.
- Periodo de hogares: ENAHO 2024.
- Territorio de hogares: Perú, con desagregación urbano/rural, condición de pobreza y 25 departamentos (Lima y Callao separados).
- Unidad de análisis: índices de precios (BCRP) y personas, o los hogares a los que pertenecen (ENAHO).

## 2. Fuentes y metodología

**BCRP (servidor MCP `bcrp`, series mensuales, API de estadísticas del BCRP).**

| Código | Serie |
|---|---|
| PN38705PM | IPC Lima Metropolitana, total (índice dic. 2021 = 100) |
| PN39445PM | IPC Alimentos y Bebidas (índice dic. 2021 = 100) |
| PN38706PM | IPC Sin Alimentos y Bebidas (índice dic. 2021 = 100) |
| PN01273PM | IPC total, var. % 12 meses |
| PN09822PM | IPC Alimentos y Bebidas, var. % 12 meses |

Herramientas usadas: `comparar_series`, `resumen` y `grafico`. Las variaciones, brechas y extremos las calculó el servidor, no yo.

**ENAHO 2024 (INEI, código 966).**

- Módulo 34 (sumaria): pobreza monetaria, gasto total y gasto en alimentos, área y departamento.
- Módulo 02 (miembros): sexo, edad y residencia habitual.
- Procesamiento: skills `limpiando-enaho`, `graficando-enaho` y `mapeando-enaho`.

**Ponderadores.** Siempre ponderado.

- Pobreza por el método INEI: `factor07 × mieperho`, sobre hogares de la sumaria.
- Características de personas: `facpob07`.
- Sin ponderar, la pobreza nacional sería 25.61 % frente a 27.58 % ponderada (validacion.txt).

**Definiciones.**

- *Peso de los alimentos* (`gasto_alimentos_pct`): porcentaje del gasto total del hogar que se destina a alimentos.
- *Pobreza monetaria*: según la definición del INEI incluida en la sumaria.

**Validación.** `salidas/validacion.txt` registra 23 pruebas aprobadas, 0 fallidas y 0 advertencias.

## 3. Resultados

**Hallazgo 1. Los alimentos subieron más que el resto de la canasta.**

- Entre dic. 2019 y dic. 2024 el IPC de alimentos y bebidas acumuló **+31.94 %** (PN39445PM, 2019-12 a 2024-12).
- El IPC total acumuló **+23.91 %** (PN38705PM, mismo periodo).
- El IPC sin alimentos y bebidas acumuló **+18.69 %** (PN38706PM, mismo periodo).
- La brecha de alimentos frente al total es de **+8.03 pp**. Frente al resto de la canasta, la brecha total es de **−5.22 pp** a favor de esta última (`comparar_series`, brecha_vs_referencia_pp, referencia PN38705PM).
- Promedio anual: 5.70 % para alimentos y 4.38 % para el total (PN39445PM y PN38705PM).

**Hallazgo 2. El pico de la inflación de alimentos fue mayor y más tardío que el del total.**

- Inflación interanual total: máximo de **8.81 %** en jun. 2022 (PN01273PM, 2020-01 a 2024-12).
- Inflación interanual de alimentos y bebidas: máximo de **13.16 %** en feb. 2023 (PN09822PM, 2020-01 a 2024-12).
- En dic. 2024 las tasas ya eran bajas: 1.97 % el total (PN01273PM) y 1.25 % alimentos (PN09822PM). El mínimo de alimentos fue 0.69 % en sep. 2024 (PN09822PM).
- Aunque la inflación se moderó, el **nivel** de precios de los alimentos no bajó, por lo que la alza acumulada del hallazgo 1 se mantiene.

**Hallazgo 3. Los hogares pobres y rurales destinan una mayor parte de su gasto a alimentos.**

- Nacional: **36.41 %** del gasto (`salidas/indicadores.csv`, gasto_alimentos_pct, Nacional).
- Rural **48.03 %** y urbano **33.69 %** (indicadores.csv, gasto_alimentos_pct, Área).
- Pobres extremos **49.27 %**, pobres no extremos **43.58 %** y no pobres **33.26 %** (indicadores.csv, gasto_alimentos_pct, Condición de pobreza).
- Lima Metropolitana (dominio) **30.00 %**, el valor más bajo entre los dominios geográficos (indicadores.csv, gasto_alimentos_pct, Dominio).

**Hallazgo 4. La pobreza es mayor en el área rural.**

- Pobreza nacional **27.58 %**, urbana **24.81 %** y rural **39.30 %** (indicadores.csv, pobreza_inei_pct).
- Pobreza extrema: urbana **3.14 %** y rural **15.52 %** (`figuras/enaho_area.csv`, pct_extrema).

**Hallazgo 5. Hay una gran dispersión entre departamentos.**

*Peso de los alimentos* (indicadores.csv, gasto_alimentos_pct):

| Posición | Departamentos |
|---|---|
| Más alto | Apurímac 47.05 %, Puno 45.09 %, Loreto 44.96 %, Cajamarca 44.20 % |
| Más bajo | Lima 30.25 %, Moquegua 31.44 %, Callao 32.81 % |

*Pobreza* (indicadores.csv, pobreza_inei_pct):

| Posición | Departamentos |
|---|---|
| Más alta | Cajamarca 45.01 %, Loreto 42.97 %, Puno 39.94 % |
| Más baja | Ica 6.01 %, Moquegua 10.97 %, Madre de Dios 11.15 % |

## 4. Visualizaciones

**Gráfico BCRP.**

![Inflación a 12 meses, total y alimentos](../figuras/bcrp_PN01273PM_PN09822PM_niveles_2020-01_2024-12.png)

*Lectura:* la inflación de alimentos supera a la total en casi todo 2021-2023 y llega a 13.16 % en feb. 2023. Desde fines de 2023 cae por debajo de la total.

**Gráfico ENAHO (peso de los alimentos en el gasto).**

![Peso de los alimentos en el gasto](../figuras/enaho_alimentos.png)

*Lectura:* el peso de los alimentos aumenta de 33.26 % en hogares no pobres a 49.27 % en pobres extremos, y es de 48.03 % en el área rural.

**Gráfico ENAHO (pobreza urbana y rural).**

![Pobreza urbana y rural](../figuras/enaho_area.png)

*Lectura:* la pobreza rural (39.30 %) es mayor que la urbana (24.81 %), y la brecha es aún mayor en pobreza extrema.

**Mapa departamental.**

![Mapa de pobreza por departamento](../mapas/mapa_pobreza_departamento.png)

*Lectura:* la pobreza se concentra en Cajamarca, Loreto y Puno, y es baja en la costa sur, Ica y Moquegua.

## 5. Interpretación

Las dos fuentes muestran juntas el siguiente patrón. Entre 2019 y 2024 los alimentos se encarecieron más que el resto de la canasta en Lima Metropolitana. En 2024, los hogares pobres, los rurales y los de varios departamentos pobres como Cajamarca, Loreto y Puno destinan una mayor parte de su gasto a los alimentos. Por tanto, un alza de precios de alimentos pesa más en la canasta de esos hogares que en la de los hogares no pobres o de Lima.

Esto es una **asociación descriptiva**, no causal. No se estima el efecto de la inflación sobre la pobreza ni sobre el bienestar.

## 6. Limitaciones

- **Territorio distinto.** El IPC es de Lima Metropolitana y la ENAHO es nacional. Los precios de los alimentos en otras ciudades y en el ámbito rural pueden haber evolucionado de otra forma.
- **Un solo año.** La ENAHO 2024 es un corte transversal. No muestra cómo cambió el peso de los alimentos entre 2020 y 2024.
- **Peso y exposición.** El peso de los alimentos en el gasto no mide por sí solo el impacto de la inflación. Falta la composición de la canasta, la autoproducción, las transferencias y la capacidad de sustitución.
- **Muestra departamental.** Algunos departamentos tienen muestras pequeñas (por ejemplo, Madre de Dios con 603 hogares y Pasco con 865), por lo que sus estimaciones son menos precisas.
- **Dos versiones del peso por departamento.** `mapas/mapa_gasto_alimentos_departamento.csv` da valores algo distintos de `salidas/indicadores.csv` (por ejemplo, Apurímac 46.59 frente a 47.05). Aquí se usa `indicadores.csv`; no verifiqué la causa de la diferencia.
- **Archivo ausente.** `salidas/personas_2024.parquet` no existe en la carpeta, aunque `indicadores.csv`, `comparacion_mapa.csv` y la validación sí están. No se pudo reabrir la base de personas para comprobaciones adicionales.
- **Alimentos y bebidas.** La serie del BCRP incluye bebidas, mientras que la ENAHO mide gasto en alimentos. Las definiciones no coinciden exactamente.

**Contraste con referencias oficiales.**

- Pobreza nacional: 27.58 % calculado frente a 27.6 % de referencia (INEI), diferencia de 0.02 pp.
- Pobreza urbana: 24.81 % frente a 24.8 %, diferencia de 0.01 pp.
- Pobreza rural: 39.30 % frente a 39.3 %, diferencia de 0.00 pp.
- Departamentos: los 25 coinciden con la referencia (`salidas/comparacion_mapa.csv`, columna `coincide` = True).

## 7. Reproducibilidad

**Archivos de salida.**

- `salidas/validacion.txt`, `salidas/indicadores.csv`, `salidas/comparacion_mapa.csv`.
- `figuras/enaho_*.png` y `.csv`, `mapas/mapa_*.png` y `.csv`.
- `figuras/bcrp_PN01273PM_PN09822PM_niveles_2020-01_2024-12.png`.

**Comandos del servidor MCP `bcrp`.**

- `comparar_series("PN38705PM,PN39445PM,PN38706PM", "2019-12", "2024-12")`
- `resumen("PN01273PM", "2020-01", "2024-12")`
- `resumen("PN09822PM", "2020-01", "2024-12")`
- `grafico("PN01273PM,PN09822PM", "2020-01", "2024-12")`

**Skills ENAHO.** `limpiando-enaho`, `graficando-enaho`, `mapeando-enaho`. Las salidas de estas skills ya existían en el proyecto cuando empecé; yo las leí y no las regeneré.

**Datos de la ENAHO.** `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip`.

**URL de las series (API del BCRP).**

- https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN38705PM/json/2019-12/2024-12
- https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN39445PM/json/2019-12/2024-12
- https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN38706PM/json/2019-12/2024-12
- https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01273PM/json/2020-1/2024-12
- https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN09822PM/json/2020-1/2024-12

## Trazabilidad de cifras

| Cifra | Origen |
|---|---|
| +31.94 % alimentos y bebidas | PN39445PM, 2019-12 a 2024-12, `comparar_series` (variacion_acumulada_pct) |
| +23.91 % IPC total | PN38705PM, 2019-12 a 2024-12, `comparar_series` |
| +18.69 % IPC sin alimentos y bebidas | PN38706PM, 2019-12 a 2024-12, `comparar_series` |
| +8.03 pp brecha alimentos vs total | `comparar_series`, brecha_vs_referencia_pp (PN39445PM) |
| −5.22 pp brecha sin alimentos vs total | `comparar_series`, brecha_vs_referencia_pp (PN38706PM) |
| 5.70 % y 4.38 % promedio anual | `comparar_series`, variacion_promedio_anual_pct (PN39445PM y PN38705PM) |
| 8.81 % pico total (jun. 2022) | `resumen` PN01273PM, 2020-01 a 2024-12 (máximo) |
| 13.16 % pico alimentos (feb. 2023) | `resumen` PN09822PM, 2020-01 a 2024-12 (máximo) |
| 0.69 % mínimo alimentos (sep. 2024) | `resumen` PN09822PM (mínimo) |
| 1.97 % y 1.25 % en dic. 2024 | `resumen` PN01273PM y PN09822PM (último) |
| 36.41 % peso nacional | `salidas/indicadores.csv`, gasto_alimentos_pct, Nacional |
| 48.03 % rural y 33.69 % urbano | `salidas/indicadores.csv`, gasto_alimentos_pct, Área |
| 49.27 %, 43.58 % y 33.26 % | `salidas/indicadores.csv`, gasto_alimentos_pct, Condición de pobreza |
| 30.00 % Lima Metropolitana | `salidas/indicadores.csv`, gasto_alimentos_pct, Dominio |
| 27.58 %, 24.81 % y 39.30 % pobreza | `salidas/indicadores.csv`, pobreza_inei_pct (Nacional y Área) |
| 3.14 % y 15.52 % pobreza extrema | `figuras/enaho_area.csv`, pct_extrema |
| 25.61 % pobreza sin ponderar | `salidas/validacion.txt`, prueba de ponderación |
| 47.05 %, 45.09 %, 44.96 %, 44.20 % | `salidas/indicadores.csv`, gasto_alimentos_pct, Departamento (Apurímac, Puno, Loreto, Cajamarca) |
| 30.25 %, 31.44 %, 32.81 % | `salidas/indicadores.csv`, gasto_alimentos_pct, Departamento (Lima, Moquegua, Callao) |
| 45.01 %, 42.97 %, 39.94 % | `salidas/indicadores.csv`, pobreza_inei_pct, Departamento (Cajamarca, Loreto, Puno) |
| 6.01 %, 10.97 %, 11.15 % | `salidas/indicadores.csv`, pobreza_inei_pct, Departamento (Ica, Moquegua, Madre de Dios) |
| 46.59 % Apurímac (versión alternativa) | `mapas/mapa_gasto_alimentos_departamento.csv`, columna valor |
| 603 y 865 hogares | `salidas/indicadores.csv`, hogares_muestra (Madre de Dios, Pasco) |
| 27.6 %, 24.8 %, 39.3 % referencia INEI | Referencias del encargo; diferencias 0.02, 0.01 y 0.00 pp según `salidas/validacion.txt` |
| 23 pruebas aprobadas, 0 fallidas | `salidas/validacion.txt` |
| 25 departamentos coinciden | `salidas/comparacion_mapa.csv`, columna coincide |
