"""Corpus de la Tarea 2: catálogo de documentos y audios peruanos, y su descarga.

    uv run python corpus.py

Todo viene de Wikimedia Commons con licencia libre (dominio público, CC0, CC BY o CC BY-SA).
La licencia y el autor de cada archivo se leen de la API de Commons al momento de bajarlo y
quedan en datos/fuentes.csv. Los archivos van a datos/raw/, que no se versiona: este script
es la forma de recuperarlos.

Se baja con un User-Agent descriptivo y con pausas de 2 s entre pedidos. Las imágenes se piden
en el ancho estándar de 1920 px de Wikimedia (o en su tamaño original si son más chicas); de
los PDF se renderiza una sola página.

Siete entrevistas tienen en su nombre de archivo el nombre de la persona entrevistada o del
estudiante que entrevista (personas privadas). Para no publicarlo, esas se piden por su número de página en Commons (curid), su
`fuente_url` usa el enlace `?curid=` y su título se guarda seudonimizado.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd
import soundfile as sf

CARPETA = Path(__file__).resolve().parent
RAW = CARPETA / "datos" / "raw"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tarea2-ocr-asr/2026 (curso Data Science Python, UP; https://github.com/LuisGuevaraVega/python_interm_dip_qlab)"}
ANCHO = 1920
PAUSA = 2.0

# id: (tipo, archivo en Commons, página si es PDF/DjVu, descripción corta)
DOCUMENTOS = {
    # impresos nítidos
    "doc_001": ("impreso", "Carta Democrática Interamericana.jpg", 1, "Nota de la Representación del Perú ante la OEA (2001)"),
    "doc_002": ("impreso", "Carta de agradecimiento del secretario de la Presidencia de la República Nazario Chávez Aliaga al pintor Segundo Ciro Gallardo Gallo en nombre del presidente Manuel Prado Ugarteche.jpg", 1, "Carta mecanografiada de la Secretaría de la Presidencia (1956)"),
    "doc_003": ("impreso", "Otorgamiento Municipal.jpg", 1, "Resolución de alcaldía de Moyobamba (2015)"),
    "doc_004": ("impreso", "NOMBRAMIENTO JAVIER DAVID HABICH.pdf", 1, "Página de normas legales de El Peruano (2006)"),
    "doc_005": ("impreso", "Constitución Política del Perú (1856).pdf", 5, "Constitución de 1856, página impresa"),
    "doc_006": ("impreso", "Variedades No. 67.pdf", 3, "Revista Variedades N.° 67 (1909)"),
    "doc_007": ("impreso", "Cachivaches.djvu", 9, "Cachivaches de Ricardo Palma (1900), página de libro"),
    "doc_008": ("impreso", "4000004161-0016 - Carta de Carlos J. Bachmann. 1914 julio 4, Maldonado; para Ricardo Palma, Lima.pdf", 1, "Carta mecanografiada a Ricardo Palma (1914)"),
    # fotos con sombra, reflejos o inclinación
    "doc_009": ("foto", "LimaPlacaCatedral1988.JPG", 1, "Placa en la Catedral de Lima, foto en contrapicado"),
    "doc_010": ("foto", "Placa de la Casa Federico Elguera, Calle La Virreyna, Lima.jpg", 1, "Placa de bronce en relieve, foto inclinada"),
    "doc_011": ("foto", "Pasaje Acisclo Villarán - Placa conmemorativa.jpg", 1, "Placa oscura en una pared del Centro de Lima"),
    "doc_012": ("foto", "Placa conmemorativa Mercado Minorista La Parada.jpg", 1, "Placa de mármol en un muro pintado"),
    "doc_013": ("foto", "Centro Español, Lima 01.jpg", 1, "Placa de azulejos en ángulo, letra cursiva"),
    "doc_014": ("foto", "Commemorative plaque to Ioannes Paulus II in the Cathedral of Lima.jpg", 1, "Placa de mármol veteado en la Catedral de Lima"),
    "doc_015": ("foto", "Araucaria patrimonial de San Isidro 06.jpg", 1, "Cartel de árbol patrimonial con reflejos, San Isidro"),
    "doc_016": ("foto", "Carta de Grau a viuda de Prat en monumento chileno.JPG", 1, "Carta de Miguel Grau grabada en piedra, foto con sombras"),
    # manuscritos
    "doc_017": ("manuscrito", "Miguel Grau - Brev.jpg", 1, "Carta de Miguel Grau (1879)"),
    "doc_018": ("manuscrito", "AR-ANH-EF-Secc.II-53-2.jpg", 1, "Carta de Agustín Gamarra (1822)"),
    "doc_019": ("manuscrito", "AR-ANH-EF-Secc.II-64.jpg", 1, "Carta de Miguel de San Román (1840)"),
    "doc_020": ("manuscrito", "AR-ANH-EF-Secc.II-69.jpg", 1, "Carta de Nicolás de Piérola (1897)"),
    "doc_021": ("manuscrito", "AAMSM carta a hermano 31072010.jpg", 1, "Carta de un soldado a su hermano (1880), foto en museo"),
    "doc_022": ("manuscrito", "4000004161-0003 - Carta de Carlos J. Bachmann. 1912 junio 10, Riberalta; para Ricardo Palma, Lima.pdf", 1, "Carta manuscrita a Ricardo Palma (1912)"),
    "doc_023": ("manuscrito", "AR-ANH-EF-Secc.II-57.pdf", 1, "Comunicación de Manuel Menéndez, Consejo de Estado (1839)"),
    "doc_024": ("manuscrito", "AR-ANH-EF-Secc.II-67.jpg", 1, "Nota de José Balta (1869)"),
    "doc_025": ("manuscrito", "AR-ANH-EF-Secc.II-17.pdf", 1, "Decreto del Virrey del Perú, Marqués de Mancera (1642)"),
}

# id: (archivo en Commons o su curid, (inicio, fin) en segundos o None para el audio completo, condición)
AUDIOS = {
    "clip_001": ("Entrevista 1 en la Av. Rivagüero - El Agustino.ogg", None, "entrevista en la calle"),
    "clip_002": ("Entrevista 2 en la Av. Rivagüero - El Agustino.ogg", None, "entrevista en la calle, varias hablantes"),
    "clip_003": ("Entrevista en el medio tiempo.opus", None, "entrevista durante un partido, ruido de fondo"),
    "clip_004": ("Entrevista 1,.wav", None, "entrevista grabada por estudiante UNMSM"),
    "clip_005": ("Entrevista 2.wav", None, "entrevista grabada por estudiante UNMSM"),
    "clip_006": ("Entrevista 3.wav", None, "entrevista grabada por estudiante UNMSM"),
    "clip_007": ("Entrevista 4.wav", None, "entrevista grabada por estudiante UNMSM"),
    "clip_008": ("Audio de la entrevista a una chica que participaba de la marcha.ogg", None, "entrevista en una marcha, ruido de multitud"),
    "clip_009": (133964620, None, "entrevista en una marcha, ruido de multitud"),
    "clip_010": (133964621, None, "entrevistas en una marcha, ruido de multitud"),
    "clip_011": (121219890, None, "declaraciones en conferencia de prensa"),
    "clip_012": (121219891, (0, 240), "declaraciones en conferencia de prensa"),
    "clip_013": (149433722, None, "entrevista en una fiesta patronal (Áncash)"),
    "clip_014": (149433723, None, "entrevista en una fiesta patronal (Áncash)"),
    "clip_015": (149445104, None, "entrevista en una fiesta patronal (Áncash)"),
    "clip_016": ("Es-Huaca El Retablo-Comas-article2.oga", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_017": ("Huaca Mateo Salado, cultura Yschma en 4 minutos audio.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_018": ("Es-Huaca Puente Inca-article.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_019": ("Es-Huaca Santa Rosa-article.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_020": ("Audio de la Huaca Sinchi Roca.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_021": ("Es-Huaca Garagay-article.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_022": ("Es-Huaca El Sauce-article.ogg", (0, 90), "lectura de artículo de Wikipedia"),
    "clip_023": ("Es-Huaca Tambo Inga 20-article.oga", (0, 90), "lectura de artículo de Wikipedia"),
}

# Títulos publicables de los archivos que se piden por curid (el nombre real queda fuera del repo)
TITULOS_SEUDONIMIZADOS = {
    "clip_009": "UNMSM Entrevista realizada en la marcha por [ENTREVISTADOR_4].wav",
    "clip_010": "UNMSM Entrevistas en la marcha 1 por [ENTREVISTADOR_4].wav",
    "clip_011": "Entrevista-[ENTREVISTADA_1]-organización de mujeres indígenas-fiestas patrias.ogg",
    "clip_012": "Entrevista a [ENTREVISTADA_2]-Organización de mujeres indígenas-fiestas patrias-protesta.ogg",
    "clip_013": "Entrevista a la señora [ENTREVISTADA_3], mujer pomabambina.ogg",
    "clip_014": "Entrevista a la señora [ENTREVISTADA_4], mujer shuyasina.ogg",
    "clip_015": "Entrevista a [ENTREVISTADA_5], organizadora de la fiesta patronal de Tayta Palli de Chuyas.ogg",
}


def _pedir(url: str, intentos: int = 5) -> bytes:
    """GET con pausa de cortesía; si Commons responde 429, espera lo que pide y reintenta."""
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                datos = r.read()
            time.sleep(PAUSA)
            return datos
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 60))
    raise RuntimeError(f"Commons sigue respondiendo 429: {url}")


def _info(titulo: str | int, pagina: int | None = None) -> dict:
    """URL de descarga, licencia y autor de un archivo de Commons (por título o por curid)."""
    clave = {"pageids": titulo} if isinstance(titulo, int) else {"titles": "File:" + titulo}
    p = {"action": "query", **clave, "prop": "imageinfo", "format": "json", "formatversion": 2,
         "iiprop": "url|mime|size|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal"}
    if pagina is not None:
        p["iiurlwidth"] = ANCHO
        if titulo.lower().endswith((".pdf", ".djvu")):
            p["iiurlparam"] = f"page{pagina}-{ANCHO}px"
    ii = json.loads(_pedir(API + "?" + urllib.parse.urlencode(p)))["query"]["pages"][0]["imageinfo"][0]
    meta = {k: re.sub(r"<[^>]+>", "", v.get("value", "")).strip() for k, v in ii.get("extmetadata", {}).items()}
    return {"url": ii.get("thumburl") or ii["url"], "licencia": meta.get("LicenseShortName", ""),
            "autor": " ".join(meta.get("Artist", "").split()), "fecha_original": meta.get("DateTimeOriginal", ""),
            "fuente_url": f"https://commons.wikimedia.org/?curid={titulo}" if isinstance(titulo, int)
            else "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(titulo.replace(" ", "_"))}


def bajar_documentos() -> pd.DataFrame:
    destino = RAW / "documentos"
    destino.mkdir(parents=True, exist_ok=True)
    filas = []
    for id_, (tipo, titulo, pagina, desc) in DOCUMENTOS.items():
        info = _info(titulo, pagina)
        ext = Path(urllib.parse.urlparse(info["url"]).path).suffix.lower()
        ruta = destino / f"{id_}{'.jpg' if ext == '.jpeg' else ext}"
        if not ruta.exists():
            ruta.write_bytes(_pedir(info["url"]))
        filas.append({"id": id_, "modalidad": "documento", "tipo": tipo, "descripcion": desc,
                      "archivo": ruta.relative_to(CARPETA).as_posix(), "titulo_original": titulo,
                      "pagina": pagina if titulo.lower().endswith((".pdf", ".djvu")) else None, **info})
        print(f"  {id_} {tipo:<10} {info['licencia']:<16} {desc}")
    return pd.DataFrame(filas)


def bajar_audios() -> pd.DataFrame:
    """Baja cada audio original y guarda el clip (recortado si corresponde) en WAV mono de 16 kHz."""
    from voz import SR, cargar_audio
    originales, destino = RAW / "audio" / "originales", RAW / "audio"
    originales.mkdir(parents=True, exist_ok=True)
    filas = []
    for id_, (titulo, recorte, condicion) in AUDIOS.items():
        info = _info(titulo)
        original = originales / f"{id_}{Path(urllib.parse.urlparse(info['url']).path).suffix.lower()}"
        if not original.exists():
            original.write_bytes(_pedir(info["url"]))
        ruta = destino / f"{id_}.wav"
        if not ruta.exists():
            x = cargar_audio(original)
            if recorte:
                x = x[int(recorte[0] * SR):int(recorte[1] * SR)]
            sf.write(ruta, x, SR)
        duracion = sf.info(ruta).duration
        filas.append({"id": id_, "modalidad": "audio", "descripcion": condicion,
                      "archivo_audio": ruta.relative_to(CARPETA).as_posix(),
                      "titulo_original": TITULOS_SEUDONIMIZADOS.get(id_, titulo),
                      "recorte": f"{recorte[0]}-{recorte[1]} s" if recorte else "completo",
                      "duracion_seg": round(duracion, 1), **info})
        print(f"  {id_} {duracion:6.1f} s  {info['licencia']:<12} {condicion}")
    return pd.DataFrame(filas)


def fuentes(docs: pd.DataFrame, audios: pd.DataFrame) -> pd.DataFrame:
    """Tabla de fuentes: de dónde sale cada archivo, con qué licencia y cómo recuperarlo."""
    hoy = date.today().isoformat()
    tabla = pd.concat([docs, audios], ignore_index=True)
    tabla["acceso"] = ("Descarga pública desde Wikimedia Commons; se recupera con `uv run python corpus.py` "
                       + tabla["recorte"].map(lambda r: "" if pd.isna(r) or r == "completo" else f"(recorte {r}) ").fillna(""))
    tabla["fecha_descarga"] = hoy
    return tabla[["id", "modalidad", "fuente_url", "licencia", "autor", "acceso", "titulo_original", "fecha_descarga"]]


def ejemplos() -> pd.DataFrame:
    """Muestra ligera y publicable para el dashboard (datos/ejemplos/): imágenes reducidas y clips en OGG.

    Solo entran los archivos sin personas privadas (sin entradas en el mapa de seudónimos): los
    demás se consultan en el dashboard como texto y metadatos, nunca como imagen o audio.
    """
    from PIL import Image
    from voz import SR, cargar_audio
    privados = set(json.loads((RAW / "seudonimos.json").read_text(encoding="utf-8")))
    destino = CARPETA / "datos" / "ejemplos"
    destino.mkdir(parents=True, exist_ok=True)
    filas = []
    for ruta in sorted((RAW / "documentos").glob("doc_*.jpg")):
        if ruta.stem in privados:
            continue
        imagen = Image.open(ruta).convert("RGB")
        imagen.thumbnail((1200, 1600))
        salida = destino / f"{ruta.stem}.jpg"
        imagen.save(salida, quality=80, optimize=True)
        filas.append({"id": ruta.stem, "archivo": salida.relative_to(CARPETA).as_posix()})
    for ruta in sorted((RAW / "audio").glob("clip_*.wav")):
        if ruta.stem in privados:
            continue
        salida = destino / f"{ruta.stem}.ogg"
        audio = cargar_audio(ruta)
        with sf.SoundFile(salida, "w", SR, 1, format="OGG", subtype="VORBIS") as f:
            for i in range(0, len(audio), 4096):   # por bloques: de un solo golpe, libsndfile desborda la pila en Windows
                f.write(audio[i:i + 4096])
        filas.append({"id": ruta.stem, "archivo": salida.relative_to(CARPETA).as_posix()})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(destino / "ejemplos.csv", index=False)
    return tabla


if __name__ == "__main__" and sys.argv[1:] == ["ejemplos"]:
    t = ejemplos()
    print(f"{len(t)} ejemplos publicables en datos/ejemplos/")
elif __name__ == "__main__":
    print("Documentos:")
    docs = bajar_documentos()
    print("Audios:")
    audios = bajar_audios()
    tabla = fuentes(docs, audios)
    tabla.to_csv(CARPETA / "datos" / "fuentes.csv", index=False)
    docs.to_csv(RAW / "documentos" / "catalogo.csv", index=False)
    audios.to_csv(RAW / "audio" / "catalogo.csv", index=False)
    print(f"\n{len(docs)} documentos · {len(audios)} clips · {audios['duracion_seg'].sum() / 60:.1f} min de audio")
    print("Licencias:", tabla["licencia"].value_counts().to_dict())
