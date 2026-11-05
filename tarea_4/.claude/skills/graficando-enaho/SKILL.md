---
name: graficando-enaho
description: Hace gráficos de pobreza monetaria y gasto en alimentos con la ENAHO 2024 del INEI, siempre ponderados - por área urbana y rural, sexo, grupo de edad, departamento, dominio geográfico o condición de pobreza - y los guarda en figuras/ con título, unidades y fuente. Úsala cuando pidan graficar, visualizar, comparar en un gráfico o «hacer una figura» de pobreza o de la ENAHO.
argument-hint: "[area | sexo | edad | departamento | dominio | alimentos | todos]"
---

# Graficar la ENAHO

1. **¿Existe la base?** Si no existen `salidas/personas_2024.parquet` y `salidas/hogares_2024.parquet`, usa
   primero la skill `limpiando-enaho` y sigue solo si su validación aprobó.
2. **Elige el tipo** según el pedido (o `$ARGUMENTS` si lo llamaron con `/graficando-enaho`):

   | Pedido | `--tipo` | Ponderador |
   |---|---|---|
   | urbano y rural, área, campo y ciudad | `area` | `factor07 × mieperho` (método INEI) |
   | sexo, hombres y mujeres, género | `sexo` | `facpob07` |
   | edad, niños, adultos mayores | `edad` | `facpob07` |
   | departamentos, regiones, ranking territorial | `departamento` | `factor07 × mieperho` |
   | costa, sierra, selva, dominio | `dominio` | `factor07 × mieperho` |
   | gasto en alimentos, comida, canasta, peso de los alimentos | `alimentos` | `facpob07` |
   | varios o «todos los gráficos» | `todos` | — |

3. **Ejecuta** desde la raíz del proyecto:

   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --tipo <tipo>
   ```

   Si el script dice que falta la base, corre `limpiando-enaho` y vuelve a ejecutarlo.
4. **Responde** con la ruta de cada PNG (`figuras/enaho_<tipo>.png`) y las cifras del `.csv` que el script deja al
   lado (es la tabla exacta que se dibujó). No redondees distinto a la tabla ni agregues cifras que no estén en ella.
   Si quieres mostrar la imagen, lee el PNG.

## Reglas que el script ya cumple (no las rompas si lo modificas)

- Toda cifra ponderada; nunca promedios simples.
- Barras que empiezan en cero, ordenadas cuando no hay un orden natural, un color por serie (azul `#2a78d6`,
  naranja `#eb6834`) y el valor escrito en cada barra.
- Título que dice el hallazgo; subtítulo con qué, dónde y cuándo («Perú 2024», «% de personas»).
- Línea punteada del promedio nacional como referencia.
- Nota al pie: «Fuente: INEI, ENAHO 2024» y el ponderador usado. PNG a 200 dpi en `figuras/`.

Describe diferencias, no causas: «la pobreza rural es 14.5 puntos mayor», no «ser rural causa pobreza».
Para otro corte que el script no tenga, calcula con `numpy.average(..., weights=...)` sobre el parquet y sigue las
mismas reglas.
