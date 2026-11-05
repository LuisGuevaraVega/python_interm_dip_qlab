"""¿Mejoran el MCP y las Skills las respuestas de Claude Code? Las mismas 10 preguntas en dos modos.

    uv run evaluacion/evaluar.py                     # modos A y B con Sonnet; escribe evaluacion/resultados.csv
    uv run evaluacion/evaluar.py --paralelo 2        # si el BCRP limita los pedidos

Modo A (sin MCP ni Skills): claude -p sin ninguna herramienta (--tools ""), sin servidores MCP
  (--strict-mcp-config sin --mcp-config), sin skills ni comandos (--disable-slash-commands) y desde una carpeta
  temporal vacía fuera del proyecto: no puede leer ningún archivo con respuestas. Solo su conocimiento previo.
Modo B (con MCP y Skills): claude -p en la carpeta del proyecto con el servidor bcrp de .mcp.json y las skills de
  .claude/skills, más Read, Glob, Grep y `uv run` para que las skills ejecuten sus scripts. Durante la evaluación se
  apartan evaluacion/ (preguntas y verdades), informes/ y evidencias_ia/: solo puede usar herramientas y salidas
  de las skills.

En ambos: el mismo modelo, la misma instrucción, el mismo esquema JSON y una sesión nueva por pregunta
(--no-session-persistence). Las verdades y tolerancias vienen de preguntas.csv, fijadas antes de correr (ver
verdades.py). Se registran las herramientas que cada respuesta usó realmente (del registro stream-json).
"""
import argparse
import json
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
REGISTROS = None
RAIZ = AQUI.parent
ESQUEMA = {"type": "object", "required": ["valor", "fuente"],
           "properties": {"valor": {"type": ["number", "null"]}, "valor_2": {"type": ["number", "null"]},
                          "categoria": {"type": ["string", "null"]}, "unidad": {"type": "string"},
                          "fuente": {"type": "string"}, "interpretacion": {"type": "string"}}}
INSTRUCCION = ("Responde con un solo número en «valor», en la unidad que pide la pregunta. Si la pregunta pide un "
               "segundo número, va en «valor_2», y si pide elegir un grupo, va en «categoria». Si no puedes saberlo "
               "con certeza, pon null: no estimes. En «fuente» di de dónde sale cada cifra y en «interpretacion», "
               "en una o dos frases, qué significa el resultado. Si tienes herramientas o skills disponibles, úsalas "
               "para calcular la cifra a partir de los datos; no copies cifras de documentación ni de archivos de "
               "referencia.\n\n")
PERMITIDAS_B = ["mcp__bcrp", "Skill", "ToolSearch", "Read", "Glob", "Grep", "Bash(uv run:*)", "Bash(uv:*)",
                "Bash(.venv/Scripts/python.exe:*)", "Bash(python:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)",
                "Bash(find:*)"]
HERRAMIENTAS_B = "Bash,Read,Glob,Grep,Skill,ToolSearch"   # sin web, sin PowerShell, sin escribir archivos a mano
# Lo que el modo B no puede ver: las verdades, el informe, las evidencias y las tablas ya calculadas por las skills.
# Solo quedan los datos crudos (datos/) y las bases procesadas (salidas/*.parquet): para responder tiene que usar el
# MCP o seguir las skills (graficar, mapear o calcular con numpy.average sobre la base).
APARTAR_B = ["evaluacion/preguntas.csv", "evaluacion/verdades.txt", "evaluacion/resultados.csv",
             "evaluacion/resultados_corrida1.csv", "evaluacion/resultados_corrida2.csv",
             "evaluacion/resultados_corrida3.csv", "evaluacion/verdades.py", "evaluacion/comparacion.md",
             "README.md", "informes", "evidencias_ia", "salidas", "figuras", "mapas"]
# Antes de cada pregunta del modo B se borran estas carpetas: cada pregunta parte solo de los datos crudos (datos/),
# el MCP y las skills, sin bases ni tablas que haya dejado la pregunta anterior.
GENERADAS = ["salidas", "figuras", "mapas"]
MODOS = {
    "A_sin_mcp_skills": {"flags": ["--tools", "", "--strict-mcp-config", "--disable-slash-commands"],
                         "herramientas_habilitadas": "ninguna (sin herramientas, sin MCP, sin skills; carpeta vacía)"},
    "B_con_mcp_skills": {"flags": ["--tools", HERRAMIENTAS_B, "--mcp-config", str(RAIZ / ".mcp.json"),
                                   "--strict-mcp-config", "--allowedTools", *PERMITIDAS_B,
                                   "--disallowedTools", "Bash(git:*)"],
                         "herramientas_habilitadas": "MCP bcrp + skills del proyecto + Read/Glob/Grep + Bash (uv run); "
                                                     "sin web, sin PowerShell, sin git"},
}


def preguntar(id_, pregunta, modo, modelo, carpeta_vacia):
    cmd = ["claude", "-p", INSTRUCCION + pregunta, "--output-format", "stream-json", "--verbose",
           "--json-schema", json.dumps(ESQUEMA), "--no-session-persistence", "--model", modelo,
           "--max-turns", "30", *MODOS[modo]["flags"]]
    t = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=900,
                              cwd=carpeta_vacia if modo.startswith("A") else RAIZ)
        salida, error = proc.stdout, proc.stderr[-300:] if proc.returncode else ""
    except subprocess.TimeoutExpired:
        salida, error = "", "timeout (900 s)"
    eventos = [json.loads(l) for l in salida.splitlines() if l.strip().startswith("{")]
    (Path(REGISTROS) / f"{modo}__{id_}.jsonl").write_text(salida, encoding="utf-8")
    usadas = [c["name"] if c["name"] != "Skill" else f"Skill:{c['input'].get('skill')}"
              for e in eventos if e.get("type") == "assistant"
              for c in e["message"].get("content", []) if c.get("type") == "tool_use"]
    final = next((e for e in reversed(eventos) if e.get("type") == "result"), {})
    r = final.get("structured_output") or {}
    if not final:
        error = error or "sin respuesta"
    elif final.get("is_error"):
        error = error or str(final.get("result", ""))[:300]
    return {"valor": r.get("valor"), "valor_2": r.get("valor_2"), "categoria": r.get("categoria"),
            "fuente": r.get("fuente", final.get("result", ""))[:500], "interpretacion": r.get("interpretacion", ""),
            "herramientas_usadas": " ".join(dict.fromkeys(u.removeprefix("mcp__bcrp__") for u in usadas)),
            "segundos": round(time.time() - t, 1), "turnos": final.get("num_turns"),
            "costo_usd": round(final.get("total_cost_usd") or 0, 4), "error": error}


def dentro(valor, verdad, tol):
    return valor is not None and abs(float(valor) - float(verdad)) <= float(tol)


def calificar(q, r):
    """bcrp/enaho: acierta, se equivoca o no sabe. mixta: acierta solo si las dos cifras y la categoría son correctas;
    si acierta en alguna parte es «parcial»."""
    if r["valor"] is None and r["valor_2"] is None:
        return "no sabe", ""
    if q.tipo != "mixta":
        return ("acierta" if dentro(r["valor"], q.verdad, q.tolerancia) else "se equivoca"), ""
    partes = {"valor": dentro(r["valor"], q.verdad, q.tolerancia),
              "valor_2": dentro(r["valor_2"], q.verdad_2, q.tolerancia_2),
              "categoria": str(r["categoria"] or "").strip().lower().startswith(q.categoria_esperada.split()[0])}
    detalle = " ".join(f"{k}={'ok' if v else 'no'}" for k, v in partes.items())
    return ("acierta" if all(partes.values()) else "parcial" if any(partes.values()) else "se equivoca"), detalle


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modos", nargs="+", default=list(MODOS), choices=list(MODOS))
    p.add_argument("--modelo", default="sonnet")
    p.add_argument("--paralelo", type=int, default=3)
    p.add_argument("--corrida", default="corrida4", help="nombre de la carpeta de registros en evidencias_ia/evaluacion/")
    a = p.parse_args()

    preguntas = pd.read_csv(AQUI / "preguntas.csv", dtype={"categoria_esperada": str}).fillna({"categoria_esperada": ""})
    casos = [(q, m) for m in sorted(a.modos) for q in preguntas.itertuples()]   # primero A, luego B
    global REGISTROS
    REGISTROS = tempfile.mkdtemp(prefix="registros_eval_")
    vacia = tempfile.mkdtemp(prefix="modo_A_vacio_")
    apartado = Path(tempfile.mkdtemp(prefix="apartado_eval_"))
    movidos = []
    if any(m.startswith("B") for m in a.modos):
        for rel in APARTAR_B:
            origen = RAIZ / rel
            if origen.exists():
                movidos.append((shutil.move(origen, apartado / rel.replace("/", "__")), origen))
    print(f"{len(casos)} llamadas a claude -p con {a.modelo}; apartados para el modo B: {[str(o.relative_to(RAIZ)) for _, o in movidos]}")
    try:
        casos_a = [c for c in casos if c[1].startswith("A")]
        with ThreadPoolExecutor(a.paralelo) as ex:      # el modo A no toca archivos: va en paralelo
            r_a = list(ex.map(lambda c: preguntar(c[0].id, c[0].pregunta, c[1], a.modelo, vacia), casos_a))
        r_b = []
        for q, m in [c for c in casos if c[1].startswith("B")]:   # el modo B, una pregunta a la vez y desde cero
            for rel in GENERADAS:
                if (RAIZ / rel).exists():
                    shutil.rmtree(RAIZ / rel)
            r_b.append(preguntar(q.id, q.pregunta, m, a.modelo, vacia))
            print(f"  B {q.id}: {r_b[-1]['valor']} · {r_b[-1]['herramientas_usadas']}", flush=True)
        respuestas = r_a + r_b
    finally:
        for destino_temp, origen in movidos:      # lo que el agente haya regenerado durante la prueba se descarta
            if origen.is_dir():
                shutil.rmtree(origen)
            elif origen.exists():
                origen.unlink()
            shutil.move(destino_temp, origen)
        destino_reg = RAIZ / "evidencias_ia" / "evaluacion" / a.corrida
        destino_reg.mkdir(parents=True, exist_ok=True)
        for r in Path(REGISTROS).glob("*.jsonl"):
            shutil.move(r, destino_reg / r.name)

    filas = []
    for (q, m), r in zip(casos, respuestas):
        resultado, detalle = calificar(q, r)
        filas.append({"id": q.id, "tipo": q.tipo, "modo": m, "pregunta": q.pregunta,
                      "respuesta_esperada": q.verdad, "tolerancia": q.tolerancia,
                      "respuesta_esperada_2": q.verdad_2, "categoria_esperada": q.categoria_esperada,
                      "respuesta_generada": r["valor"], "respuesta_generada_2": r["valor_2"],
                      "categoria_generada": r["categoria"], "resultado": resultado, "detalle_mixta": detalle,
                      "fuente_utilizada": r["fuente"], "herramientas_usadas": r["herramientas_usadas"],
                      "herramientas_habilitadas": MODOS[m]["herramientas_habilitadas"],
                      "segundos": r["segundos"], "turnos": r["turnos"], "costo_usd": r["costo_usd"],
                      "error": r["error"], "interpretacion": r["interpretacion"], "modelo": a.modelo})
    res = pd.DataFrame(filas)
    res.to_csv(AQUI / "resultados.csv", index=False, encoding="utf-8")
    print("\n" + res.pivot(index="id", columns="modo", values="respuesta_generada").to_string())
    tabla = res.groupby("modo").resultado.value_counts().unstack(fill_value=0)
    tabla["segundos_promedio"] = res.groupby("modo").segundos.mean().round(1)
    print("\n" + tabla.to_string())


if __name__ == "__main__":
    main()
