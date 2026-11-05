---
name: mapeando-enaho
description: Hace mapas coropléticos por departamento del Perú con la ENAHO 2024 del INEI - pobreza monetaria, pobreza extrema o peso de los alimentos en el gasto del hogar - uniendo indicadores y límites departamentales por código (ubigeo[:2] = FIRST_IDDP), con los 25 departamentos y Lima y Callao separados, y valida la pobreza contra la referencia de la sesión 16. Úsala cuando pidan un mapa, una distribución territorial o regional, o «dónde» se concentra la pobreza en el Perú.
argument-hint: "[pobreza | pobreza_extrema | gasto_alimentos]"
---

# Mapear la ENAHO por departamento

1. **¿Existe la base?** Si no existe `salidas/hogares_2024.parquet`, usa primero la skill `limpiando-enaho` y sigue
   solo si su validación aprobó.
2. **Elige el indicador** según el pedido (o `$ARGUMENTS`): `pobreza` (por defecto), `pobreza_extrema` o
   `gasto_alimentos` (parte del gasto del hogar que va a comida).
3. **Ejecuta** desde la raíz del proyecto:

   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py --indicador <indicador>
   ```

   El script baja el GeoJSON del curso a `datos/` si falta, une **por código** (`ubigeo[:2]` = `FIRST_IDDP`, como
   texto, `validate="one_to_one"`) y termina con error si no hay 25 unidades, si alguna queda sin dato o si Lima
   (15) y Callao (07) no están separados.
4. **Si el indicador es pobreza**, lee la línea «Comparación con la sesión 16» y `salidas/comparacion_mapa.csv`:
   los 25 departamentos deben coincidir con [referencias/pobreza_departamento_2024.csv](referencias/pobreza_departamento_2024.csv)
   a 0.1 pp o menos. Si el script falla aquí, informa las diferencias; no edites la referencia ni los valores.
5. **Responde** con la ruta del PNG (`mapas/mapa_<indicador>_departamento.png`), el más alto, el más bajo y el
   nacional, tomados del `.csv` que el script deja al lado.

## Reglas del mapa (el script ya las cumple)

- Nunca unir por nombre: «APURIMAC» del GeoJSON no es «Apurímac»; la llave oficial es el código.
- Un solo tono de claro a oscuro (azul), clases fijas desde 0, leyenda con la unidad («% de personas…»). Nada de
  arcoíris.
- Recuadro ampliado de Lima y Callao, que en el mapa del país no se distinguen.
- Ponderado con `factor07 × mieperho` (método INEI); fuente INEI, ENAHO 2024 y límites del repositorio del curso.

El mapa describe dónde está la pobreza; no explica por qué. No atribuyas causas a la geografía.
