"""Verifica que cada cifra del guion del reel salga de los datos del análisis, antes de narrarlo.

    uv run --project .. python verificar_guion.py        # desde tarea_3/reel/

Cada escena de guion.json lista en «datos» lo que dice y de dónde sale:
- "ruta":      un valor de datos/procesados/indicadores.json (claves separadas por puntos)
- "resultado": [grado, área, dimensión, grupo, año] → % satisfactorio en datos/procesados/resultados.csv
- "region":    [grado|área, región, campo] → la tabla por región de indicadores.json
- "maximo":    [grado, área, año] → la región con el % satisfactorio más alto ese año
Además, todo número que aparece en «cifra» o «etiqueta» (salvo años y grados) debe estar entre esos valores.
Si algo no cuadra, el script termina con error y no se narra.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
PROCESADOS = AQUI.parent / "datos" / "procesados"


def buscar(ind, res, d):
    if "ruta" in d:
        x = ind
        for k in d["ruta"].split("."):
            x = x[k]
        return x
    if "resultado" in d:
        grado, area, dim, grupo, anio = d["resultado"]
        f = res[(res.grado == grado) & (res.area == area) & (res.dimension == dim) & (res.grupo == grupo) & (res.anio == anio)]
        return round(float(f.satisfactorio.iloc[0]), 1)
    if "region" in d:
        combo, region, campo = d["region"]
        return next(r for r in ind["combinaciones"][combo]["regiones"] if r["region"] == region)[campo]
    if "maximo" in d:
        grado, area, anio = d["maximo"]
        f = res[(res.grado == grado) & (res.area == area) & (res.dimension == "region") & (res.anio == anio)]
        return f.loc[f.satisfactorio.idxmax(), "grupo"]
    raise ValueError(f"Dato sin fuente: {d}")


def numeros(texto):
    """Números de un texto, sin años (2015-2026) ni grados (4.º, 2.º)."""
    texto = re.sub(r"\b\d\.º", "", texto)
    vals = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:,\d+)?", texto)]
    return [v for v in vals if not 2015 <= v <= 2026]


def main():
    ind = json.loads((PROCESADOS / "indicadores.json").read_text(encoding="utf-8"))
    res = pd.read_csv(PROCESADOS / "resultados.csv")
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    errores = 0
    palabras = 0
    for i, e in enumerate(guion["escenas"], 1):
        palabras += len(e["frase"].split())
        print(f"Escena {i}: {e['frase']}")
        permitidos = {26.0}  # «26 regiones» es la cobertura, no un resultado
        for d in e["datos"]:
            real = buscar(ind, res, d)
            ok = real == d["valor"] if isinstance(d["valor"], str) else abs(float(real) - d["valor"]) < 0.051
            errores += not ok
            print(f"   {'OK ' if ok else '¡¡ '} {d['dice']}: guion {d['valor']} · datos {real}")
            if not isinstance(d["valor"], str):
                permitidos |= {abs(round(float(real), 1)), abs(round(float(real)))}
        for campo in ("cifra", "etiqueta"):
            for n in numeros(e[campo]):
                if n not in permitidos:
                    errores += 1
                    print(f"   ¡¡  «{n:g}» en {campo} no está entre los datos de la escena")
    segundos = palabras / 2.6  # ritmo medido en el reel anterior con la misma voz (2,5 a 3 palabras por segundo)
    print(f"\n{len(guion['escenas'])} escenas · {palabras} palabras · ~{segundos:.0f} s de narración estimada")
    if errores:
        sys.exit(f"{errores} cifra(s) no cuadran con los datos: corrige guion.json antes de narrar.")
    print("Todas las cifras del guion salen de los datos.")


if __name__ == "__main__":
    main()
