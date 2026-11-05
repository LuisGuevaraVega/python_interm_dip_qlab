"""Calcula las respuestas esperadas de la evaluación SIN usar el servidor MCP ni las Skills del proyecto.

    uv run evaluacion/verdades.py      # escribe evaluacion/verdades.txt con cada cifra y cómo se obtuvo

- BCRP: pide cada serie directamente a la API oficial (https://estadisticas.bcrp.gob.pe/estadisticas/series/api)
  con httpx y hace las cuentas aquí. No importa mcp/server.py.
- ENAHO: lee los .dta originales del INEI dentro de los zip de datos/ con código propio (no usa limpiar.py ni las
  bases de salidas/), aplica el filtro de residentes y los factores de expansión.
- Referencias publicadas: pobreza nacional 27.6 %, urbana 24.8 %, rural 39.3 % (INEI, informe técnico de pobreza
  monetaria 2024) y la pobreza departamental de la sesión 16 (referencias/pobreza_departamento_2024.csv).

Las verdades se fijaron antes de correr los dos modos; preguntas.csv las copia y no se cambian después.
"""
import io
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7, "Ago": 8, "Set": 9, "Sep": 9,
         "Oct": 10, "Nov": 11, "Dic": 12}
lineas = []


def anotar(texto):
    print(texto)
    lineas.append(texto)


def bcrp(codigo, desde, hasta):
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for _ in range(4):
        try:
            j = httpx.get(url, timeout=60).json()
            break
        except ValueError:
            import time
            time.sleep(3)
    s = {}
    for p in j["periods"]:
        mes, anio = p["name"].split(".")
        s[f"{anio}-{MESES[mes]:02d}"] = float(p["values"][0])
    return pd.Series(s), url


def leer(zip_path, nombre, columnas):
    with zipfile.ZipFile(zip_path) as z:
        df = pd.read_stata(io.BytesIO(z.read(nombre)), convert_categoricals=False, columns=columnas)
    return df


anotar("# Verdades de la evaluación (cálculo independiente)\n")
anotar("## BCRP (API oficial, sin el servidor MCP)")
total, u1 = bcrp("PN01273PM", "2020-1", "2024-12")
anotar(f"bcrp_ipc_dic24: PN01273PM 2024-12 = {total['2024-12']:.4f}  ({u1})")
anotar(f"bcrp_pico_ipc: máximo de PN01273PM 2020-01..2024-12 = {total.max():.4f} en {total.idxmax()}")
alim12, u2 = bcrp("PN09822PM", "2020-1", "2024-12")
anotar(f"bcrp_alim_feb23: PN09822PM 2023-02 = {alim12['2023-02']:.4f}  ({u2})")
idx_t, u3 = bcrp("PN38705PM", "2019-12", "2024-12")
idx_a, u4 = bcrp("PN39445PM", "2019-12", "2024-12")
var_t = 100 * (idx_t["2024-12"] / idx_t["2019-12"] - 1)
var_a = 100 * (idx_a["2024-12"] / idx_a["2019-12"] - 1)
anual_a = 100 * ((idx_a["2024-12"] / idx_a["2019-12"]) ** (1 / 5) - 1)
anotar(f"bcrp_acum_alim: PN39445PM {idx_a['2019-12']} (2019-12) -> {idx_a['2024-12']} (2024-12) = {var_a:.4f} %  ({u4})")
anotar(f"   IPC total PN38705PM {idx_t['2019-12']} -> {idx_t['2024-12']} = {var_t:.4f} %  ({u3})")
anotar(f"   brecha alimentos - total = {var_a - var_t:.4f} pp; promedio anual geométrico alimentos = {anual_a:.4f} %")

anotar("\n## ENAHO 2024 (microdatos del INEI, código propio)")
hog = leer(RAIZ / "datos" / "966-Modulo34.zip", "966-Modulo34/sumaria-2024.dta", None)
hog.columns = hog.columns.str.lower()
w = hog.factor07 * hog.mieperho
pobre = (hog.pobreza <= 2).astype(float)
rural = hog.estrato >= 6
nac = 100 * np.average(pobre, weights=w)
rur = 100 * np.average(pobre[rural], weights=w[rural])
caj = hog.ubigeo.astype(str).str[:2] == "06"
cajamarca = 100 * np.average(pobre[caj], weights=w[caj])
anotar(f"enaho_pobreza_nac: sumaria, (pobreza<=2) ponderado por factor07*mieperho = {nac:.4f} % (INEI publica 27.6 %)")
anotar(f"enaho_pobreza_rural: estrato>=6 = {rur:.4f} % (INEI publica 39.3 %)")
anotar(f"enaho_cajamarca: ubigeo[:2]=='06' = {cajamarca:.4f} % (sesión 16: 45.0 %)")
gru1 = [c for c in hog.columns if c.startswith("gru1")]
alim = 100 * hog[gru1].fillna(0).sum(axis=1) / hog.gashog2d
ext = hog.pobreza == 1
anotar(f"   columnas del grupo 1 de gasto sumadas: {gru1}")
anotar(f"enaho_alim_extremos: peso de alimentos en el gasto, pobres extremos, factor07*mieperho = "
       f"{np.average(alim[ext], weights=w[ext]):.4f} %")
per = leer(RAIZ / "datos" / "966-Modulo02.zip", "966-Modulo02/enaho01-2024-200.dta",
           ["conglome", "vivienda", "hogar", "codperso", "p204", "p205", "p206", "p208a", "facpob07"])
res = per[((per.p204 == 1) & (per.p205 == 2)) | ((per.p204 == 2) & (per.p206 == 1))]
x = res.merge(hog.assign(alim=alim)[["conglome", "vivienda", "hogar", "alim", "pobreza", "estrato"]],
              on=["conglome", "vivienda", "hogar"], validate="m:1")
ext_p = x.pobreza == 1
anotar(f"   mismo indicador ponderado por personas (facpob07, {len(res):,} residentes) = "
       f"{np.average(x.alim[ext_p], weights=x.facpob07[ext_p]):.4f} %")
rur_p = x.estrato >= 6
a_rur = np.average(x.alim[rur_p], weights=x.facpob07[rur_p])
a_urb = np.average(x.alim[~rur_p], weights=x.facpob07[~rur_p])
anotar(f"mixta_brecha_rural_urbana: peso de alimentos rural {a_rur:.4f} % - urbano {a_urb:.4f} % = {a_rur - a_urb:.4f} pp (facpob07)")

ninos = x.p208a <= 14
anotar(f"enaho_pobreza_ninos: residentes de 0 a 14 años en pobreza, facpob07 = "
       f"{100 * np.average((x.pobreza[ninos] <= 2).astype(float), weights=x.facpob07[ninos]):.4f} %")
(RAIZ / "evaluacion" / "verdades.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
