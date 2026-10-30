"""Paso 1: descarga las bases de datos de la UMC del MINEDU y los límites de las regiones a datos/originales/.

    uv run python scripts/obtener_datos.py            # baja lo que falte
    uv run python scripts/obtener_datos.py --forzar   # vuelve a bajar todo

Fuente única de los datos: Oficina de Medición de la Calidad de los Aprendizajes (UMC) del MINEDU,
«Bases de datos» de las evaluaciones nacionales de logros de aprendizaje (http://umc.minedu.gob.pe/bases-de-datos/).
Los límites de las regiones (solo para dibujar el mapa) son de github.com/juaneladio/peru-geojson.

Cada descarga queda registrada en datos/originales/descargas.csv con su URL, fecha y tamaño.
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / "datos" / "originales"
UMC = "http://umc.minedu.gob.pe/wp-content/uploads"

# nombre local: (ruta en el sitio de la UMC). Por región (DRE) y por estrato; nivel de logro y medida promedio.
ARCHIVOS_UMC = {
    "dre_4p_nivel.xlsx": "2026/05/2.-DRE-4P-2016-2025-Nivel-de-desempeño.xlsx",
    "dre_4p_medida.xlsx": "2026/05/2.-DRE-4P-2016-2025-medida-promedio.xlsx",
    "estratos_4p_nivel.xlsx": "2026/05/1.-Estratos-4P-2016-2025-Nivel-de-desempeño.xlsx",
    "estratos_4p_medida.xlsx": "2026/05/1.-Estratos-4P-2016-2025-medida-promedio.xlsx",
    "dre_2s_2015_2022_nivel.xlsx": "2026/05/2.-DRE-2S-2015-2022-2S-Nivel-de-desempeño.xlsx",
    "dre_2s_2015_2022_medida.xlsx": "2026/05/2.-DRE-2S-2015-2022-2S-medida-promedio.xlsx",
    "dre_2s_2023_2025_nivel.xlsx": "2026/05/2.-DRE-2S-2023-2025-2S-Nivel-de-desempeño.xlsx",
    "dre_2s_2023_2025_medida.xlsx": "2026/05/2.-DRE-2S-2023-2025-2S-medida-promedio.xlsx",
    "estratos_2s_2015_2022_nivel.xlsx": "2026/05/1.-Estratos-2015-2022-2S-Nivel-de-desempeño.xlsx",
    "estratos_2s_2015_2022_medida.xlsx": "2026/05/1.-Estratos-2S-2015-2022-2S-medida-promedio.xlsx",
    "estratos_2s_2023_2025_nivel.xlsx": "2026/05/1.-Estratos-2023-2025-2S-Nivel-de-desempeño.xlsx",
    "estratos_2s_2023_2025_medida.xlsx": "2026/05/1.-Estratos-2S-2023-2025-2S-medida-promedio.xlsx",
}
GEO = "https://raw.githubusercontent.com/juaneladio/peru-geojson/master"
ARCHIVOS_GEO = {
    "peru_departamental.geojson": f"{GEO}/peru_departamental_simple.geojson",
    "peru_provincial.geojson": f"{GEO}/peru_provincial_simple.geojson",
}


def bajar(url, destino, forzar):
    if destino.exists() and not forzar:
        return None
    for intento in range(3):
        try:
            r = httpx.get(url, timeout=120, follow_redirects=True)
            r.raise_for_status()
            break
        except httpx.HTTPError as e:
            if intento == 2:
                raise SystemExit(f"No se pudo bajar {url}: {e}")
            time.sleep(3 * (intento + 1))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(r.content)
    return {"archivo": str(destino.relative_to(RAIZ)).replace("\\", "/"), "url": url,
            "descargado": f"{datetime.now():%Y-%m-%d %H:%M}", "bytes": len(r.content)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--forzar", action="store_true", help="vuelve a bajar aunque el archivo exista")
    args = p.parse_args()

    registro = ORIGINALES / "descargas.csv"
    filas = {}
    if registro.exists():
        with registro.open(encoding="utf-8") as f:
            filas = {x["archivo"]: x for x in csv.DictReader(f)}

    pedidos = [(f"{UMC}/{quote(ruta)}", ORIGINALES / "umc" / nombre) for nombre, ruta in ARCHIVOS_UMC.items()]
    pedidos += [(url, ORIGINALES / "geo" / nombre) for nombre, url in ARCHIVOS_GEO.items()]
    for url, destino in pedidos:
        fila = bajar(url, destino, args.forzar)
        if fila:
            filas[fila["archivo"]] = fila
            print(f"  {fila['archivo']}: {fila['bytes'] / 1e3:.0f} kB")
            time.sleep(1)

    with registro.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["archivo", "url", "descargado", "bytes"])
        w.writeheader()
        w.writerows(sorted(filas.values(), key=lambda x: x["archivo"]))
    print(f"Listo: {len(filas)} archivos en datos/originales/ (registro en {registro.name}).")


if __name__ == "__main__":
    main()
