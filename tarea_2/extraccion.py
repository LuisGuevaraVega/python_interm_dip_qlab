"""Parte 1 de la Tarea 2: OCR de los documentos y transcripción de los audios.

Lo usa 01_extraccion.ipynb. Cada archivo se procesa una sola vez y su resultado crudo queda
como respaldo en datos/raw/ (no se versiona): si el respaldo ya existe, se lee en vez de volver
a correr el modelo. Así el corpus se puede procesar por tandas desde la terminal, sin que una
laptop con poca RAM tenga que hacerlo todo en una sola sesión del notebook:

    uv run python extraccion.py ocr doc_001 doc_002 ...     # sin ids: todos los pendientes
    uv run python extraccion.py asr clip_001 ...
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"  # no probar la conexión a cada servidor de modelos
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from PIL import Image

import voz

CARPETA = Path(__file__).resolve().parent
RAW = CARPETA / "datos" / "raw"
DOCS, AUDIO = RAW / "documentos", RAW / "audio"

# OCR: la configuración base de PaddleOCR (PP-OCRv6), con el motor nativo de Paddle en CPU.
# Sin preprocesamiento: no se gira la página, no se "plancha" la hoja ni se gira cada línea.
OPCIONES_OCR = dict(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
# ASR: faster-whisper small en CPU (int8), con VAD de Silero; idioma fijado en español.
MODELO_ASR = "small"
IDIOMA = "es"


# ───────────────────────────────────────────────────────── OCR
def cargar_ocr():
    import logging
    from paddleocr import PaddleOCR
    for nombre in ("paddlex", "paddleocr"):
        logging.getLogger(nombre).setLevel(logging.ERROR)
    return PaddleOCR(device="cpu", **OPCIONES_OCR)


def nombre_modelo_ocr(ocr=None) -> str:
    import paddleocr
    p = getattr(ocr, "_params", {}) if ocr is not None else {}
    det = p.get("text_detection_model_name") or "PP-OCRv6_medium_det"
    rec = p.get("text_recognition_model_name") or "PP-OCRv6_medium_rec"
    return f"PaddleOCR {paddleocr.__version__} ({det} + {rec}, CPU, sin preprocesamiento)"


def ocr_documento(id_: str, ocr=None) -> dict:
    """OCR de una imagen. Guarda el resultado crudo (JSON), la imagen con las cajas y un recorte por línea."""
    respaldo = DOCS / "ocr" / f"{id_}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    ocr = ocr or cargar_ocr()
    ruta = DOCS / f"{id_}.jpg"
    t0 = time.perf_counter()
    r = ocr.predict(str(ruta))[0]
    segundos = time.perf_counter() - t0
    cajas = np.asarray(r["rec_boxes"]).reshape(-1, 4).astype(int).tolist()   # x0, y0, x1, y1 de cada línea
    salida = {"id": id_, "modelo": nombre_modelo_ocr(ocr), "segundos": round(segundos, 1),
              "lineas": r["rec_texts"], "confianzas": [round(float(c), 3) for c in r["rec_scores"]], "cajas": cajas}
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    # recortes: la imagen con las cajas detectadas y cada línea por separado
    recortes = DOCS / "recortes" / id_
    recortes.mkdir(parents=True, exist_ok=True)
    r.save_to_img(str(recortes))
    imagen = Image.open(ruta).convert("RGB")
    for i, (x0, y0, x1, y1) in enumerate(cajas, 1):
        imagen.crop((x0, y0, x1, y1)).save(recortes / f"linea_{i:03d}.jpg", quality=85)
    return salida


# ───────────────────────────────────────────────────────── ASR
def cargar_asr() -> voz.Transcriptor:
    """El Transcriptor de voz.py, con faster-whisper small en vez de la variante turbo que trae por defecto."""
    voz.MODELOS["faster-whisper"] = {**voz.MODELOS["faster-whisper"], "nombre": f"faster-whisper {MODELO_ASR}", "hf": MODELO_ASR}
    return voz.Transcriptor("faster-whisper", device="cpu")


def nombre_modelo_asr() -> str:
    import faster_whisper
    return f"faster-whisper {faster_whisper.__version__} {MODELO_ASR} (CPU int8, beam 5, VAD Silero on, idioma={IDIOMA})"


def transcribir_clip(id_: str, transcriptor: voz.Transcriptor | None = None) -> dict:
    """VAD + transcripción + diarización de un clip. Guarda JSON (segmentos), SRT y TXT en datos/raw/audio/asr/."""
    respaldo = AUDIO / "asr" / f"{id_}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    transcriptor = transcriptor or cargar_asr()
    audio = voz.cargar_audio(AUDIO / f"{id_}.wav")
    t0 = time.perf_counter()
    segmentos = transcriptor.segmentos(audio, idioma=IDIOMA)
    s_asr = time.perf_counter() - t0
    t0 = time.perf_counter()
    segmentos = voz.diarizar(audio, segmentos, device="cpu")   # n_hablantes desconocido: decide el umbral
    s_diar = time.perf_counter() - t0
    salida = {"id": id_, "modelo": nombre_modelo_asr(), "duracion_seg": round(len(audio) / voz.SR, 1),
              "voz_seg": round(sum(b - a for a, b in voz.tramos_de_voz(audio)), 1),
              "segundos_asr": round(s_asr, 1), "segundos_diarizacion": round(s_diar, 1),
              "segmentos": voz.a_tabla(segmentos).to_dict(orient="records")}
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    (respaldo.with_suffix(".srt")).write_text(voz.a_srt(segmentos), encoding="utf-8")
    (respaldo.with_suffix(".txt")).write_text(voz.a_texto(segmentos), encoding="utf-8")
    return salida


def segmentos_de(asr: dict) -> list[voz.Segmento]:
    return [voz.Segmento(**s) for s in asr["segmentos"]]


# ───────────────────────────────────────────────────────── por tandas desde la terminal
if __name__ == "__main__":
    tarea, ids = sys.argv[1], sys.argv[2:]
    if tarea == "ocr":
        ids = ids or sorted(p.stem for p in DOCS.glob("doc_*.jpg"))
        pendientes = [i for i in ids if not (DOCS / "ocr" / f"{i}.json").exists()]
        modelo = cargar_ocr() if pendientes else None
        for i in pendientes:
            r = ocr_documento(i, modelo)
            print(f"{i}: {len(r['lineas'])} líneas en {r['segundos']} s", flush=True)
    elif tarea == "asr":
        ids = ids or sorted(p.stem for p in AUDIO.glob("clip_*.wav"))
        pendientes = [i for i in ids if not (AUDIO / "asr" / f"{i}.json").exists()]
        modelo = cargar_asr() if pendientes else None
        for i in pendientes:
            r = transcribir_clip(i, modelo)
            hablantes = len({s["hablante"] for s in r["segmentos"]})
            print(f"{i}: {r['duracion_seg']} s de audio en {r['segundos_asr']} s, {hablantes} hablante(s)", flush=True)
    else:
        raise SystemExit("uso: python extraccion.py ocr|asr [ids...]")
