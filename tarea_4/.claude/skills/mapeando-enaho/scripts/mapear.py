"""Mapa coroplético departamental de la ENAHO 2024: une indicadores y geometrías por código, nunca por nombre.

    uv run .claude/skills/mapeando-enaho/scripts/mapear.py                          # pobreza monetaria
    uv run .claude/skills/mapeando-enaho/scripts/mapear.py --indicador pobreza_extrema
    uv run .claude/skills/mapeando-enaho/scripts/mapear.py --indicador gasto_alimentos

1. Calcula el indicador de cada departamento con salidas/hogares_2024.parquet, ponderado:
   pobreza y pobreza extrema con factor07 × mieperho (método INEI); gasto en alimentos, % del gasto del hogar
   ponderado por personas (factor07 × mieperho).
2. Une con el GeoJSON departamental del curso por llave oficial: ubigeo[:2] (ccdd) = FIRST_IDDP, como texto,
   con validate="one_to_one". Exige 25 departamentos, ninguno sin dato, Lima (15) y Callao (07) por separado.
3. Para la pobreza, compara con referencias/pobreza_departamento_2024.csv (sesión 16) y escribe
   salidas/comparacion_mapa.csv. Si algún departamento difiere más de 0.15 pp, termina con error.
4. Guarda mapas/mapa_<indicador>_departamento.png (200 dpi) y su .csv con los valores dibujados.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import httpx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle
from shapely.geometry import box

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
GEOJSON = RAIZ / "datos" / "peru_departamental_simple.geojson"
URL_GEOJSON = ("https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/"
               "Data/peru_departamental_simple.geojson")
REFERENCIA = AQUI.parent / "referencias" / "pobreza_departamento_2024.csv"
FUENTE = ("Fuente: INEI, ENAHO 2024 (módulo 34, sumaria); límites departamentales del repositorio del curso "
          "(d2cml-ai/Data-Science-Python, sesión 06).")
# rampa secuencial azul (claro -> oscuro) de la paleta validada; una sola tonalidad, nunca arcoíris
RAMPA = ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"]
TINTA, TINTA_2, MUTED, FONDO, BORDE = "#0b0b0b", "#52514e", "#898781", "#fcfcfb", "#ffffff"
HALO = [patheffects.withStroke(linewidth=2.6, foreground="#ffffff")]   # rótulo legible sobre cualquier tono
INDICADORES = {
    "pobreza": {"var": "pobre", "cortes": [0, 10, 20, 30, 40, 50], "unidad": "% de personas en pobreza monetaria",
                "titulo": "Pobreza monetaria por departamento, Perú 2024"},
    "pobreza_extrema": {"var": "pobre_extremo", "cortes": [0, 2, 5, 10, 15, 25],
                        "unidad": "% de personas en pobreza extrema",
                        "titulo": "Pobreza extrema por departamento, Perú 2024"},
    "gasto_alimentos": {"var": "gasto_alimentos_pct", "cortes": [0, 32, 36, 40, 44, 50],
                        "unidad": "% del gasto del hogar destinado a alimentos",
                        "titulo": "Peso de los alimentos en el gasto de los hogares por departamento, Perú 2024"},
}


def calcular(indicador, anio):
    base = RAIZ / "salidas" / f"hogares_{anio}.parquet"
    if not base.exists():
        sys.exit(f"ERROR: falta {base}. Ejecuta primero la skill limpiando-enaho: "
                 "uv run .claude/skills/limpiando-enaho/scripts/limpiar.py")
    h = pd.read_parquet(base)
    h["peso"] = h.factor07 * h.mieperho
    var = INDICADORES[indicador]["var"]
    escala = 1 if indicador == "gasto_alimentos" else 100
    filas = [{"ccdd": c, "departamento": d.departamento.iloc[0],
              "valor": escala * np.average(d[var].astype(float), weights=d.peso), "hogares_muestra": len(d)}
             for c, d in h.groupby("ccdd")]
    nacional = escala * np.average(h[var].astype(float), weights=h.peso)
    return pd.DataFrame(filas), nacional


def geometrias():
    if not GEOJSON.exists():
        GEOJSON.parent.mkdir(exist_ok=True)
        GEOJSON.write_bytes(httpx.get(URL_GEOJSON, timeout=60, follow_redirects=True).content)
    g = gpd.read_file(GEOJSON)
    g["FIRST_IDDP"] = g.FIRST_IDDP.astype(str).str.zfill(2)
    return g


def unir(g, t):
    m = g.merge(t, left_on="FIRST_IDDP", right_on="ccdd", how="left", validate="one_to_one")
    errores = []
    if len(m) != 25 or m.FIRST_IDDP.nunique() != 25:
        errores.append(f"se esperaban 25 unidades territoriales y hay {m.FIRST_IDDP.nunique()}")
    if m.valor.isna().any():
        errores.append("sin dato: " + ", ".join(m.loc[m.valor.isna(), "NOMBDEP"]))
    if not {"07", "15"} <= set(m.ccdd.dropna()):
        errores.append("Lima (15) y Callao (07) deben estar separados")
    sobran = sorted(set(t.ccdd) - set(g.FIRST_IDDP))
    if sobran:
        errores.append(f"códigos de la ENAHO sin geometría: {sobran}")
    if errores:
        sys.exit("ERROR en la unión territorial: " + "; ".join(errores))
    return m


def comparar(t):
    ref = pd.read_csv(REFERENCIA, dtype={"ccdd": str}).rename(columns={"pobreza_pct": "referencia_pct"})
    c = t.merge(ref[["ccdd", "referencia_pct"]], on="ccdd", how="outer", validate="one_to_one")
    c["calculado_pct"] = c.valor.round(1)
    c["diferencia_pp"] = (c.calculado_pct - c.referencia_pct).round(2)
    c["coincide"] = c.diferencia_pp.abs() <= 0.1
    c = c[["ccdd", "departamento", "calculado_pct", "referencia_pct", "diferencia_pp", "coincide"]]
    c.to_csv(RAIZ / "salidas" / "comparacion_mapa.csv", index=False, encoding="utf-8")
    print(f"Comparación con la sesión 16: {int(c.coincide.sum())}/25 departamentos a ≤ 0.1 pp "
          f"(máxima diferencia {c.diferencia_pp.abs().max():.2f} pp) -> salidas/comparacion_mapa.csv")
    if c.diferencia_pp.isna().any() or (c.diferencia_pp.abs() > 0.15).any():
        sys.exit("ERROR: el mapa no reproduce la referencia de la sesión 16:\n" +
                 c[~c.coincide].to_string(index=False))
    return c


def dibujar(m, indicador, nacional):
    cfg = INDICADORES[indicador]
    cortes = cfg["cortes"]
    if m.valor.max() > cortes[-1]:
        cortes = cortes[:-1] + [float(np.ceil(m.valor.max()))]
    cmap, norm = ListedColormap(RAMPA), BoundaryNorm(cortes, len(RAMPA))
    m = m.to_crs(32718)                                       # UTM 18S: el Perú sin deformar
    fig, ax = plt.subplots(figsize=(8.6, 10.6), facecolor=FONDO)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.08)
    m.plot(column="valor", cmap=cmap, norm=norm, edgecolor=BORDE, linewidth=0.8, ax=ax)
    for _, f in m.iterrows():
        if f.ccdd in ("07", "15"):
            continue                                          # van en el recuadro de Lima y Callao
        p = f.geometry.representative_point()
        ax.annotate(f"{f.departamento}\n{f.valor:.1f}", (p.x, p.y), ha="center", va="center", fontsize=7,
                    color=TINTA, linespacing=1.1, path_effects=HALO)
    ax.set_axis_off()

    # recuadro: Lima y Callao, que en el mapa grande no se distinguen
    lc = m[m.ccdd.isin(["07", "15"])]
    x0, y0, x1, y1 = m[m.ccdd == "07"].total_bounds
    zona = (x0 - 60_000, y0 - 60_000, x1 + 60_000, y1 + 60_000)
    ins = fig.add_axes([0.03, 0.12, 0.3, 0.27])
    m.plot(column="valor", cmap=cmap, norm=norm, edgecolor=BORDE, linewidth=1, ax=ins)
    ins.set_xlim(zona[0], zona[2])
    ins.set_ylim(zona[1], zona[3])
    ins.set_xticks([])
    ins.set_yticks([])
    for lado in ins.spines.values():
        lado.set_color(MUTED)
    ins.set_xlabel("")
    ins.set_ylabel("")
    for _, f in lc.iterrows():
        p = f.geometry.intersection(box(*zona)).representative_point()   # el punto, dentro del recuadro
        if f.ccdd == "07":   # Callao es una franja costera: su rótulo va sobre el mar, con una flecha
            ins.annotate(f"{f.departamento}\n{f.valor:.1f}", (p.x, p.y), xytext=(zona[0] + 25_000, p.y),
                         ha="center", va="center", fontsize=7.5, color=TINTA, linespacing=1.1, path_effects=HALO,
                         arrowprops={"arrowstyle": "-", "color": TINTA_2, "lw": 0.8})
        else:
            ins.annotate(f"{f.departamento}\n{f.valor:.1f}", (p.x, p.y), ha="center", va="center", fontsize=7.5,
                         color=TINTA, linespacing=1.1, path_effects=HALO)
    ins.set_title("Lima y Callao", fontsize=8.5, color=TINTA_2, loc="left")
    ax.add_patch(Rectangle((zona[0], zona[1]), zona[2] - zona[0], zona[3] - zona[1], fill=False,
                           edgecolor=MUTED, lw=0.8))

    etiquetas = [f"{a:g} a < {b:g}" for a, b in zip(cortes[:-2], cortes[1:-1])] + [f"{cortes[-2]:g} a {cortes[-1]:g}"]
    ax.legend([Patch(facecolor=c, edgecolor=MUTED, lw=0.4) for c in RAMPA], etiquetas, title=cfg["unidad"],
              loc="upper right", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5, title_fontsize=8.5,
              alignment="left")
    alto, bajo = m.loc[m.valor.idxmax()], m.loc[m.valor.idxmin()]
    fig.text(0.03, 0.975, cfg["titulo"], fontsize=14, fontweight="bold", color=TINTA, va="top")
    fig.text(0.03, 0.945, f"Más alto: {alto.departamento} ({alto.valor:.1f}). Más bajo: {bajo.departamento} "
             f"({bajo.valor:.1f}). Nacional: {nacional:.1f}. Unidad: {cfg['unidad']}.", fontsize=9.5,
             color=TINTA_2, va="top")
    fig.text(0.03, 0.015, "Unión por código: ubigeo[:2] = FIRST_IDDP (25 departamentos; Lima y Callao separados). "
             "Ponderado con factor07 × mieperho.\n" + FUENTE, fontsize=7.5, color=MUTED, va="bottom")
    salida = RAIZ / "mapas"
    salida.mkdir(exist_ok=True)
    png = salida / f"mapa_{indicador}_departamento.png"
    fig.savefig(png, dpi=200, facecolor=FONDO)
    plt.close(fig)
    tabla = m[["ccdd", "departamento", "valor", "hogares_muestra"]].sort_values("valor", ascending=False)
    tabla.round(2).to_csv(png.with_suffix(".csv"), index=False, encoding="utf-8")
    return png, tabla


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--indicador", default="pobreza", choices=list(INDICADORES))
    a.add_argument("--anio", type=int, default=2024)
    args = a.parse_args()
    t, nacional = calcular(args.indicador, args.anio)
    m = unir(geometrias(), t)
    print(f"Unión territorial: {len(m)} unidades, 0 sin dato, Lima (15) y Callao (07) separados.")
    if args.indicador == "pobreza":
        comparar(t)
    png, tabla = dibujar(m, args.indicador, nacional)
    print(f"Mapa: {png}  ·  valores en {png.with_suffix('.csv').name}")
    print(tabla.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
