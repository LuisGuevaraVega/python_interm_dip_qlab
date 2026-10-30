"""Paso 2: pasa los Excel de la UMC a una tabla ordenada y arma el mapa de las 26 regiones.

    uv run python scripts/procesar_datos.py

Salidas en datos/procesados/:
- resultados.csv   una fila por grado, área, año y grupo (región o estrato): % en cada nivel de logro,
                   su error estándar (años muestrales), medida promedio y su error estándar
- regiones.geojson las 26 regiones de la UMC: los 24 departamentos, Callao, y Lima dividida en
                   Lima Metropolitana (provincia de Lima) y Lima Provincias (las otras 9 provincias)
- control.json     verificaciones: los cuatro niveles suman 100 %, regiones y años completos
"""
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[1]
UMC = RAIZ / "datos" / "originales" / "umc"
GEO = RAIZ / "datos" / "originales" / "geo"
PROCESADOS = RAIZ / "datos" / "procesados"

AREAS = {"Lectura": "Lectura", "Matemática": "Matemática"}  # 2S también trae CS y CT; aquí no se usan
NIVELES = {"previo al inicio": "previo", "en inicio": "inicio", "en proceso": "proceso", "satisfactorio": "satisfactorio"}
# Años censales (todos los estudiantes) y muestrales (con error estándar), según la nota «Fuente» de cada Excel
CENSALES = {"4P": {2016, 2018, 2024}, "2S": {2015, 2016, 2018, 2019}}
ARCHIVOS = [  # (grado, ámbito, archivo de nivel de logro, archivo de medida promedio)
    ("4P", "region", "dre_4p_nivel", "dre_4p_medida"),
    ("4P", "estrato", "estratos_4p_nivel", "estratos_4p_medida"),
    ("2S", "region", "dre_2s_2015_2022_nivel", "dre_2s_2015_2022_medida"),
    ("2S", "region", "dre_2s_2023_2025_nivel", "dre_2s_2023_2025_medida"),
    ("2S", "estrato", "estratos_2s_2015_2022_nivel", "estratos_2s_2015_2022_medida"),
    ("2S", "estrato", "estratos_2s_2023_2025_nivel", "estratos_2s_2023_2025_medida"),
]
# Dimensiones de los estratos: el título de sección en el Excel → nombre corto; y cómo se escribe cada grupo
DIMENSIONES = {"sexo": "sexo", "gestion de la ie": "gestion", "area de la ie": "area", "caracteristica": "tipo",
               "caracteristicas": "tipo", "regiones": "region"}
GRUPOS = {"URBANA": "Urbano", "URBANO": "Urbano", "RURAL": "Rural", "HOMBRE": "Hombre", "MUJER": "Mujer",
          "ESTATAL": "Estatal", "NO ESTATAL": "No estatal", "POLIDOCENTE": "Polidocente",
          "MULTIGRADO/UNIDOCENTE": "Multigrado o unidocente", "NACIONAL": "Nacional"}


def sin_tildes(s):
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().strip().lower()


def nombre_region(s):
    """«LIMA METROPOLITANA» → «Lima Metropolitana», «SAN MARTIN» → «San Martín»…"""
    especiales = {"APURIMAC": "Apurímac", "HUANUCO": "Huánuco", "JUNIN": "Junín", "SAN MARTIN": "San Martín",
                  "ANCASH": "Áncash"}
    s = s.strip()
    return especiales.get(s, s.title().replace(" De ", " de "))


def leer_hoja(archivo, hoja, medida):
    """Una hoja de la UMC en filas largas: (dimension, grupo, anio, variable, valor)."""
    d = pd.read_excel(UMC / f"{archivo}.xlsx", hoja, header=None)
    anios = d.iloc[3].ffill()
    if medida:
        variables = ["medida" if str(v).startswith("Medida") else "medida_ee" for v in d.iloc[4]]
        inicio = 5
    else:
        niveles = d.iloc[4].ffill()
        variables = [None if pd.isna(n) else NIVELES[sin_tildes(n)] + ("" if u == "%" else "_ee")
                     for n, u in zip(niveles, d.iloc[5])]
        inicio = 6
    filas, dimension = [], None
    for i in range(inicio, len(d)):
        etiqueta = d.iloc[i, 0]
        if not isinstance(etiqueta, str):
            continue
        valores = pd.to_numeric(d.iloc[i, 1:], errors="coerce")
        if valores.isna().all():
            if sin_tildes(etiqueta) in DIMENSIONES:
                dimension = DIMENSIONES[sin_tildes(etiqueta)]
            continue
        if etiqueta.startswith(("Fuente", "1/")):
            break
        grupo = etiqueta.strip().upper()
        dim = "nacional" if grupo == "NACIONAL" else dimension
        nombre = nombre_region(grupo) if dim == "region" else GRUPOS[grupo]
        for j in range(1, d.shape[1]):
            if variables[j] and pd.notna(d.iloc[i, j]) and pd.notna(anios[j]):
                filas.append((dim, nombre, int(anios[j]), variables[j], float(d.iloc[i, j])))
    return filas


def procesar_resultados(control):
    filas = []
    for grado, ambito, nivel, medida in ARCHIVOS:
        for hoja, area in AREAS.items():
            for archivo, es_medida in ((nivel, False), (medida, True)):
                for dim, grupo, anio, var, valor in leer_hoja(archivo, hoja, es_medida):
                    filas.append({"grado": grado, "area": area, "dimension": dim, "grupo": grupo, "anio": anio,
                                  "variable": var, "valor": valor})
    largo = pd.DataFrame(filas)
    r = largo.pivot_table(index=["grado", "area", "dimension", "grupo", "anio"], columns="variable",
                          values="valor", aggfunc="first").reset_index()
    r.columns.name = None
    r["evaluacion"] = [("censal" if a in CENSALES[g] else "muestral") for g, a in zip(r.grado, r.anio)]
    r["debajo"] = r.previo + r.inicio  # no alcanzan ni el nivel «en proceso»
    columnas = ["grado", "area", "dimension", "grupo", "anio", "evaluacion", "satisfactorio", "satisfactorio_ee",
                "proceso", "proceso_ee", "inicio", "inicio_ee", "previo", "previo_ee", "debajo", "medida",
                "medida_ee"]
    r = r[columnas].sort_values(["grado", "area", "dimension", "grupo", "anio"])

    suma = (r.previo + r.inicio + r.proceso + r.satisfactorio - 100).abs()
    regiones = r[r.dimension == "region"]
    control["niveles_suman_100"] = {"filas": int(len(r)), "desvio_maximo_pp": round(float(suma.max()), 4)}
    control["regiones_por_grado_anio"] = {f"{g} {a}": int(n) for (g, a), n in
                                          regiones.groupby(["grado", "anio"]).grupo.nunique().items()}
    control["anios"] = {g: sorted(int(a) for a in x.anio.unique()) for g, x in r.groupby("grado")}
    control["filas_sin_medida"] = int(r.medida.isna().sum())
    return r


def procesar_mapa(nombres_umc, control):
    deps = json.loads((GEO / "peru_departamental.geojson").read_text(encoding="utf-8"))["features"]
    provs = json.loads((GEO / "peru_provincial.geojson").read_text(encoding="utf-8"))["features"]
    regiones = {}
    for f in deps:
        if f["properties"]["NOMBDEP"] != "LIMA":
            regiones[nombre_region(f["properties"]["NOMBDEP"])] = shape(f["geometry"])
    lima = [shape(f["geometry"]) for f in provs if f["properties"]["FIRST_NOMB"] == "LIMA"
            and f["properties"]["NOMBPROV"] == "LIMA"]
    resto = [shape(f["geometry"]) for f in provs if f["properties"]["FIRST_NOMB"] == "LIMA"
             and f["properties"]["NOMBPROV"] != "LIMA"]
    regiones["Lima Metropolitana"] = unary_union(lima)
    regiones["Lima Provincias"] = unary_union(resto)
    faltan = sorted(set(nombres_umc) - set(regiones))
    sobran = sorted(set(regiones) - set(nombres_umc))
    if faltan or sobran:
        raise SystemExit(f"Las regiones del mapa no coinciden con las de la UMC: faltan {faltan}, sobran {sobran}")
    control["mapa"] = {"regiones": len(regiones)}

    def redondear(g):  # 3 decimales (~100 m) bastan para un mapa nacional y achican el archivo
        txt = json.dumps(mapping(g.simplify(0.002, preserve_topology=True)))
        return json.loads(re.sub(r"(\d+\.\d{3})\d+", r"\1", txt))

    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "id": n, "properties": {"region": n}, "geometry": redondear(g)}
                         for n, g in sorted(regiones.items())]}


def main():
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    control = {}
    r = procesar_resultados(control)
    mapa = procesar_mapa(r[r.dimension == "region"].grupo.unique(), control)
    r.round(4).to_csv(PROCESADOS / "resultados.csv", index=False)
    (PROCESADOS / "regiones.geojson").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")),
                                                 encoding="utf-8")
    (PROCESADOS / "control.json").write_text(json.dumps(control, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(control, ensure_ascii=False, indent=1))
    print(f"resultados.csv: {len(r)} filas · regiones.geojson: "
          f"{(PROCESADOS / 'regiones.geojson').stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
