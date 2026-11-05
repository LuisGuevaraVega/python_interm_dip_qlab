"""Exporta las conversaciones de Claude Code de este proyecto a evidencias_ia/, con datos sensibles ocultos.

    uv run scripts/exportar_conversaciones.py <sesion.jsonl> [<otra.jsonl> ...] --salida evidencias_ia/conversaciones

Claude Code guarda cada sesión en ~/.claude/projects/<carpeta-del-proyecto>/<id>.jsonl. Por cada archivo escribe:
  <id>.md     la conversación legible: pedidos del usuario, respuestas del asistente y cada llamada a herramienta
              con sus argumentos y un resumen del resultado (las imágenes se reemplazan por una marca)
  <id>.jsonl  el registro original con los mismos datos ocultos
Oculta: correos electrónicos, claves y tokens con formato conocido (sk-, ghp_, github_pat_, xox, AKIA, Bearer) y
la carpeta del usuario de Windows. No incluye el razonamiento interno (bloques «thinking»).
"""
import argparse
import json
import re
from pathlib import Path

OCULTAR = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[correo oculto]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abp]-[A-Za-z0-9-]{10,}"
                r"|AKIA[0-9A-Z]{16})\b"), "[clave oculta]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"), "Bearer [token oculto]"),
    (re.compile(r"(?i)C:[\\/]+Users[\\/]+[^\\/\s\"']+"), "~"),
    (re.compile(r"/c/Users/[^/\s\"']+"), "~"),
]


def limpiar(texto):
    for patron, reemplazo in OCULTAR:
        texto = patron.sub(reemplazo, texto)
    return texto


def corto(valor, largo):
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False, indent=1)
    return texto if len(texto) <= largo else texto[:largo] + f"\n… [{len(texto) - largo:,} caracteres más]"


def texto_resultado(contenido):
    if isinstance(contenido, str):
        return contenido
    partes = []
    for c in contenido or []:
        if c.get("type") == "text":
            partes.append(c["text"])
        elif c.get("type") == "image":
            partes.append("[imagen]")
    return "\n".join(partes)


def exportar(ruta, salida):
    lineas_md = [f"# Conversación de Claude Code `{ruta.stem}`", "",
                 "Exportada con scripts/exportar_conversaciones.py. Correos, claves y la carpeta del usuario están "
                 "ocultos; el razonamiento interno del modelo no se incluye.", ""]
    jsonl_limpio = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        jsonl_limpio.append(limpiar(linea))
        e = json.loads(linea)
        tipo, hora = e.get("type"), (e.get("timestamp") or "")[:19].replace("T", " ")
        mensaje = e.get("message") or {}
        contenido = mensaje.get("content")
        if tipo == "user":
            if isinstance(contenido, str):
                if contenido.strip():
                    lineas_md += [f"## 👤 Usuario · {hora} UTC", "", contenido.strip(), ""]
                continue
            for c in contenido or []:
                if c.get("type") == "text" and c["text"].strip():
                    lineas_md += [f"## 👤 Usuario · {hora} UTC", "", c["text"].strip(), ""]
                elif c.get("type") == "tool_result":
                    etiqueta = "Resultado (error)" if c.get("is_error") else "Resultado"
                    lineas_md += [f"<details><summary>{etiqueta}</summary>", "", "```text",
                                  corto(texto_resultado(c.get("content")), 2500).replace("```", "ˋˋˋ"), "```",
                                  "</details>", ""]
        elif tipo == "assistant":
            for c in contenido or []:
                if c.get("type") == "text" and c["text"].strip():
                    lineas_md += [f"### 🤖 Claude · {hora} UTC", "", c["text"].strip(), ""]
                elif c.get("type") == "tool_use":
                    lineas_md += [f"**Herramienta `{c['name']}`**", "", "```json",
                                  corto(c.get("input"), 4000).replace("```", "ˋˋˋ"), "```", ""]
    (salida / f"{ruta.stem}.md").write_text(limpiar("\n".join(lineas_md)), encoding="utf-8")
    (salida / f"{ruta.stem}.jsonl").write_text("\n".join(jsonl_limpio) + "\n", encoding="utf-8")
    return salida / f"{ruta.stem}.md"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("sesiones", nargs="+", type=Path)
    a.add_argument("--salida", type=Path, default=Path("evidencias_ia/conversaciones"))
    args = a.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    for ruta in args.sesiones:
        md = exportar(ruta, args.salida)
        print(f"{ruta.name} -> {md} ({md.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
