"""Gráficos de pobreza monetaria y gasto en alimentos con la ENAHO 2024, siempre ponderados.

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo area
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo todos

Tipos:
  area          pobreza total y extrema, urbana frente a rural (método INEI: factor07 × mieperho)
  sexo          pobreza de hombres y mujeres (residentes, facpob07)
  edad          pobreza por grupo de edad (residentes, facpob07)
  departamento  pobreza de los 25 departamentos, ordenada, con la línea nacional (método INEI)
  dominio       pobreza por dominio geográfico (costa, sierra, selva, Lima Metropolitana)
  alimentos     parte del gasto del hogar que va a alimentos según condición de pobreza y área (facpob07)
  todos         todos los anteriores

Lee salidas/personas_2024.parquet y salidas/hogares_2024.parquet (los crea la skill limpiando-enaho). Cada
figura se guarda en figuras/enaho_<tipo>.png (200 dpi) junto a un .csv con los valores exactos que dibuja.
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[4]
FUENTE = "Fuente: INEI, Encuesta Nacional de Hogares (ENAHO) 2024, módulos 34 y 02. Estimaciones ponderadas."
AZUL, NARANJA = "#2a78d6", "#eb6834"                        # slots 1 y 2 de la paleta categórica validada
AZUL_CLARO = "#9ec5f4"
CAJA = {"facecolor": "#fcfcfb", "edgecolor": "none", "pad": 1.2}   # las cifras tapan la línea punteada, no al revés
TINTA, TINTA_2, MUTED, REJILLA, BASE, FONDO = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": BASE, "axes.labelcolor": TINTA_2,
                     "xtick.color": TINTA_2, "ytick.color": TINTA_2, "figure.facecolor": FONDO,
                     "axes.facecolor": FONDO, "savefig.facecolor": FONDO})


def cargar(anio):
    rutas = {n: RAIZ / "salidas" / f"{n}_{anio}.parquet" for n in ("personas", "hogares")}
    faltan = [str(r) for r in rutas.values() if not r.exists()]
    if faltan:
        sys.exit("ERROR: falta la base procesada (" + ", ".join(faltan) + "). Ejecuta primero la skill "
                 "limpiando-enaho: uv run .claude/skills/limpiando-enaho/scripts/limpiar.py")
    p, h = (pd.read_parquet(r) for r in rutas.values())
    h["peso"] = h.factor07 * h.mieperho
    return p, h


def _tasa(df, col, peso, var="pobre"):
    """% ponderado de una variable 0/1 (por defecto, pobre) en cada grupo, con su tamaño de muestra n."""
    filas = []
    for g, d in df.groupby(col, observed=True, sort=False):
        filas.append({col: g, "pct": 100 * np.average(d[var].astype(float), weights=d[peso]), "n": len(d)})
    return pd.DataFrame(filas)


def nacional(h):
    return 100 * np.average(h.pobre.astype(float), weights=h.peso)


def estilo(ax, eje="y"):
    for lado in ("top", "right", "left" if eje == "y" else "bottom"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis=eje, color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=10)


def titular(fig, titulo, subtitulo, nota=""):
    fig.text(0.02, 0.965, titulo, fontsize=14.5, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 0.905 - 0.055 * titulo.count(chr(10)), subtitulo, fontsize=10.5, color=TINTA_2, va="top")
    fig.text(0.02, 0.02, (nota + "\n" if nota else "") + FUENTE, fontsize=8, color=MUTED, va="bottom")


def guardar(fig, tipo, tabla):
    salida = RAIZ / "figuras"
    salida.mkdir(exist_ok=True)
    png = salida / f"enaho_{tipo}.png"
    fig.savefig(png, dpi=200)
    plt.close(fig)
    tabla.to_csv(png.with_suffix(".csv"), index=False, encoding="utf-8")
    print(f"{png}  ·  valores en {png.with_suffix('.csv').name}")
    print(tabla.to_string(index=False))
    return png


def barras_agrupadas(ax, categorias, series, colores, etiquetas, ancho=0.36):
    x = np.arange(len(categorias))
    for i, (vals, color, et) in enumerate(zip(series, colores, etiquetas)):
        pos = x + (i - (len(series) - 1) / 2) * (ancho + 0.03)
        barras = ax.bar(pos, vals, ancho, color=color, label=et, zorder=2)
        for b, v in zip(barras, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f} %", ha="center", va="bottom",
                    fontsize=10, color=TINTA, bbox=CAJA)
    ax.set_xticks(x, categorias)
    return x


def g_area(p, h):
    t = _tasa(h, "area", "peso").merge(_tasa(h, "area", "peso", "pobre_extremo").rename(
        columns={"pct": "pct_extrema"}).drop(columns="n"), on="area").set_index("area").loc[["Urbana", "Rural"]]
    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(top=0.78, bottom=0.17, left=0.08, right=0.97)
    barras_agrupadas(ax, ["Urbana", "Rural"], [t.pct, t.pct_extrema], [AZUL, NARANJA],
                     ["Pobreza monetaria total", "Pobreza extrema"])
    nac = nacional(h)
    ax.axhline(nac, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1.5)
    ax.text(1.5, nac + 0.6, f"Promedio nacional {nac:.1f} %", ha="right", va="bottom", fontsize=9, color=TINTA_2)
    ax.set_ylim(0, 50)
    ax.set_ylabel("% de la población")
    ax.legend(loc="upper left", frameon=False, fontsize=10, ncol=2, bbox_to_anchor=(0, 1.08))
    estilo(ax)
    brecha = t.pct.Rural - t.pct.Urbana
    titular(fig, f"En el campo la pobreza es {brecha:.1f} puntos más alta que en las ciudades",
            "Pobreza monetaria total y extrema por área de residencia, Perú 2024 (% de personas)",
            "Urbana: centros poblados de 2,000 a más habitantes (estrato ≤ 5). Ponderado con factor07 × mieperho "
            "(método INEI).")
    return guardar(fig, "area", t.reset_index().round(2))


def g_persona(p, col, tipo, orden, titulo_fn, subtitulo, figsize=(8, 5.4)):
    t = _tasa(p, col, "facpob07").merge(_tasa(p, col, "facpob07", "pobre_extremo").rename(
        columns={"pct": "pct_extrema"}).drop(columns="n"), on=col).set_index(col).loc[orden]
    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(top=0.78, bottom=0.17, left=0.08, right=0.97)
    barras_agrupadas(ax, orden, [t.pct, t.pct_extrema], [AZUL, NARANJA],
                     ["Pobreza monetaria total", "Pobreza extrema"], ancho=0.36 if len(orden) < 4 else 0.38)
    nac = 100 * np.average(p.pobre.astype(float), weights=p.facpob07)
    ax.axhline(nac, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1.5)
    ax.text(len(orden) - 0.5, nac + 0.6, f"Promedio nacional (facpob07) {nac:.1f} %", ha="right", va="bottom", fontsize=9,
            color=TINTA_2)
    ax.set_ylim(0, max(45, t.pct.max() + 8))
    ax.set_ylabel("% de la población")
    ax.legend(loc="upper left", frameon=False, fontsize=10, ncol=2, bbox_to_anchor=(0, 1.08))
    estilo(ax)
    titular(fig, titulo_fn(t), subtitulo, "Residentes habituales ponderados con facpob07 (la persona es la unidad "
            "de análisis).")
    return guardar(fig, tipo, t.reset_index().round(2))


def g_departamento(p, h):
    t = _tasa(h, "departamento", "peso").merge(h.groupby("departamento").ccdd.first().reset_index(),
                                               on="departamento").sort_values("pct")
    nac = nacional(h)
    fig, ax = plt.subplots(figsize=(8.5, 9.6))
    fig.subplots_adjust(top=0.875, bottom=0.1, left=0.2, right=0.95)
    colores = [AZUL if v > nac else AZUL_CLARO for v in t.pct]
    ax.barh(t.departamento, t.pct, color=colores, height=0.72, zorder=2)
    for y, v in enumerate(t.pct):
        ax.text(v + 0.5, y, f"{v:.1f}", va="center", fontsize=9, color=TINTA, bbox=CAJA)
    ax.axvline(nac, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1.5)
    ax.text(nac + 0.4, len(t) - 0.2, f"Nacional {nac:.1f} %", fontsize=9, color=TINTA_2, va="bottom")
    ax.set_xlim(0, 50)
    ax.set_ylim(-0.6, len(t) + 0.4)
    ax.set_xlabel("% de personas en situación de pobreza monetaria")
    estilo(ax, "x")
    top, fondo = t.iloc[-1], t.iloc[0]
    fig.text(0.02, 0.975, f"{top.departamento} tiene {top.pct / fondo.pct:.0f} veces la pobreza de {fondo.departamento}",
             fontsize=14.5, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 0.94, "Pobreza monetaria por departamento, Perú 2024 (% de personas). Azul oscuro: sobre el "
             "promedio nacional", fontsize=10, color=TINTA_2, va="top")
    fig.text(0.02, 0.012, "Departamento = ubigeo[:2]; Lima (provincias y Lima Metropolitana) y Callao por separado. "
             "Ponderado con factor07 × mieperho (método INEI).\n" + FUENTE, fontsize=8, color=MUTED, va="bottom")
    return guardar(fig, "departamento", t[["ccdd", "departamento", "pct", "n"]].sort_values("pct", ascending=False).round(2))


def g_dominio(p, h):
    t = _tasa(h, "dominio_nombre", "peso").sort_values("pct")
    nac = nacional(h)
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    fig.subplots_adjust(top=0.8, bottom=0.17, left=0.22, right=0.95)
    ax.barh(t.dominio_nombre, t.pct, color=[AZUL if v > nac else AZUL_CLARO for v in t.pct], height=0.7, zorder=2)
    for y, v in enumerate(t.pct):
        ax.text(v + 0.5, y, f"{v:.1f}", va="center", fontsize=9.5, color=TINTA, bbox=CAJA)
    ax.axvline(nac, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1.5)
    ax.text(nac + 0.4, len(t) - 0.45, f"Nacional {nac:.1f} %", fontsize=9, color=TINTA_2)
    ax.set_xlim(0, 52)
    ax.set_xlabel("% de personas")
    estilo(ax, "x")
    titular(fig, f"La sierra norte concentra la mayor pobreza: {t.pct.max():.1f} %",
            "Pobreza monetaria por dominio geográfico, Perú 2024 (% de personas)",
            "Ponderado con factor07 × mieperho (método INEI).")
    return guardar(fig, "dominio", t.round(2))


def g_alimentos(p, h):
    """La parte del gasto que se va en alimentos: el canal por el que la inflación de alimentos pesa más."""
    def media(d):
        return np.average(d.gasto_alimentos_pct, weights=d.facpob07)
    filas = [{"grupo": "Pobre extremo", "pct": media(p[p.pobreza == 1])},
             {"grupo": "Pobre no extremo", "pct": media(p[p.pobreza == 2])},
             {"grupo": "No pobre", "pct": media(p[p.pobreza == 3])},
             {"grupo": "Rural", "pct": media(p[~p.urbano])}, {"grupo": "Urbana", "pct": media(p[p.urbano])},
             {"grupo": "Lima Metropolitana", "pct": media(p[p.dominio == 8])}]
    t = pd.DataFrame(filas)
    t["n"] = [int((p.pobreza == 1).sum()), int((p.pobreza == 2).sum()), int((p.pobreza == 3).sum()),
              int((~p.urbano).sum()), int(p.urbano.sum()), int((p.dominio == 8).sum())]
    t["bloque"] = ["Condición de pobreza"] * 3 + ["Área de residencia"] * 3
    nac = media(p)
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    fig.subplots_adjust(top=0.74, bottom=0.17, left=0.25, right=0.95)
    y = [6, 5, 4, 2, 1, 0]
    ax.barh(y, t.pct, color=[AZUL] * 3 + [NARANJA] * 3, height=0.7, zorder=2)
    for yy, v in zip(y, t.pct):
        ax.text(v + 0.6, yy, f"{v:.1f} %", va="center", fontsize=10, color=TINTA, bbox=CAJA)
    ax.set_yticks(y, t.grupo)
    ax.axvline(nac, color=TINTA_2, lw=1, ls=(0, (4, 3)), zorder=1.5)
    ax.text(nac + 0.4, 6.75, f"Promedio nacional {nac:.1f} %", fontsize=9, color=TINTA_2)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=AZUL), Patch(color=NARANJA)], ["Según condición de pobreza", "Según área de residencia"],
              loc="upper left", bbox_to_anchor=(0, 1.1), ncol=2, frameon=False, fontsize=10)
    ax.set_ylim(-0.6, 7.2)
    ax.set_xlim(0, 60)
    ax.set_xlabel("% del gasto total del hogar destinado a alimentos")
    estilo(ax, "x")
    pobre_ext, no_pobre = t.pct[0], t.pct[2]
    titular(fig, f"Los pobres extremos destinan a comida {pobre_ext:.0f} de cada 100 soles\n"
                 f"que gastan; los no pobres, {no_pobre:.0f}",
            "Parte del gasto del hogar destinada a alimentos, Perú 2024 (promedio ponderado por personas)",
            "Alimentos = grupo 1 del gasto de la sumaria (comprados, autoconsumo, donados; dentro y fuera del hogar) "
            "÷ gasto total bruto (gashog2d).\nPonderado con facpob07.")
    return guardar(fig, "alimentos", t[["bloque", "grupo", "pct", "n"]].round(2))


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--tipo", default="todos",
                   choices=["area", "sexo", "edad", "departamento", "dominio", "alimentos", "todos"])
    a.add_argument("--anio", type=int, default=2024)
    args = a.parse_args()
    p, h = cargar(args.anio)
    graficos = {
        "area": lambda: g_area(p, h),
        "sexo": lambda: g_persona(
            p, "sexo", "sexo", ["Hombre", "Mujer"],
            lambda t: f"La pobreza casi no distingue sexo: {t.pct.Mujer:.1f} % en mujeres y {t.pct.Hombre:.1f} % en hombres",
            "Pobreza monetaria total y extrema por sexo, Perú 2024 (% de personas)"),
        "edad": lambda: g_persona(
            p, "grupo_edad", "edad", ["0-14", "15-29", "30-44", "45-64", "65 y más"],
            lambda t: f"Más de un tercio de los niños de 0 a 14 años vive en pobreza ({t.pct['0-14']:.1f} %)",
            "Pobreza monetaria total y extrema por grupo de edad, Perú 2024 (% de personas)", figsize=(9, 5.6)),
        "departamento": lambda: g_departamento(p, h),
        "dominio": lambda: g_dominio(p, h),
        "alimentos": lambda: g_alimentos(p, h),
    }
    for tipo in (graficos if args.tipo == "todos" else [args.tipo]):
        graficos[tipo]()


if __name__ == "__main__":
    main()
