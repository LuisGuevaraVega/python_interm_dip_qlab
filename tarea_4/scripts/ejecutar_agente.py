"""Ejecuta el agente (Claude Code en modo no interactivo) con el MCP del BCRP y las Skills de la ENAHO, y deja
evidencia de qué herramientas usó.

    uv run scripts/ejecutar_agente.py --nombre mapa --prompt "Haz un mapa de la pobreza monetaria por departamento con ENAHO 2024."
    uv run scripts/ejecutar_agente.py --nombre investigacion --prompt-archivo agente/pregunta_investigacion.md --sin-base

--sin-base aparta salidas/*.parquet antes de la ejecución (y los repone si el agente no los regeneró), para
demostrar que las Skills de gráficos y mapas activan primero limpiando-enaho.

Escribe en evidencias_ia/integracion/:
  <nombre>.jsonl         el registro completo (stream-json) de la sesión: mensajes, llamadas y resultados
  <nombre>_bitacora.md   la bitácora legible: cada herramienta MCP y Skill, en orden, con sus argumentos
y agrega una fila a evidencias_ia/integracion/ejecuciones.csv (herramientas, turnos, tiempo, costo).
"""
import argparse
import csv
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "evidencias_ia" / "integracion"
# Lo que el agente puede hacer sin pedir permiso: el MCP, las Skills, leer/escribir archivos y correr uv.
PERMITIDAS = ["mcp__bcrp", "Skill", "Read", "Write", "Edit", "Glob", "Grep", "Bash(uv run:*)", "Bash(ls:*)",
              "Bash(cat:*)", "Bash(head:*)", "Bash(test:*)"]


def resumir(valor, largo=300):
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    return texto if len(texto) <= largo else texto[:largo] + "…"


def bitacora(eventos, prompt, nombre, segundos):
    llamadas, resultados, final = [], {}, {}
    for e in eventos:
        if e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use":
                    llamadas.append(c)
        elif e.get("type") == "user":
            contenido = e.get("message", {}).get("content", [])
            for c in contenido if isinstance(contenido, list) else []:
                if c.get("type") == "tool_result":
                    r = c.get("content")
                    if isinstance(r, list):
                        r = " ".join(x.get("text", "") for x in r if isinstance(x, dict))
                    resultados[c["tool_use_id"]] = ("ERROR: " if c.get("is_error") else "") + resumir(r or "", 400)
        elif e.get("type") == "result":
            final = e
    mcp = [c for c in llamadas if c["name"].startswith("mcp__")]
    skills = [c for c in llamadas if c["name"] == "Skill"]
    lineas = [f"# Bitácora del agente: {nombre}", "",
              f"- Fecha: {datetime.now():%Y-%m-%d %H:%M} (hora local, UTC-5)",
              f"- Modelo: {final.get('modelUsage') and ', '.join(final['modelUsage']) or 'ver .jsonl'}",
              f"- Turnos: {final.get('num_turns')} · Tiempo: {segundos:.0f} s · "
              f"Costo informado por Claude Code: US$ {final.get('total_cost_usd', 0):.2f}",
              f"- Herramientas MCP distintas: {len({c['name'] for c in mcp})} "
              f"({', '.join(sorted({c['name'].removeprefix('mcp__bcrp__') for c in mcp})) or 'ninguna'})",
              f"- Skills distintas: {len({c['input'].get('skill') for c in skills})} "
              f"({', '.join(dict.fromkeys(c['input'].get('skill', '') for c in skills)) or 'ninguna'})",
              f"- Registro completo: [{nombre}.jsonl]({nombre}.jsonl)", "", "## Pedido", "", "```text", prompt.strip(),
              "```", "", "## Llamadas a herramientas, en orden", "", "| # | Herramienta | Argumentos | Resultado (resumen) |",
              "|---|---|---|---|"]
    for i, c in enumerate(llamadas, 1):
        celda = lambda t: t.replace("|", "\\|").replace("\n", " ")
        lineas.append(f"| {i} | `{c['name']}` | {celda(resumir(c['input'], 220))} | "
                      f"{celda(resultados.get(c['id'], ''))} |")
    lineas += ["", "## Respuesta final del agente", "", final.get("result", "(sin respuesta)"), ""]
    return "\n".join(lineas), mcp, skills, final


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--nombre", required=True)
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-archivo", type=Path)
    a.add_argument("--modelo", default="sonnet")
    a.add_argument("--sin-base", action="store_true", help="apartar salidas/*.parquet antes de ejecutar")
    a.add_argument("--limpio", action="store_true",
                   help="apartar TODAS las salidas previas (salidas/, figuras/, mapas/, informes/) para que el agente "
                        "tenga que producirlas")
    a.add_argument("--max-turnos", type=int, default=60)
    args = a.parse_args()
    prompt = args.prompt or (RAIZ / args.prompt_archivo).read_text(encoding="utf-8")
    SALIDA.mkdir(parents=True, exist_ok=True)

    apartados = []
    if args.sin_base or args.limpio:
        reserva = Path(tempfile.mkdtemp(prefix="salidas_apartadas_"))   # fuera del proyecto: el agente no las ve
        patrones = (["salidas/*", "figuras/*", "mapas/*", "informes/*"] if args.limpio else ["salidas/*.parquet"])
        for patron in patrones:
            for p in RAIZ.glob(patron):
                if p.is_file():
                    destino = reserva / p.relative_to(RAIZ).as_posix().replace("/", "__")
                    apartados.append((shutil.move(p, destino), p))
        print(f"Apartados fuera del proyecto: {len(apartados)} archivos ({reserva})")

    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", args.modelo,
           "--mcp-config", str(RAIZ / ".mcp.json"), "--strict-mcp-config", "--max-turns", str(args.max_turnos),
           "--allowedTools", *PERMITIDAS]
    print(f"Ejecutando claude -p ({args.modelo}) en {RAIZ} ...")
    t = time.time()
    proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=3600)
    segundos = time.time() - t
    for origen, destino in apartados:          # si el agente no regeneró la base, se repone la original
        if not destino.exists():
            shutil.move(origen, destino)
        else:
            Path(origen).unlink()

    (SALIDA / f"{args.nombre}.jsonl").write_text(proc.stdout, encoding="utf-8")
    eventos = [json.loads(l) for l in proc.stdout.splitlines() if l.strip().startswith("{")]
    texto, mcp, skills, final = bitacora(eventos, prompt, args.nombre, segundos)
    (SALIDA / f"{args.nombre}_bitacora.md").write_text(texto, encoding="utf-8")
    fila = {"fecha": f"{datetime.now():%Y-%m-%d %H:%M}", "nombre": args.nombre, "modelo": args.modelo,
            "segundos": round(segundos), "turnos": final.get("num_turns"),
            "mcp_distintas": len({c["name"] for c in mcp}), "skills_distintas": len({c["input"].get("skill") for c in skills}),
            "herramientas_mcp": " ".join(sorted({c["name"].removeprefix("mcp__bcrp__") for c in mcp})),
            "skills": " ".join(dict.fromkeys(c["input"].get("skill", "") for c in skills)),
            "error": final.get("is_error", proc.returncode != 0)}
    registro = SALIDA / "ejecuciones.csv"
    nuevo = not registro.exists()
    with open(registro, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fila))
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    if proc.returncode != 0 and not eventos:
        print("STDERR:", proc.stderr[-2000:])
    print(texto[:3000])


if __name__ == "__main__":
    main()
