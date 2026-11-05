---
name: limpiando-enaho
description: Limpia y valida los módulos 34 (sumaria) y 02 (miembros) de la ENAHO 2024 del INEI y arma las bases de personas y hogares con pobreza monetaria, departamento, área urbana/rural, sexo, edad, gasto en alimentos y factores de expansión. Úsala cuando pidan limpiar, unir, validar o analizar la ENAHO, o calcular pobreza (nacional, urbana, rural, por departamento, sexo o edad) o la parte del gasto que va a alimentos; también antes de graficar o mapear la ENAHO si no existe salidas/personas_2024.parquet.
argument-hint: "[año, por defecto 2024]"
---

# Limpiar y validar la ENAHO

El procesamiento no se improvisa: lo hace siempre el mismo script, que corta si algo no cuadra.

1. **Datos.** Revisa que existan `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip` (966 = ENAHO 2024).
   Si faltan, agrega `--descargar` en el paso 2 (los baja del portal del INEI) y avísale al usuario.
2. **Ejecuta exactamente** (desde la raíz del proyecto):

   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py            # agrega --anio $ARGUMENTS solo si pidieron otro año
   ```

3. **Lee `salidas/validacion.txt`.** Si dice `VALIDACIÓN FALLIDA` o el script terminó con error, **detente**:
   informa qué validación falló y su detalle. Nunca ajustes cifras ni factores para que coincidan con la
   referencia, y no sigas a gráficos, mapas ni informes con una base que no validó.
4. **Responde con las salidas**, citando el archivo:
   - `salidas/personas_2024.parquet`: 108,664 residentes habituales (una fila por persona).
   - `salidas/hogares_2024.parquet`: 33,691 hogares de la sumaria.
   - `salidas/indicadores.csv`: pobreza y gasto en alimentos por área, dominio, departamento, sexo y edad.
5. **Ponderación (obligatoria; nunca promedios simples):**
   - Pobreza territorial (nacional, urbana/rural, dominio, departamento): columna `pobreza_inei_pct`, el método
     del INEI (hogares × `factor07 × mieperho`). Es el que reproduce las cifras oficiales.
   - Características de la persona (sexo, edad): `pobreza_personas_pct`, residentes × `facpob07`.
   - Si calculas algo nuevo con el parquet, usa `numpy.average(..., weights=facpob07)` en personas o
     `weights=factor07 * mieperho` en hogares, y escribe el código que usaste.
6. Antes de usar una variable que no está en las bases, o si dudas de un código, lee [reference.md](reference.md).

Toda cifra que reportes debe decir de qué columna y archivo sale y que la fuente es «INEI, ENAHO 2024».
Las asociaciones (por ejemplo, entre gasto en alimentos y pobreza) son descriptivas, no causales.
