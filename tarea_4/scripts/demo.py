"""Demo guiada del proyecto: las cuatro piezas en orden, con una pausa entre pasos.

    uv run scripts/demo.py                  # demo completa (el último paso llama a Claude Code: ~1 min, ~US$ 0.15)
    uv run scripts/demo.py --sin-agente     # sin el paso 5 (no usa Claude)
    uv run scripts/demo.py --sin-pausas     # de corrido, sin esperar Enter
    uv run scripts/demo.py --sin-abrir      # sin abrir el gráfico y el mapa en el visor de imágenes

1. Pruebas del servidor MCP (pytest).
2. El servidor MCP del BCRP por dentro: sus herramientas, recursos y prompts, y dos consultas reales.
3. La skill limpiando-enaho: microdatos del INEI -> base validada.
4. Las skills graficando-enaho y mapeando-enaho: un gráfico y un mapa.
5. El agente: Claude Code responde una pregunta que necesita las dos fuentes, con el MCP y las skills.
"""
import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
PREGUNTA = ("¿Qué hogares peruanos quedaron más expuestos a la inflación de alimentos de 2020-2024? Usa el BCRP para "
            "saber cuánto más subieron los alimentos que el IPC total en Lima entre dic. 2019 y dic. 2024, y la ENAHO "
            "2024 para comparar el peso de los alimentos en el gasto de los hogares pobres extremos, no pobres, rurales "
            "y urbanos. Usa el servidor MCP bcrp para los precios y carga la skill graficando-enaho con la herramienta "
            "Skill para el peso de los alimentos. Cita el origen de cada cifra y responde en no más de 8 líneas.")

pausas = True


def titulo(n, texto):
    print(f"\n{'═' * 78}\n  PASO {n} · {texto}\n{'═' * 78}")


def pausa():
    if pausas:
        input("\n  [Enter para seguir] ")


def correr(cmd, ultimas=None, mostrar=True):
    print(f"\n  $ {' '.join(cmd)}\n")
    salida = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout
    if mostrar:
        lineas = salida.strip().splitlines()
        for l in (lineas[-ultimas:] if ultimas else lineas):
            print("   ", l)
    return salida


async def mcp_por_dentro():
    from fastmcp import Client
    from server import mcp
    async with Client(mcp) as c:
        herramientas = await c.list_tools()
        recursos = await c.list_resources() + await c.list_resource_templates()
        prompts = await c.list_prompts()
        print(f"  Herramientas ({len(herramientas)}): {', '.join(t.name for t in herramientas)}")
        print(f"  Recursos ({len(recursos)}): {', '.join(getattr(r, 'uri_template', None) or str(r.uri) for r in recursos)}")
        print(f"  Prompts ({len(prompts)}): {', '.join(p.name for p in prompts)}")

        print('\n  > comparar_series("PN38705PM,PN39445PM,PN38706PM", "2019-12", "2024-12")   [herramienta propia]')
        r = (await c.call_tool("comparar_series", {"codigos": "PN38705PM,PN39445PM,PN38706PM",
                                                   "desde": "2019-12", "hasta": "2024-12"})).data
        for s in r["series"]:
            nombre = s["nombre"].split(" - ")[-1]
            print(f"    {s['codigo']}  {nombre[:34]:<34} {s['variacion_acumulada_pct']:>6.2f} %   "
                  f"brecha vs total {s['brecha_vs_referencia_pp']:+.2f} pp")

        print('\n  > resumen("PN09822PM", "2020-01", "2024-12")   [inflación de alimentos a 12 meses]')
        r = (await c.call_tool("resumen", {"codigo": "PN09822PM", "desde": "2020-01", "hasta": "2024-12"})).data
        print(f"    máximo {r['maximo']['valor']:.2f} % en {r['maximo']['periodo']} · último {r['ultimo']['valor']:.2f} % "
              f"en {r['ultimo']['periodo']}\n    fuente: {r['fuente']}")


def main():
    global pausas
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--sin-agente", action="store_true")
    a.add_argument("--sin-pausas", action="store_true")
    a.add_argument("--sin-abrir", action="store_true", help="no abrir el gráfico y el mapa en el visor")
    args = a.parse_args()
    pausas = not args.sin_pausas
    print("\n  DEMO · Agente de investigación socioeconómica: MCP del BCRP + Skills de la ENAHO 2024")
    print("  Pregunta del proyecto: ¿cuánto subieron los alimentos frente al resto (2020-2024) y quiénes")
    print("  estaban más expuestos por el peso de la comida en su gasto (ENAHO 2024)?")
    pausa()

    titulo(1, "Las pruebas del servidor MCP: 8 originales de la sesión 04 + 2 propias")
    correr(["uv", "run", "pytest", "-q"], ultimas=2)
    pausa()

    titulo(2, "El servidor MCP del BCRP por dentro (datos reales de la API del BCRP)")
    asyncio.run(mcp_por_dentro())
    pausa()

    titulo(3, "Skill limpiando-enaho: microdatos del INEI -> base de personas validada")
    salida = correr(["uv", "run", ".claude/skills/limpiando-enaho/scripts/limpiar.py"], mostrar=False)
    for l in salida.splitlines():
        if any(k in l for k in ("Residentes habituales", "Unión m:1", "25 códigos", "Pobreza monetaria nacional (método",
                                "Pobreza urbana (método", "Pobreza rural (método", "promedio simple", "Resultado:")):
            print("   ", l[:140])
    pausa()

    titulo(4, "Skills graficando-enaho y mapeando-enaho")
    correr(["uv", "run", ".claude/skills/graficando-enaho/scripts/graficar.py", "--tipo", "alimentos"])
    correr(["uv", "run", ".claude/skills/mapeando-enaho/scripts/mapear.py", "--indicador", "pobreza"], ultimas=6)
    for archivo in ("figuras/enaho_alimentos.png", "mapas/mapa_pobreza_departamento.png"):
        print(f"  Figura: {archivo}")
        if sys.platform == "win32" and not args.sin_abrir:
            os.startfile(RAIZ / archivo)
    pausa()

    if args.sin_agente:
        print("\n  (Paso 5 omitido: --sin-agente)")
        return
    titulo(5, "El agente: Claude Code usa el MCP y las skills para una pregunta con las dos fuentes")
    print(f"  Pregunta: {PREGUNTA}\n  Pensando (≈1 min)...")
    t = time.time()
    salida = subprocess.run(
        [sys.executable, "scripts/ejecutar_agente.py", "--nombre", "demo", "--prompt", PREGUNTA, "--max-turnos", "30"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout
    bitacora = (RAIZ / "evidencias_ia" / "integracion" / "demo_bitacora.md").read_text(encoding="utf-8")
    for l in bitacora.splitlines()[3:7]:
        print("  ", l)
    print("\n   Herramientas, en orden:")
    for l in bitacora.splitlines():
        if l.startswith("| ") and "`" in l and not l.startswith("| #"):
            celdas = [c.strip() for c in l.split("|")]
            print(f"    {celdas[1]:>2}. {celdas[2]}")
    print("\n   Respuesta del agente:\n")
    for l in bitacora.split("## Respuesta final del agente", 1)[-1].strip().splitlines():
        print("   ", l)
    print(f"\n  ({time.time() - t:.0f} s · bitácora completa: evidencias_ia/integracion/demo_bitacora.md)")


if __name__ == "__main__":
    main()
