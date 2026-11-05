# Verificación de cifras del informe final

Siete afirmaciones numéricas de [`informe_final.md`](informe_final.md), de las dos fuentes, comprobadas por un camino
distinto al que usó el agente: las tablas públicas del BCRP en la web (no la API ni el servidor MCP), el cálculo
independiente de [`evaluacion/verdades.py`](../evaluacion/verdades.py) (código propio que lee los `.dta` originales
del INEI, sin las skills) y las cifras publicadas por el INEI. Verificado el 5 de noviembre de 2026.

| # | Afirmación del informe | Valor del informe | Valor de verificación | Fuente o procedimiento | ¿Coincide? | Diferencia observada |
|---|---|---|---|---|---|---|
| 1 | Alimentos y bebidas acumuló 31.94 % entre dic. 2019 y dic. 2024 (hallazgo 1) | 31.94 % | 31.95 % | Tabla web del BCRP, PN39445PM: [90.59 (Dic19) y 119.53 (Dic24)](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN39445PM/html/2019-12/2024-12/); 119.53 / 90.59 − 1 = 31.95 %. Con la API sin redondear (`verdades.py`): 31.9444 % | Sí | 0.01 pp: la web muestra el índice con 2 decimales |
| 2 | La inflación a 12 meses llegó a 8.81 % en jun. 2022 (hallazgo 3) | 8.81 % (2022-06) | 8.81 % (Jun22) | [Tabla web del BCRP, PN01273PM, may.-jul. 2022](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01273PM/html/2022-05/2022-07/): 8.09, **8.81**, 8.74. `verdades.py`: máximo 2020-2024 = 8.8126 en 2022-06 | Sí | Ninguna |
| 3 | La inflación de alimentos llegó a 13.16 % en feb. 2023, 8 meses después del pico total (hallazgo 3) | 13.16 % (2023-02) | 13.16 % (Feb23) | [Tabla web del BCRP, PN09822PM, ene.-mar. 2023](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN09822PM/html/2023-01/2023-03/): 12.93, **13.16**, 12.81. De jun. 2022 a feb. 2023 hay 8 meses | Sí | Ninguna |
| 4 | La inflación de alimentos estuvo sobre la total de mediados de 2021 a inicios de 2024 (lectura del gráfico) | — | Sobre la total sin interrupción de 2021-06 a 2024-03; debajo desde 2024-04 | Diferencia mes a mes PN09822PM − PN01273PM con los datos de la herramienta `serie` | Sí | Ninguna |
| 5 | Pobreza monetaria nacional 27.58 %, urbana 24.81 %, rural 39.30 % (hallazgo 6) | 27.58 / 24.81 / 39.30 % | 27.6 / 24.8 / 39.3 % (INEI); 27.5795 / — / 39.3028 % (`verdades.py`) | Cifras oficiales del INEI para 2024 (valores de referencia del enunciado) y cálculo propio: sumaria, `pobreza <= 2`, ponderado con `factor07 × mieperho` | Sí | ≤ 0.02 pp (redondeo) |
| 6 | Los pobres extremos destinan 49.27 % de su gasto a alimentos (hallazgo 5) | 49.27 % | 49.27 % (`facpob07`); 49.22 % (`factor07 × mieperho`) | `verdades.py`: grupo 1 del gasto (`gru1*`) ÷ `gashog2d`, residentes habituales unidos a la sumaria | Sí | 0.05 pp entre ponderadores; el informe usa `facpob07` y lo dice |
| 7 | Pobreza de Cajamarca 45.0 % e Ica 6.0 % (hallazgo 8) | 45.0 / 6.0 % | 45.0 / 6.0 % | Referencia de la sesión 16 (`.claude/skills/mapeando-enaho/referencias/pobreza_departamento_2024.csv`); `verdades.py`: Cajamarca 45.0069 % | Sí | Ninguna (25/25 departamentos a 0.00 pp, `salidas/comparacion_mapa.csv`) |

## Diferencias y errores encontrados

- **Ninguna cifra del informe resultó incorrecta.** La única diferencia (0.01 pp en la afirmación 1) se debe a que la
  tabla web redondea el índice a dos decimales.
- **Dos ponderadores para el peso de los alimentos.** El agente notó que el mapa departamental pondera con
  `factor07 × mieperho` y las tablas por área con `facpob07` (Apurímac 46.6 % frente a 47.05 %). Lo dejó explícito
  en Limitaciones; no cambia el orden de los departamentos.
- **Primer intento descartado.** En la primera ejecución el agente no invocó las skills: leyó salidas que ya existían
  de pruebas anteriores. Se repitió desde cero, con las salidas apartadas
  ([`evidencias_ia/integracion/investigacion_intento1_bitacora.md`](../evidencias_ia/integracion/investigacion_intento1_bitacora.md)).
- **Manejo de errores.** En la ejecución final ninguna herramienta falló. Las respuestas de error de las herramientas
  están probadas aparte: `comparar_series` rechaza tasas, frecuencias distintas y códigos inexistentes
  (`mcp/test_comparar_series.py`), y `limpiar.py` y `mapear.py` terminan con error explícito si falta la base, si una
  validación esencial falla o si la unión territorial no da 25 unidades.
