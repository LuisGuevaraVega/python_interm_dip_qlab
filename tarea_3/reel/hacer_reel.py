"""El guion verificado se narra con mi voz clonada y se convierte en un reel vertical con figuras, música y subtítulos.

Adaptado de mi reel de incendios (github.com/LuisGuevaraVega/reel-incendios), que sigue la sesión 15 del curso.
Cambios: música de fondo bajo la voz, fuente de datos siempre visible, tarjeta final de créditos y colores del tablero.

Uso (con el entorno del reel; ver README.md de esta carpeta):
    python verificar_guion.py                                             # primero: las cifras salen de los datos
    python hacer_reel.py --voz privado/mi_voz.mp4 --texto-voz "…" --solo-voz   # narra las escenas
    python hacer_reel.py --solo-video                                     # audio + subtítulos + video

Salidas en salidas/: reel.mp4, reel.srt, portada.png, control_voz.json, tiempos.json
"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import jiwer
import numpy as np
import soundfile as sf
from num2words import num2words
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).parent
FIGS = RAIZ / "figuras"
SALIDAS = RAIZ / "salidas"
ESCENAS = SALIDAS / "escenas"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ANCHO, ALTO, FPS = 1080, 1920, 30
MARGEN = 72          # a los lados; a la derecha se deja más por los botones de la app
PAUSA = 0.3          # silencio entre escenas, en segundos
COLA = 5.0           # segundos extra para la tarjeta final de créditos
FUNDIDO = 8          # cuadros de transición entre escenas
PANEL = (600, 1340)  # franja vertical donde va la figura

# los colores del tablero en modo oscuro: superficie, tintas, azul (serie 1) y naranja (serie 2)
FONDO = (26, 26, 25)
TEXTO = (240, 239, 236)
TENUE = (195, 194, 183)
AZUL = (57, 135, 229)
NARANJA = (217, 89, 38)
MUSICA = RAIZ / "recursos" / "musica_clean_soul.mp3"
LUFS_VOZ, LUFS_MUSICA = -14, -29  # la música queda 15 LU por debajo de la voz

FUENTE = "C:/Windows/Fonts/bahnschrift.ttf"


def fuente(tamano, variante="Bold"):
    f = ImageFont.truetype(FUENTE, tamano)
    f.set_variation_by_name(variante)
    return f


# ---------------------------------------------------------------- audio

def a_wav(origen, destino, sr=24000, max_seg=25):
    """Convierte la nota de voz (m4a, ogg, mp3…) a wav mono y la recorta."""
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(origen), "-t", str(max_seg),
                    "-ac", "1", "-ar", str(sr), str(destino)], check=True)


def en_palabras(numero):
    if "," in numero or "." in numero:
        entero, dec = re.split(r"[.,]", numero)
        return f"{num2words(int(entero), lang='es')} coma {num2words(int(dec), lang='es')}"
    return num2words(int(numero), lang="es")


def normalizar_texto(texto):
    """Minúsculas, sin puntuación y con los dígitos en palabras, para medir el WER."""
    # Whisper escribe \u00ab1.475\u00bb y \u00ab98%\u00bb; el guion lo dice en palabras
    texto = re.sub(r"(?<=\d)[\s\u202f\u00a0.](?=\d{3}\b)", "", texto)
    texto = texto.replace("%", " por ciento")
    texto = re.sub(r"\d+(?:[.,]\d+)?", lambda m: en_palabras(m.group()), texto)
    texto = re.sub(r"[^\w\s]", " ", texto.lower())
    return " ".join(texto.split())


def transcribir(whisper, ruta, palabras=False):
    # Se le pasa el audio ya cargado: la versión de av instalada no acepta rutas en faster-whisper
    import librosa
    audio, _ = librosa.load(ruta, sr=16000, mono=True)
    segmentos, _ = whisper.transcribe(audio, language="es", word_timestamps=palabras, beam_size=5)
    segmentos = list(segmentos)
    texto = " ".join(s.text.strip() for s in segmentos)
    if not palabras:
        return texto
    return texto, [(w.word.strip(), w.start, w.end) for s in segmentos for w in s.words]


def recortar_silencio(wav, sr, umbral=0.01):
    """Quita el silencio del inicio y del final de cada escena."""
    voz = np.where(np.abs(wav) > umbral)[0]
    if len(voz) == 0:
        return wav
    a, b = max(voz[0] - int(0.05 * sr), 0), min(voz[-1] + int(0.12 * sr), len(wav))
    return wav[a:b]


def narrar(guion, voz, tts_id, device, intentos, texto_voz=None):
    import torch
    from faster_whisper import WhisperModel
    from qwen_tts import Qwen3TTSModel

    ESCENAS.mkdir(parents=True, exist_ok=True)
    ref = SALIDAS / "voz_ref.wav"
    a_wav(voz, ref)

    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    # Si se sabe qué se leyó, ese texto es mejor referencia que la transcripción
    ref_texto = texto_voz or transcribir(whisper, str(ref))
    print(f"Tu grabación dice: «{ref_texto}»")

    t0 = time.time()
    tts = Qwen3TTSModel.from_pretrained(tts_id, device_map=device, dtype=torch.float32)
    prompt = tts.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_texto)
    print(f"Modelo cargado en {time.time() - t0:.0f} s")

    registro = []
    for i, escena in enumerate(guion["escenas"], 1):
        mejor = None
        for intento in range(1, intentos + 1):
            t0 = time.time()
            wavs, sr = tts.generate_voice_clone(text=escena["frase"], language="Spanish",
                                                voice_clone_prompt=prompt)
            wav = recortar_silencio(wavs[0], sr)
            ruta = ESCENAS / f"escena_{i:02d}.wav"
            sf.write(ruta, wav, sr)
            calculo = time.time() - t0
            oido = transcribir(whisper, str(ruta))
            wer = jiwer.wer(normalizar_texto(escena["frase"]), normalizar_texto(oido))
            print(f"  escena {i} · intento {intento}: {len(wav) / sr:.1f} s de audio en {calculo:.0f} s · WER {wer:.0%}")
            if mejor is None or wer < mejor[0]:
                mejor = (wer, wav, oido, calculo)
            # Si Whisper entiende mal más del 25 % de las palabras, se genera de nuevo
            if wer <= 0.25:
                break
        wer, wav, oido, calculo = mejor
        sf.write(ESCENAS / f"escena_{i:02d}.wav", wav, sr)
        registro.append({"escena": i, "wer": round(wer, 3), "oido": oido, "segundos_audio": round(len(wav) / sr, 2),
                         "segundos_calculo": round(calculo, 1), "intentos": intento})
        if wer > 0.25:
            print(f"  ¡¡ escena {i} quedó con WER {wer:.0%}: escúchala antes de publicar")

    (SALIDAS / "control_voz.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return sr


def unir_audio(n_escenas):
    """Une las escenas con pausas, normaliza a −14 LUFS y devuelve dónde empieza cada una."""
    partes, tiempos, t = [np.zeros(int(0.3 * 24000), dtype=np.float32)], [], 0.3
    sr = 24000
    for i in range(1, n_escenas + 1):
        wav, sr = sf.read(ESCENAS / f"escena_{i:02d}.wav", dtype="float32")
        tiempos.append((t, t + len(wav) / sr))
        partes += [wav, np.zeros(int(PAUSA * sr), dtype=np.float32)]
        t += len(wav) / sr + PAUSA
    partes.append(np.zeros(int(COLA * sr), dtype=np.float32))
    crudo = SALIDAS / "reel_crudo.wav"
    sf.write(crudo, np.concatenate(partes), sr)
    # Ganancia hacia −14 LUFS con un limitador para los picos; como el limitador baja la sonoridad,
    # se mide la salida y se corrige la ganancia hasta quedar a menos de 0,3 LU
    def sonoridad(ruta):
        medida = subprocess.run([FFMPEG, "-hide_banner", "-i", str(ruta), "-af", "loudnorm=print_format=json",
                                 "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(json.loads(medida[medida.rfind("{"):medida.rfind("}") + 1])["input_i"])

    ganancia = -14 - sonoridad(crudo)
    for _ in range(4):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(crudo),
                        "-af", f"volume={ganancia:.2f}dB,alimiter=limit=0.84:level=false",
                        "-ar", "48000", str(SALIDAS / "reel.wav")], check=True)
        falta = -14 - sonoridad(SALIDAS / "reel.wav")
        if abs(falta) < 0.3:
            break
        ganancia += falta
    mezclar_musica(t + COLA)
    return tiempos, t + COLA


def mezclar_musica(total):
    """La música (CC BY 4.0) entra suave, queda 15 LU bajo la voz y se apaga en la tarjeta final."""
    filtro = (f"[1:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,aformat=channel_layouts=mono,"
              f"loudnorm=I={LUFS_MUSICA}:TP=-8:LRA=11,aresample=48000,"
              f"afade=t=in:d=2,afade=t=out:st={total - 3.5:.2f}:d=3.5[m];"
              f"[0:a][m]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(SALIDAS / "reel.wav"), "-i", str(MUSICA),
                    "-filter_complex", filtro, "-map", "[a]", "-ar", "48000", str(SALIDAS / "reel_final.wav")],
                   check=True)


def palabras_con_tiempo(guion, tiempos):
    """Tiempo de cada palabra del guion: se reparte según Whisper o, si no cuadra, según su largo."""
    from faster_whisper import WhisperModel
    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    salida = []
    for i, (escena, (ini, fin)) in enumerate(zip(guion["escenas"], tiempos), 1):
        palabras = escena["frase"].split()
        _, oidas = transcribir(whisper, str(ESCENAS / f"escena_{i:02d}.wav"), palabras=True)
        if len(oidas) == len(palabras):
            marcas = [(p, ini + a, ini + b) for p, (_, a, b) in zip(palabras, oidas)]
        else:
            pesos = np.array([len(p) + 1 for p in palabras], dtype=float)
            bordes = ini + (fin - ini) * np.concatenate([[0], np.cumsum(pesos) / pesos.sum()])
            marcas = [(p, bordes[k], bordes[k + 1]) for k, p in enumerate(palabras)]
        salida.append(marcas)
    return salida


CONECTORES = {"y", "e", "o", "de", "del", "en", "el", "la", "los", "las", "un", "una", "a", "al", "con",
              "por", "que", "se", "su", "mil", "entre", "para"}


def lineas_subtitulo(marcas, max_car=30):
    """Agrupa las palabras de una escena en bloques cortos para leer en el celular."""
    bloques, actual = [], []
    for m in marcas:
        largo = len(" ".join(p for p, _, _ in actual + [m]))
        # No se corta después de un conector («setenta y / cinco»), salvo que el bloque ya sea muy largo
        corta = largo > max_car and actual[-1][0].lower() not in CONECTORES if actual else False
        if actual and (corta or largo > max_car + 12 or actual[-1][0][-1] in ".,;:?"):
            bloques.append(actual)
            actual = []
        actual.append(m)
    if actual:
        bloques.append(actual)
    return bloques


def srt(bloques, ruta):
    def ts(s):
        return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(s * 1000 % 1000):03d}"
    filas = []
    for k, b in enumerate(bloques, 1):
        filas.append(f"{k}\n{ts(b[0][1])} --> {ts(b[-1][2])}\n{' '.join(p for p, _, _ in b)}\n")
    ruta.write_text("\n".join(filas), encoding="utf-8")


# ---------------------------------------------------------------- video

def preparar_figura(nombre):
    """Escala la figura para cubrir el panel; si sobra por un lado, se recorre durante la escena."""
    img = Image.open(FIGS / f"{nombre}.png").convert("RGB")
    alto_panel = PANEL[1] - PANEL[0]
    escala = max(ANCHO / img.width, alto_panel / img.height)
    return img.resize((round(img.width * escala), round(img.height * escala)), Image.LANCZOS)


def cuadro_figura(img, avance):
    """Recorte del panel en el instante `avance` (0 a 1), con movimiento suave."""
    alto_panel = PANEL[1] - PANEL[0]
    e = 0.5 - 0.5 * np.cos(np.pi * avance)
    x = round((img.width - ANCHO) * e)
    y = round((img.height - alto_panel) * e)
    return img.crop((x, y, x + ANCHO, y + alto_panel))


def texto_ajustado(draw, texto, f, ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=f) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    return lineas + [actual] if actual else lineas


class Lienzo:
    def __init__(self, guion, autor, enlace):
        self.guion, self.autor, self.enlace = guion, autor, enlace
        self.f_autor = fuente(34, "SemiBold")
        self.f_ia = fuente(28, "Bold")
        self.f_cifra = fuente(190, "Bold Condensed")
        self.f_etiqueta = fuente(50, "SemiBold")
        self.f_sub = fuente(64, "Bold")
        self.f_titulo = fuente(96, "Bold Condensed")
        self.f_enlace = fuente(40, "SemiBold")
        self.f_fuente = fuente(30, "SemiBold")
        self.f_credito = fuente(31, "Regular")
        self.base = self._base()

    def _base(self):
        """Lo que se ve todo el tiempo: fondo, autor y aviso de IA."""
        img = Image.new("RGB", (ANCHO, ALTO), FONDO)
        d = ImageDraw.Draw(img)
        d.text((MARGEN, 150), self.autor, font=self.f_autor, fill=TENUE)
        aviso = "VOZ GENERADA CON IA"
        w = d.textlength(aviso, font=self.f_ia)
        x = ANCHO - MARGEN - w - 28
        d.rounded_rectangle((x, 144, ANCHO - MARGEN, 196), radius=26, outline=NARANJA, width=3)
        d.text((x + 14, 154), aviso, font=self.f_ia, fill=NARANJA)
        d.text((MARGEN, 1592), f"Datos: {self.guion['fuente']}", font=self.f_fuente, fill=TENUE)
        return img

    def cifra(self, d, escena, alfa):
        cifra = escena.get("cifra", "").replace("¡¡", "")
        color = tuple(round(FONDO[k] + (c - FONDO[k]) * alfa) for k, c in enumerate(AZUL))
        claro = tuple(round(FONDO[k] + (c - FONDO[k]) * alfa) for k, c in enumerate(TEXTO))
        y = 250
        if cifra:
            f = self.f_cifra
            while d.textlength(cifra, font=f) > ANCHO - 2 * MARGEN and f.size > 90:
                f = fuente(f.size - 10, "Bold Condensed")
            d.text((MARGEN, y + (190 - f.size) // 2), cifra, font=f, fill=color)
            y += 215
        for linea in texto_ajustado(d, escena.get("etiqueta", ""), self.f_etiqueta, ANCHO - 2 * MARGEN - 60)[:2]:
            d.text((MARGEN, y), linea, font=self.f_etiqueta, fill=claro)
            y += 60

    def subtitulo(self, d, bloque, t):
        lineas, actual = [], []
        for m in bloque:
            prueba = " ".join(p for p, _, _ in actual + [m])
            if actual and d.textlength(prueba, font=self.f_sub) > ANCHO - 2 * MARGEN - 80:
                lineas.append(actual)
                actual = []
            actual.append(m)
        lineas.append(actual)
        # Solo una palabra en naranja: la última que empezó a sonar (los tiempos de Whisper se traslapan)
        empezadas = [m for m in bloque if m[1] <= t]
        suena = empezadas[-1] if empezadas and t < empezadas[-1][2] + 0.25 else None
        y = 1395
        for linea in lineas:
            x = MARGEN
            for m in linea:
                p = m[0]
                color = NARANJA if m is suena else TEXTO
                d.text((x, y), p, font=self.f_sub, fill=color, stroke_width=3, stroke_fill=FONDO)
                x += d.textlength(p + " ", font=self.f_sub)
            y += 80

    def final(self, d, alfa):
        claro = tuple(round(FONDO[k] + (c - FONDO[k]) * alfa) for k, c in enumerate(TEXTO))
        azul = tuple(round(FONDO[k] + (c - FONDO[k]) * alfa) for k, c in enumerate(AZUL))
        tenue = tuple(round(FONDO[k] + (c - FONDO[k]) * alfa) for k, c in enumerate(TENUE))
        d.rectangle((0, 1350, ANCHO, 1720), fill=FONDO)  # la fuente fija pasa a la lista de créditos
        d.text((MARGEN, 1372), "Explora el tablero interactivo", font=self.f_etiqueta, fill=claro)
        y = 1436
        # la URL no tiene espacios: se corta después de cada «/»
        for linea in texto_ajustado(d, re.sub(r"/", "/ ", self.enlace), self.f_enlace, ANCHO - 2 * MARGEN):
            linea = linea.replace("/ ", "/")
            d.text((MARGEN, y), linea, font=self.f_enlace, fill=azul)
            y += 48
        creditos = [f"Datos: {self.guion['fuente']}",
                    "Voz generada con IA (Qwen3-TTS) a partir de mi propia voz",
                    "Música: «Clean Soul», de Kevin MacLeod · CC BY 4.0"]
        y += 14
        for c in creditos:
            for linea in texto_ajustado(d, c, self.f_credito, ANCHO - 2 * MARGEN):
                d.text((MARGEN, y), linea, font=self.f_credito, fill=tenue)
                y += 38


def renderizar(guion, tiempos, total, marcas, autor, enlace, destino):
    lienzo = Lienzo(guion, autor, enlace)
    figuras = {}
    for e in guion["escenas"]:
        if e["figura"] not in figuras:
            figuras[e["figura"]] = preparar_figura(e["figura"])
    bloques = [lineas_subtitulo(m) for m in marcas]

    # Cada escena ocupa de su inicio al inicio de la siguiente; la última se estira hasta el final
    cortes = [ini for ini, _ in tiempos] + [total]
    cortes[0] = 0.0
    n = round(total * FPS)

    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
                             "-i", str(SALIDAS / "reel_final.wav"),
                             "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(destino)],
                            stdin=subprocess.PIPE)
    t0 = time.time()
    portada = None
    for k in range(n):
        t = k / FPS
        i = max(j for j in range(len(tiempos)) if cortes[j] <= t)
        ini, fin = cortes[i], cortes[i + 1]
        avance = (t - ini) / (fin - ini)
        img = lienzo.base.copy()

        panel = cuadro_figura(figuras[guion["escenas"][i]["figura"]], avance)
        # Fundido con la escena anterior en los primeros cuadros
        dentro = (t - ini) * FPS
        if i > 0 and dentro < FUNDIDO:
            previa = cuadro_figura(figuras[guion["escenas"][i - 1]["figura"]], 1.0)
            panel = Image.blend(previa, panel, dentro / FUNDIDO)
        img.paste(panel, (0, PANEL[0]))
        sombra = Image.new("L", (ANCHO, 40))
        for y in range(40):
            ImageDraw.Draw(sombra).line([(0, y), (ANCHO, y)], fill=round(180 * (1 - y / 40)))
        img.paste(FONDO, (0, PANEL[0], ANCHO, PANEL[0] + 40), sombra)

        d = ImageDraw.Draw(img)
        lienzo.cifra(d, guion["escenas"][i], min(1.0, dentro / 6))

        ultimo = i == len(tiempos) - 1
        habla = [b for b in bloques[i] if b[0][1] - 0.1 <= t]
        if ultimo and t > tiempos[i][1] + 0.2:
            lienzo.final(d, min(1.0, (t - tiempos[i][1] - 0.2) * 3))
        elif habla:
            lienzo.subtitulo(d, habla[-1], t)

        # Barra de avance por escena, arriba de la zona de botones (no va en la tarjeta final)
        ancho_barra = (ANCHO - 2 * MARGEN) / len(tiempos)
        for j in range(len(tiempos) if not (ultimo and t > tiempos[i][1] + 0.2) else 0):
            x0 = MARGEN + j * ancho_barra
            d.rectangle((x0 + 3, 1560, x0 + ancho_barra - 3, 1566), fill=AZUL if j <= i else (60, 60, 64))

        if portada is None and i == 0 and dentro >= 6:
            portada = img.copy()
        proc.stdin.write(img.tobytes())
        if k % (FPS * 10) == 0:
            print(f"  video: {t:.0f}/{total:.0f} s ({time.time() - t0:.0f} s)")
    proc.stdin.close()
    proc.wait()
    return portada


def hacer_portada(guion, autor, primer_cuadro):
    """Portada: el primer cuadro con el título encima, para la miniatura del reel."""
    img = primer_cuadro.copy()
    d = ImageDraw.Draw(img)
    f = fuente(96, "Bold Condensed")
    lineas = texto_ajustado(d, guion["titulo"], f, ANCHO - 2 * MARGEN)
    alto = 40 + 110 * len(lineas)
    d.rectangle((0, 1380, ANCHO, 1380 + alto + 40), fill=FONDO)
    for k, linea in enumerate(lineas):
        d.text((MARGEN, 1400 + 110 * k), linea, font=f, fill=TEXTO)
    img.save(SALIDAS / "portada.png")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--guion", default=str(RAIZ / "guion.json"))
    p.add_argument("--voz")
    p.add_argument("--texto-voz", help="lo que dice la grabación, si se leyó un texto")
    p.add_argument("--autor", default="Luis Gabriel Guevara Vega")
    p.add_argument("--enlace", default=None, help="por defecto, el del guion")
    p.add_argument("--solo-voz", action="store_true", help="solo narra las escenas (para revisarlas antes del video)")
    p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    p.add_argument("--device", default="cpu")
    p.add_argument("--intentos", type=int, default=3)
    p.add_argument("--solo-video", action="store_true", help="reusa los audios de salidas/escenas")
    args = p.parse_args()

    guion = json.loads(Path(args.guion).read_text(encoding="utf-8"))
    pendientes = [e["cifra"] for e in guion["escenas"] if "¡¡" in e.get("cifra", "")]
    if pendientes:
        raise SystemExit(f"El guion tiene cifras sin verificar: {pendientes}. Revísalas antes de narrar.")

    inicio = time.time()
    if not args.solo_video:
        if not args.voz:
            p.error("--voz es obligatorio salvo con --solo-video")
        narrar(guion, args.voz, args.tts, args.device, args.intentos, args.texto_voz)
    t_voz = time.time() - inicio
    if args.solo_voz:
        print(f"Voz lista en {t_voz:.0f} s: revisen salidas/control_voz.json y escuchen salidas/escenas/.")
        return
    args.enlace = args.enlace or guion["enlace"]

    tiempos, total = unir_audio(len(guion["escenas"]))
    marcas = palabras_con_tiempo(guion, tiempos)
    srt([b for m in marcas for b in lineas_subtitulo(m)], SALIDAS / "reel.srt")
    (SALIDAS / "tiempos.json").write_text(json.dumps({"escenas": tiempos, "total": total}, indent=2), encoding="utf-8")

    t1 = time.time()
    portada = renderizar(guion, tiempos, total, marcas, args.autor, args.enlace, SALIDAS / "reel.mp4")
    hacer_portada(guion, args.autor, portada)
    mb = (SALIDAS / "reel.mp4").stat().st_size / 1e6
    print(f"\nreel.mp4: {total:.1f} s, {mb:.1f} MB · voz {t_voz:.0f} s · video {time.time() - t1:.0f} s")


if __name__ == "__main__":
    main()
