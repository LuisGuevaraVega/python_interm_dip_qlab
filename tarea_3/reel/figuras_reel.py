"""Figuras del reel (una por escena), con los colores del tablero en modo oscuro.

    uv run --project .. python figuras_reel.py        # desde tarea_3/reel/

Cada figura mide 2160×1480 px: el reel la muestra en una franja de 1080×740 (la mitad), así se ve nítida.
Todas salen de datos/procesados/; la sexta es una captura del tablero publicado (capturar_tablero).
"""
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Polygon
from shapely.geometry import shape

AQUI = Path(__file__).parent
PROCESADOS = AQUI.parent / "datos" / "procesados"
FIGS = AQUI / "figuras"
TABLERO = "https://luisguevaravega.github.io/python_interm_dip_qlab/tarea_3/web/"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

FONDO, TINTA, TINTA2, TENUE, REJILLA = "#1a1a19", "#f0efec", "#c3c2b7", "#898781", "#2c2c2a"
AZUL, NARANJA, MEDIO, ROJO = "#3987e5", "#d95926", "#383835", "#e66767"
plt.rcParams.update({"font.family": "Bahnschrift", "font.size": 22, "text.color": TINTA, "axes.labelcolor": TINTA2,
                     "xtick.color": TENUE, "ytick.color": TENUE, "axes.edgecolor": REJILLA, "axes.facecolor": FONDO,
                     "figure.facecolor": FONDO, "savefig.facecolor": FONDO})

r = pd.read_csv(PROCESADOS / "resultados.csv")
ind = json.loads((PROCESADOS / "indicadores.json").read_text(encoding="utf-8"))["combinaciones"]


def serie(grado, area, dim, grupo):
    return r[(r.grado == grado) & (r.area == area) & (r.dimension == dim) & (r.grupo == grupo)].set_index("anio").satisfactorio


def lienzo():
    fig, ax = plt.subplots(figsize=(10.8, 7.4), dpi=200)
    fig.subplots_adjust(left=0.1, right=0.86, top=0.86, bottom=0.12)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis="y", color=REJILLA, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=20)
    return fig, ax


def titulo(fig, texto, sub):
    fig.text(0.1, 0.94, texto, fontsize=30, weight="bold", color=TINTA)
    fig.text(0.1, 0.895, sub, fontsize=19, color=TENUE)


def franja(ax):
    ax.axvspan(2019.5, 2021.5, color=TENUE, alpha=0.13, lw=0)
    ax.text(2020.5, ax.get_ylim()[1] * 0.97, "escuelas\ncerradas", ha="center", va="top", fontsize=16, color=TENUE)


def pct(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")


def f1_caida():
    s = serie("4P", "Matemática", "nacional", "Nacional")
    fig, ax = lienzo()
    ax.plot(s.index, s.values, color=AZUL, lw=4, marker="o", ms=11, mec=FONDO, mew=2.5)
    ax.set_ylim(0, 40)
    franja(ax)
    for anio, color in ((2019, AZUL), (2022, NARANJA)):
        ax.plot(anio, s[anio], "o", ms=20, color=color, mec=FONDO, mew=3, zorder=5)
        ax.annotate(f"{s[anio]:.1f} %".replace(".", ","), (anio, s[anio]), xytext=(0, 22), textcoords="offset points",
                    ha="center", fontsize=30, weight="bold", color=TINTA)
    ax.set_xticks(s.index)
    pct(ax)
    titulo(fig, "Matemática, 4.º de primaria", "% de estudiantes en el nivel satisfactorio, Perú")
    fig.savefig(FIGS / "f1_caida.png")


def f2_recuperacion():
    s = serie("4P", "Matemática", "nacional", "Nacional")
    fig, ax = lienzo()
    anios, colores = [2019, 2022, 2025], [TENUE, NARANJA, AZUL]
    ax.bar([str(a) for a in anios], [s[a] for a in anios], color=colores, width=0.55)
    ax.axhline(s[2019], color=TINTA2, lw=1.5)
    ax.text(2.33, s[2019] + 0.6, "nivel de 2019", fontsize=17, color=TINTA2, ha="right")
    for k, a in enumerate(anios):
        ax.text(k, s[a] - 3.2, f"{s[a]:.1f} %".replace(".", ","), ha="center", fontsize=30, weight="bold", color=FONDO if a != 2022 else TINTA)
    ax.set_ylim(0, 40)
    ax.tick_params(axis="x", labelsize=24, labelcolor=TINTA2)
    pct(ax)
    titulo(fig, "Se recuperó más de la mitad", "Matemática, 4.º de primaria: % en nivel satisfactorio")
    fig.savefig(FIGS / "f2_recuperacion.png")


def f3_mapa():
    geo = json.loads((PROCESADOS / "regiones.geojson").read_text(encoding="utf-8"))["features"]
    reg = {x["region"]: x for x in ind["2S|Matemática"]["regiones"]}
    fig = plt.figure(figsize=(10.8, 7.4), dpi=200)
    ax = fig.add_axes((0.0, 0.02, 0.62, 0.86))
    cmap = LinearSegmentedColormap.from_list("div", [ROJO, MEDIO, AZUL])
    norma = TwoSlopeNorm(vcenter=0, vmin=-11, vmax=11)
    parches, colores = [], []
    for f in geo:
        g = shape(f["geometry"])
        for poli in getattr(g, "geoms", [g]):
            parches.append(Polygon(list(poli.exterior.coords), closed=True))
            colores.append(cmap(norma(reg[f["properties"]["region"]]["neto"])))
    ax.add_collection(PatchCollection(parches, facecolor=colores, edgecolor=FONDO, linewidth=1.2))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    peores = sorted(reg.values(), key=lambda x: x["neto"])[:3]
    mejores = [x for x in reg.values() if x["estado"] == "supera 2019"]
    fig.text(0.62, 0.70, "Peor que en 2019", fontsize=22, color=ROJO, weight="bold")
    fig.text(0.62, 0.635, f"{ind['2S|Matemática']['kpis']['regiones_debajo']} de 26 regiones", fontsize=34, weight="bold")
    for k, x in enumerate(peores):
        fig.text(0.62, 0.56 - k * 0.055, f"{x['region']}  {x['neto']:+.1f} pp".replace(".", ",").replace("-", "–"), fontsize=20, color=TINTA2)
    fig.text(0.62, 0.34, "Ya lo superan", fontsize=22, color=AZUL, weight="bold")
    for k, x in enumerate(sorted(mejores, key=lambda x: -x["neto"])):
        fig.text(0.62, 0.275 - k * 0.055, f"{x['region']}  {x['neto']:+.1f} pp".replace(".", ","), fontsize=20, color=TINTA2)
    fig.text(0.04, 0.94, "Matemática, 2.º de secundaria", fontsize=30, weight="bold")
    fig.text(0.04, 0.895, "Cambio en % satisfactorio de 2019 a 2025, en puntos porcentuales", fontsize=19, color=TENUE)
    fig.savefig(FIGS / "f3_mapa.png")


def f4_genero():
    fig, ax = lienzo()
    for grupo, nombre, color in (("Hombre", "Niños", AZUL), ("Mujer", "Niñas", NARANJA)):
        s = serie("4P", "Matemática", "sexo", grupo)
        ax.plot(s.index, s.values, color=color, lw=4, marker="o", ms=11, mec=FONDO, mew=2.5)
        ax.text(2025.35, s[2025], f"{nombre}\n{s[2025]:.1f} %".replace(".", ","), va="center", fontsize=22, color=TINTA, weight="bold")
    ax.set_ylim(0, 40)
    ax.set_xlim(2015.6, 2025.2)
    franja(ax)
    ax.set_xticks([2016, 2018, 2019, 2022, 2023, 2024, 2025])
    pct(ax)
    titulo(fig, "Una brecha que casi no existía", "Matemática, 4.º de primaria: % en nivel satisfactorio")
    fig.savefig(FIGS / "f4_genero.png")


def f5_regiones():
    t = ind["4P|Matemática"]["regiones"]
    fig, ax = lienzo()
    fig.subplots_adjust(left=0.08, right=0.72)
    for x in t:
        destacada = {"Tacna": NARANJA, "Ucayali": AZUL}.get(x["region"])
        ax.plot([0, 1, 2], [x["antes"], x["pandemia"], x["ahora"]], color=destacada or TENUE, alpha=1 if destacada else 0.35,
                lw=4 if destacada else 1.6, marker="o", ms=10 if destacada else 5, mec=FONDO, zorder=3 if destacada else 2)
        if destacada:
            ax.text(2.08, x["ahora"], f"{x['region']}  {x['neto']:+.1f} pp".replace(".", ",").replace("-", "–"),
                    va="center", fontsize=22, color=TINTA, weight="bold")
    ax.set_xticks([0, 1, 2], ["2019", "2022", "2025"], fontsize=22)
    ax.set_xlim(-0.1, 2.05)
    ax.set_ylim(0, 70)
    pct(ax)
    titulo(fig, "Cayeron más las que estaban arriba", "Matemática, 4.º de primaria: % satisfactorio en las 26 regiones")
    fig.savefig(FIGS / "f5_regiones.png")


def capturar_tablero():
    """La sexta figura: el tablero publicado, en modo oscuro (Edge sin ventana)."""
    from PIL import Image
    crudo = FIGS / "_tablero_crudo.png"
    perfil = AQUI / "privado" / "edge-perfil"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
                    "--blink-settings=preferredColorScheme=0", "--force-device-scale-factor=2", "--virtual-time-budget=20000",
                    "--window-size=1280,1500", f"--screenshot={crudo}", TABLERO + "#mapa=cambio"], check=True,
                   capture_output=True)
    im = Image.open(crudo)
    k = im.width / 1280
    # KPIs y gráficos: una franja con la proporción del panel del reel (1080×740)
    x0, x1, y0 = 50, 1230, 600
    y1 = y0 + (x1 - x0) * 740 / 1080
    im.crop((int(x0 * k), int(y0 * k), int(x1 * k), int(y1 * k))).save(FIGS / "f6_tablero.png")
    crudo.unlink()


if __name__ == "__main__":
    FIGS.mkdir(exist_ok=True)
    for f in (f1_caida, f2_recuperacion, f3_mapa, f4_genero, f5_regiones, capturar_tablero):
        f()
        print("listo:", f.__name__)
