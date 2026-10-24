"""Parte 2 de la Tarea 2: modelos alternativos, métricas y extracción estructurada con un LLM.

Lo usa 02_evaluacion.ipynb. Igual que extraccion.py, cada salida cruda queda como respaldo en
datos/raw/ y no se recalcula si ya existe, así que se puede correr por tandas desde la terminal:

    uv run python evaluacion.py config                 # escribe modelos/configuracion.json
    uv run python evaluacion.py easyocr doc_001 ...    # sin ids: los 10 de la muestra
    uv run python evaluacion.py qwen clip_001 ...
    uv run python evaluacion.py llm doc_001 clip_001 ...   # sin ids: los 48 textos

Las configuraciones de abajo se fijaron ANTES de calcular cualquier CER/WER y no se tocan
después (el enunciado prohíbe ajustar parámetros mirando las métricas de la muestra).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd

import voz

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "datos"
RAW = DATOS / "raw"
DOCS, AUDIO = RAW / "documentos", RAW / "audio"
REFERENCIAS = DATOS / "referencias"

# ───────────────────────────────────────────────────────── muestra de evaluación (Parte 1, día 2)
MUESTRA_DOCS = ["doc_001", "doc_002", "doc_008",                 # impresos
                "doc_009", "doc_012", "doc_013", "doc_015",      # fotos
                "doc_020", "doc_022", "doc_024"]                 # manuscritos
MUESTRA_CLIPS = ["clip_001", "clip_002", "clip_003", "clip_006", "clip_008",
                 "clip_009", "clip_013", "clip_015", "clip_016", "clip_020"]

# ───────────────────────────────────────────────────────── configuraciones fijas
# OCR alternativo: EasyOCR (detector CRAFT + reconocedor CRNN "latin_g2"), en CPU y con sus
# valores por defecto. Misma imagen que recibió PaddleOCR, sin preprocesamiento.
EASYOCR = dict(idiomas=["es"], gpu=False, readtext={})
# ASR alternativo: Qwen3-ASR 0.6B (transformers) en CPU, float32, idioma fijado en español.
# El audio largo se corta con el mismo VAD de Silero de voz.py (pausas de 0,3 s, tramos de 12 s máx.).
QWEN = dict(clave="qwen3-asr-0.6b", device="cpu", idioma="es", silencio_min=0.3, max_tramo=12.0)
# LLM: Gemini Flash-Lite (capa gratuita), temperatura 0 y salida JSON validada con un esquema.
MODELOS_LLM = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]   # el segundo, solo si el primero falla
PAUSA_LLM = 4.0   # segundos entre pedidos (la capa gratuita limita los pedidos por minuto)


def configuracion() -> dict:
    """Todo lo que define cada modelo comparado, para guardarlo en modelos/configuracion.json."""
    import easyocr
    import faster_whisper
    import paddleocr
    import transformers

    import extraccion as ex
    return {
        "fijada": "2026-10-24, antes de calcular CER/WER sobre la muestra",
        "muestra": {"documentos": MUESTRA_DOCS, "clips": MUESTRA_CLIPS},
        "ocr": {
            "base": {"modelo": ex.nombre_modelo_ocr(), "opciones": ex.OPCIONES_OCR},
            "alternativo": {"modelo": nombre_easyocr(), "version": easyocr.__version__, **EASYOCR},
        },
        "asr": {
            "base": {"modelo": ex.nombre_modelo_asr(), "version": faster_whisper.__version__},
            "alternativo": {"modelo": nombre_qwen(), "hf": voz.MODELOS[QWEN["clave"]]["hf"],
                            "transformers": transformers.__version__, **QWEN},
        },
        "llm": {"modelos": MODELOS_LLM, "temperatura": 0, "salida": "JSON con esquema (pydantic)",
                "prompt_documento": PROMPT_DOCUMENTO, "prompt_audio": PROMPT_AUDIO},
        "metricas": {
            "normalizacion": "voz.normalizar: minúsculas, sin puntuación ni espacios repetidos; tildes se conservan",
            "referencia": "se quitan las marcas de hablante (h1:, h2.) y las anotaciones entre corchetes ([?], [risas])",
            "hipotesis": "se quitan las marcas [HABLANTE_n] de la diarización",
            "seudonimos": "referencia e hipótesis se seudonimizan con el mismo mapa antes de medir",
            "agregado": "CER/WER de corpus (errores totales / largo total de las referencias) y por archivo",
        },
        "versiones": {"paddleocr": paddleocr.__version__},
    }


# ───────────────────────────────────────────────────────── OCR alternativo: EasyOCR
def nombre_easyocr() -> str:
    import easyocr
    return f"EasyOCR {easyocr.__version__} (CRAFT + latin_g2, lang=es, CPU, valores por defecto)"


def cargar_easyocr():
    import easyocr
    return easyocr.Reader(EASYOCR["idiomas"], gpu=EASYOCR["gpu"], verbose=False)


def easyocr_documento(id_: str, lector=None) -> dict:
    """OCR de una imagen con EasyOCR. El resultado crudo queda en datos/raw/documentos/ocr_easyocr/."""
    respaldo = DOCS / "ocr_easyocr" / f"{id_}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    lector = lector or cargar_easyocr()
    t0 = time.perf_counter()
    r = lector.readtext(str(DOCS / f"{id_}.jpg"), **EASYOCR["readtext"])
    segundos = time.perf_counter() - t0
    salida = {"id": id_, "modelo": nombre_easyocr(), "segundos": round(segundos, 1),
              "lineas": [t for _, t, _ in r], "confianzas": [round(float(c), 3) for _, _, c in r],
              "cajas": [[[int(x), int(y)] for x, y in caja] for caja, _, _ in r]}
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


# ───────────────────────────────────────────────────────── ASR alternativo: Qwen3-ASR
def nombre_qwen() -> str:
    return f"Qwen3-ASR 0.6B (transformers, CPU float32, VAD Silero, idioma={QWEN['idioma']})"


def cargar_qwen() -> voz.Transcriptor:
    return voz.Transcriptor(QWEN["clave"], device=QWEN["device"])


def qwen_clip(id_: str, transcriptor: voz.Transcriptor | None = None) -> dict:
    """VAD + transcripción con Qwen3-ASR. El resultado crudo queda en datos/raw/audio/asr_qwen/."""
    respaldo = AUDIO / "asr_qwen" / f"{id_}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    transcriptor = transcriptor or cargar_qwen()
    audio = voz.cargar_audio(AUDIO / f"{id_}.wav")
    t0 = time.perf_counter()
    segmentos = transcriptor.segmentos(audio, idioma=QWEN["idioma"], silencio_min=QWEN["silencio_min"],
                                       max_tramo=QWEN["max_tramo"])
    segundos = time.perf_counter() - t0
    salida = {"id": id_, "modelo": nombre_qwen(), "duracion_seg": round(len(audio) / voz.SR, 1),
              "segundos_asr": round(segundos, 1), "segmentos": voz.a_tabla(segmentos).to_dict(orient="records")}
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


# ───────────────────────────────────────────────────────── métricas
MARCA_REFERENCIA = re.compile(r"^\s*h\d+\s*[:.]\s*", re.IGNORECASE | re.MULTILINE)   # h1: / h2.
ANOTACION = re.compile(r"\[[^\]]*\]")                                               # [?] [risas]
MARCA_HABLANTE = re.compile(r"\[HABLANTE_\d+\]")


def leer_referencia(id_: str) -> str:
    """Transcripción manual tal como la escribió el autor (con nombres reales: no se publica así)."""
    return (REFERENCIAS / f"{id_}.txt").read_text(encoding="utf-8").strip()


def limpiar_referencia(texto: str) -> str:
    """Solo lo que se lee o se dice: sin marcas de hablante ni anotaciones. Los [ETIQUETA_n] de
    los seudónimos se protegen, porque reemplazan a un nombre que sí se dijo."""
    protegidos = re.findall(r"\[[A-Z]+_\d+\]", texto)
    texto = re.sub(r"\[[A-Z]+_\d+\]", "\0", MARCA_REFERENCIA.sub("", texto))
    texto = ANOTACION.sub(" ", texto)
    for p in protegidos:
        texto = texto.replace("\0", p, 1)
    return texto


def limpiar_hipotesis(texto: str) -> str:
    return MARCA_HABLANTE.sub(" ", texto or "")


def por_archivo(referencias: dict[str, str], hipotesis: dict[str, str], metrica) -> pd.Series:
    return pd.Series({i: metrica([referencias[i]], [hipotesis.get(i, "")]) for i in referencias})


# ───────────────────────────────────────────────────────── extracción estructurada con el LLM
PROMPT_DOCUMENTO = """Eres un archivista peruano. Recibes el texto que un OCR extrajo de un documento
escaneado o fotografiado (impreso, foto de celular o manuscrito, a veces de los siglos XIX o XX).
El OCR comete errores: no los corrijas inventando, y si una parte es ilegible no la reconstruyas.

Devuelve SOLO estos campos, basándote únicamente en el texto:
- modalidad: siempre "documento".
- tema: el asunto principal en pocas palabras (máximo 8).
- resumen: una o dos oraciones con lo que dice el documento.
- emisor: quien firma, escribe o publica el documento, tal como aparece; null si no aparece.
- fecha: la fecha del documento tal como aparece en el texto; null si no aparece.
- monto: una cantidad de dinero con su moneda, tal como aparece; null si no hay ninguna.
Usa null para todo dato ausente. No agregues campos. Las etiquetas como [PERSONA_1] son
seudónimos de personas reales: cópialas tal cual, no intentes adivinar el nombre."""

PROMPT_AUDIO = """Eres un archivista de historia oral peruana. Recibes la transcripción automática
(ASR) de un clip de audio en español. Las marcas [HABLANTE_n] vienen de una diarización automática
que puede equivocarse (juntar o dividir voces). El ASR también comete errores: no los corrijas inventando.

Devuelve SOLO estos campos, basándote únicamente en la transcripción:
- modalidad: siempre "audio".
- tema: el asunto principal en pocas palabras (máximo 8).
- resumen: una o dos oraciones con lo que se dice en el clip.
- numero_hablantes: cuántas personas distintas hablan, solo si el contenido lo sustenta
  (turnos de pregunta y respuesta, saludos, nombres); null si no se puede saber.
- citas_clave: de 1 a 3 frases textuales copiadas EXACTAMENTE de la transcripción, que resuman
  lo más importante; null si no hay ninguna frase con sentido.
Usa null para todo dato ausente. No agregues campos. Las etiquetas como [ENTREVISTADA_1] son
seudónimos de personas reales: cópialas tal cual, no intentes adivinar el nombre."""


def _esquemas():
    from typing import Literal, Optional

    from pydantic import BaseModel, Field

    class Documento(BaseModel):
        modalidad: Literal["documento"]
        tema: str
        resumen: str
        emisor: Optional[str]
        fecha: Optional[str]
        monto: Optional[str]

    class Audio(BaseModel):
        modalidad: Literal["audio"]
        tema: str
        resumen: str
        numero_hablantes: Optional[int]
        citas_clave: Optional[list[str]] = Field(max_length=3)

    return Documento, Audio


def cliente_llm():
    from dotenv import load_dotenv
    from google import genai
    load_dotenv(CARPETA / ".env")
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def extraer_campos(id_: str, texto: str, cliente=None) -> dict:
    """Campos JSON de un texto YA seudonimizado (nunca se envían nombres reales a la API).
    La respuesta cruda queda en datos/raw/llm/."""
    respaldo = RAW / "llm" / f"{id_}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    from google.genai import types
    Documento, Audio = _esquemas()
    es_doc = id_.startswith("doc_")
    config = types.GenerateContentConfig(
        system_instruction=PROMPT_DOCUMENTO if es_doc else PROMPT_AUDIO, temperature=0,
        response_mime_type="application/json", response_schema=Documento if es_doc else Audio)
    cliente = cliente or cliente_llm()
    pedido = f"{'Texto OCR' if es_doc else 'Transcripción'} ({id_}):\n\n{texto}"
    for modelo in MODELOS_LLM:
        for intento in range(3):
            try:
                t0 = time.perf_counter()
                resp = cliente.models.generate_content(model=modelo, contents=pedido, config=config)
                campos = resp.parsed.model_dump()
                salida = {"id": id_, "modelo_llm": modelo, "fecha": time.strftime("%Y-%m-%d"),
                          "segundos": round(time.perf_counter() - t0, 1), "campos": campos}
                respaldo.parent.mkdir(parents=True, exist_ok=True)
                respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
                return salida
            except Exception as e:   # 503 saturado, 429 cuota, respuesta que no cumple el esquema...
                print(f"    {id_} {modelo}: {type(e).__name__}: {str(e)[:120]} (intento {intento + 1})", flush=True)
                time.sleep(15 * (intento + 1))
    raise RuntimeError(f"Ningún modelo respondió para {id_}")


def textos_publicados() -> dict[str, str]:
    """Los textos OCR y ASR ya seudonimizados y revisados de la Parte 1 (los de los CSV)."""
    docs = pd.read_csv(DATOS / "documentos.csv")
    clips = pd.read_csv(DATOS / "transcripciones.csv")
    return {**dict(zip(docs.id, docs.texto_ocr.fillna(""))), **dict(zip(clips.id, clips.texto_asr.fillna("")))}


# ───────────────────────────────────────────────────────── por tandas desde la terminal
if __name__ == "__main__":
    tarea, ids = sys.argv[1], sys.argv[2:]
    if tarea == "config":
        ruta = CARPETA / "modelos" / "configuracion.json"
        ruta.write_text(json.dumps(configuracion(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"escrito {ruta.relative_to(CARPETA)}")
    elif tarea == "easyocr":
        ids = ids or MUESTRA_DOCS
        pendientes = [i for i in ids if not (DOCS / "ocr_easyocr" / f"{i}.json").exists()]
        lector = cargar_easyocr() if pendientes else None
        for i in pendientes:
            r = easyocr_documento(i, lector)
            print(f"{i}: {len(r['lineas'])} líneas en {r['segundos']} s", flush=True)
    elif tarea == "qwen":
        ids = ids or MUESTRA_CLIPS
        pendientes = [i for i in ids if not (AUDIO / "asr_qwen" / f"{i}.json").exists()]
        modelo = cargar_qwen() if pendientes else None
        for i in pendientes:
            r = qwen_clip(i, modelo)
            print(f"{i}: {r['duracion_seg']} s de audio en {r['segundos_asr']} s "
                  f"(factor de tiempo real {r['segundos_asr'] / r['duracion_seg']:.2f})", flush=True)
    elif tarea == "llm":
        textos = textos_publicados()
        ids = ids or sorted(textos)
        pendientes = [i for i in ids if not (RAW / "llm" / f"{i}.json").exists()]
        cliente = cliente_llm() if pendientes else None
        for i in pendientes:
            r = extraer_campos(i, textos[i], cliente)
            print(f"{i}: {r['modelo_llm']} en {r['segundos']} s", flush=True)
            time.sleep(PAUSA_LLM)
    else:
        raise SystemExit("uso: python evaluacion.py config|easyocr|qwen|llm [ids...]")
