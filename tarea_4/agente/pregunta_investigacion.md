Eres un agente de investigación socioeconómica del Perú. Responde esta pregunta con datos oficiales, usando las
herramientas del proyecto y sin calcular nada a mano:

**¿Cuánto subieron los precios de los alimentos frente al resto de la canasta en Lima Metropolitana entre 2020 y
2024, y qué tan expuestos estaban a esa alza —por el peso de los alimentos en su gasto— los hogares pobres, rurales
y de cada departamento del Perú en 2024?**

Cómo trabajar:

1. Plan. Antes de usar herramientas, escribe en 4 a 6 líneas qué datos necesitas de cada fuente y qué
   herramienta o skill usarás para cada uno.
2. BCRP (servidor MCP `bcrp`). Lee el recurso `bcrp://series-clave` o usa `buscar_series` para ubicar las series
   del IPC de Lima Metropolitana (total, alimentos y bebidas, sin alimentos y bebidas). Usa `comparar_series` entre
   dic. 2019 y dic. 2024 sobre los índices, `resumen` para el pico de la inflación interanual total y de alimentos en
   2020-2024, y `grafico` para guardar en figuras/ un gráfico de la inflación a 12 meses total y de alimentos.
3. ENAHO 2024 (skills). Si no existe la base procesada, usa `limpiando-enaho` y revisa su validación. Usa
   `graficando-enaho` para el gráfico del peso de los alimentos en el gasto y el de pobreza urbana/rural, y
   `mapeando-enaho` para el mapa de pobreza por departamento. Toma las cifras de los .csv que dejan las skills y de
   salidas/indicadores.csv.
4. Contraste. Compara tus cifras con las referencias oficiales: pobreza nacional 27.6 %, urbana 24.8 %, rural
   39.3 % (INEI) y salidas/comparacion_mapa.csv. Si una herramienta falla o no encuentra datos, dilo en el informe en
   vez de inventar.
5. Escribe `informes/informe_final.md` en español con estas secciones:
   1. Pregunta de investigación (tema, objetivo y delimitación: periodo, territorio y unidad de análisis).
   2. Fuentes y metodología (series del BCRP con su código; módulos de la ENAHO; ponderadores; definiciones).
   3. Resultados: al menos 3 hallazgos numerados, cada uno con su cifra y entre paréntesis su origen
      (código de serie y periodo, o archivo y columna).
   4. Visualizaciones: incrusta con rutas relativas (../figuras/..., ../mapas/...) un gráfico del BCRP, un gráfico de
      la ENAHO y el mapa departamental, cada uno con una línea de lectura.
   5. Interpretación: qué patrón muestran juntas las dos fuentes. Es una asociación descriptiva, no causal.
   6. Limitaciones: el IPC es de Lima Metropolitana y la ENAHO es nacional; la ENAHO es de un solo año (2024);
      el peso de los alimentos no mide por sí solo el impacto de la inflación; muestra por departamento; etc.
   7. Reproducibilidad: comandos, scripts, archivos de salida y URL de las series usadas.
   Agrega al final una tabla «Trazabilidad de cifras» con cada número del informe y su origen.
6. Termina con un resumen de 5 líneas de lo que hiciste y qué herramientas usaste.

Reglas de ejecución: las salidas de la ENAHO (bases, figuras, mapas) no existen todavía; las tienes que producir
tú. Carga cada skill con la herramienta Skill (`limpiando-enaho`, `graficando-enaho`, `mapeando-enaho`) y sigue
sus instrucciones; no ejecutes sus scripts sin haberla cargado. Las cifras del BCRP salen solo de las herramientas
del servidor `bcrp`.
