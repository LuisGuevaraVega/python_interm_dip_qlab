"""Paso 3: indicadores de pérdida, recuperación y brechas; escribe los datos que usa el dashboard.

    uv run python scripts/analizar_datos.py

Salidas:
- datos/procesados/indicadores.json   KPIs por grado y área, tabla por región y brechas, con las cifras de los hallazgos
- web/data/datos.json                 lo que dibuja el dashboard
- web/data/regiones.geojson           el mapa (copia de datos/procesados/)

Pérdida = 2022 − 2019 (primera evaluación tras el cierre de escuelas), recuperación = 2025 − 2022 y cambio
neto = 2025 − 2019, en puntos porcentuales (pp) de estudiantes en el nivel satisfactorio. Un cambio es
«significativo» si |diferencia| > 1,96 × √(ee₁² + ee₂²); en los años censales el error estándar es 0.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
WEB_DATA = RAIZ / "web" / "data"
ANTES, PANDEMIA, AHORA = 2019, 2022, 2025
BRECHAS = {  # dimensión: (grupo de referencia, grupo comparado, nombre de la brecha)
    "area": ("Urbano", "Rural", "Urbano − rural"),
    "gestion": ("No estatal", "Estatal", "Privada − pública"),
    "sexo": ("Hombre", "Mujer", "Niños − niñas"),
}
GRADOS = {"4P": "4.º de primaria", "2S": "2.º de secundaria"}


def r1(x):
    return None if x is None or pd.isna(x) else round(float(x), 1)


def cambio(a, b, ee_a, ee_b):
    d = b - a
    ee = float(np.sqrt(np.nan_to_num(ee_a) ** 2 + np.nan_to_num(ee_b) ** 2))
    return {"pp": r1(d), "significativo": bool(abs(d) > 1.96 * ee) if ee > 0 else True}


def por_region(x):
    reg = x[x.dimension == "region"]
    sat = reg.pivot(index="grupo", columns="anio", values="satisfactorio")
    ee = reg.pivot(index="grupo", columns="anio", values="satisfactorio_ee")
    med = reg.pivot(index="grupo", columns="anio", values="medida")
    filas = []
    for g in sat.index:
        neto = cambio(sat.loc[g, ANTES], sat.loc[g, AHORA], ee.loc[g, ANTES], ee.loc[g, AHORA])
        perdida = sat.loc[g, PANDEMIA] - sat.loc[g, ANTES]
        recup = sat.loc[g, AHORA] - sat.loc[g, PANDEMIA]
        estado = ("supera 2019" if neto["pp"] > 0 and neto["significativo"] else
                  "debajo de 2019" if neto["pp"] < 0 and neto["significativo"] else "igual a 2019")
        filas.append({"region": g, "antes": r1(sat.loc[g, ANTES]), "pandemia": r1(sat.loc[g, PANDEMIA]),
                      "ahora": r1(sat.loc[g, AHORA]), "perdida": r1(perdida), "recuperacion": r1(recup),
                      "neto": neto["pp"], "neto_significativo": neto["significativo"], "estado": estado,
                      "medida_neto": r1(med.loc[g, AHORA] - med.loc[g, ANTES])})
    return sorted(filas, key=lambda f: f["neto"])


def brechas(x):
    salida = {}
    for dim, (ref, comp, nombre) in BRECHAS.items():
        e = x[x.dimension == dim].pivot(index="anio", columns="grupo", values="satisfactorio")
        serie = (e[ref] - e[comp]).round(1)
        salida[dim] = {"nombre": nombre, "referencia": ref, "comparado": comp,
                       "serie": {int(a): float(v) for a, v in serie.items()},
                       "antes": float(serie[ANTES]), "ahora": float(serie[AHORA])}
    return salida


def kpis(x, regiones, br):
    n = x[x.dimension == "nacional"].set_index("anio")
    s = n.satisfactorio
    perdida = s[PANDEMIA] - s[ANTES]
    recup = s[AHORA] - s[PANDEMIA]
    if perdida < 0:
        recuperado = {"pct": r1(100 * recup / -perdida), "texto": "de lo perdido"}
    else:
        recuperado = {"pct": None, "texto": "no hubo caída en 2022"}
    peor = min(regiones, key=lambda f: f["perdida"])
    return {
        "satisfactorio_ahora": r1(s[AHORA]), "satisfactorio_antes": r1(s[ANTES]),
        "satisfactorio_pandemia": r1(s[PANDEMIA]),
        "neto": cambio(s[ANTES], s[AHORA], n.satisfactorio_ee[ANTES], n.satisfactorio_ee[AHORA]),
        "perdida": cambio(s[ANTES], s[PANDEMIA], n.satisfactorio_ee[ANTES], n.satisfactorio_ee[PANDEMIA]),
        "recuperacion": cambio(s[PANDEMIA], s[AHORA], n.satisfactorio_ee[PANDEMIA], n.satisfactorio_ee[AHORA]),
        "recuperado": recuperado,
        "debajo_ahora": r1(n.debajo[AHORA]), "debajo_antes": r1(n.debajo[ANTES]),
        "regiones_debajo": sum(f["estado"] == "debajo de 2019" for f in regiones),
        "regiones_supera": sum(f["estado"] == "supera 2019" for f in regiones),
        "region_mayor_perdida": {"region": peor["region"], "pp": peor["perdida"]},
        "brecha_mayor": max(br.values(), key=lambda b: abs(b["ahora"]))["nombre"],
    }


def main():
    r = pd.read_csv(PROCESADOS / "resultados.csv")
    combos = {}
    for (grado, area), x in r.groupby(["grado", "area"]):
        regiones = por_region(x)
        br = brechas(x)
        combos[f"{grado}|{area}"] = {"grado": grado, "grado_nombre": GRADOS[grado], "area": area,
                                     "kpis": kpis(x, regiones, br), "regiones": regiones, "brechas": br}

    control = json.loads((PROCESADOS / "control.json").read_text(encoding="utf-8"))
    (PROCESADOS / "indicadores.json").write_text(json.dumps({"combinaciones": combos, "control": control},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")

    columnas = ["grado", "area", "dimension", "grupo", "anio", "evaluacion", "satisfactorio", "satisfactorio_ee",
                "proceso", "inicio", "previo", "debajo", "medida", "medida_ee"]
    filas = r[columnas].replace({np.nan: None}).round(2).to_dict("records")
    datos = {"periodos": {"antes": ANTES, "pandemia": PANDEMIA, "ahora": AHORA}, "grados": GRADOS,
             "anios": {g: sorted(int(a) for a in x.anio.unique()) for g, x in r.groupby("grado")},
             "resultados": filas, "combinaciones": combos}
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
    shutil.copy(PROCESADOS / "regiones.geojson", WEB_DATA / "regiones.geojson")

    for c in combos.values():
        k = c["kpis"]
        print(f"{c['grado']} {c['area']:10}  {k['satisfactorio_antes']} → {k['satisfactorio_pandemia']} → "
              f"{k['satisfactorio_ahora']}  pérdida {k['perdida']['pp']:+} recup {k['recuperacion']['pp']:+} "
              f"neto {k['neto']['pp']:+} (sig {k['neto']['significativo']})  recuperado {k['recuperado']}  "
              f"regiones debajo {k['regiones_debajo']} / supera {k['regiones_supera']}  "
              f"mayor pérdida {k['region_mayor_perdida']}")
        for b in c["brechas"].values():
            print(f"      {b['nombre']:18} {b['antes']:+5.1f} → {b['ahora']:+5.1f}")
    print(f"web/data/datos.json: {(WEB_DATA / 'datos.json').stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
