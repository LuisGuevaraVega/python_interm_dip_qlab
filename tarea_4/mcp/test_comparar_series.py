"""Las 2 pruebas propias: la herramienta comparar_series (no forman parte de las 8 originales de la sesión 04).

    uv run pytest -q        # junto con test_server.py: 10 passed

La verdad de la primera prueba no sale de comparar_series sino de los datos crudos que devuelve la herramienta serie,
y la cuenta se hace aparte, aquí mismo.
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def test_comparar_series_reproduce_la_variacion_acumulada():
    r = llamar("comparar_series", codigos="PN38705PM,PN39445PM", desde="2019-12", hasta="2024-12")
    assert r["periodo_comun"] == {"desde": "2019-12", "hasta": "2024-12", "observaciones": 61}
    total, alimentos = r["series"]
    for x in (total, alimentos):   # la cuenta independiente, con los datos crudos de la API
        d = llamar("serie", codigo=x["codigo"], desde="2019-12", hasta="2024-12")["datos"]
        assert x["variacion_acumulada_pct"] == pytest.approx(100 * (d[-1]["valor"] / d[0]["valor"] - 1), abs=1e-3)
    assert total["brecha_vs_referencia_pp"] == 0
    assert alimentos["brecha_vs_referencia_pp"] == pytest.approx(
        alimentos["variacion_acumulada_pct"] - total["variacion_acumulada_pct"], abs=1e-3)
    assert alimentos["variacion_acumulada_pct"] > total["variacion_acumulada_pct"]   # los alimentos subieron más
    assert -1 <= r["correlacion_variaciones"][0]["pearson"] <= 1
    assert all(f.startswith("https://estadisticas.bcrp.gob.pe") for f in r["fuentes"])


def test_comparar_series_rechaza_tasas_y_frecuencias_distintas():
    with pytest.raises(ToolError, match="PN01273PM.*tasa"):         # var% 12 meses: no se acumula
        llamar("comparar_series", codigos="PN38705PM,PN01273PM", desde="2020-01", hasta="2020-12")
    with pytest.raises(ToolError, match="distinta frecuencia"):      # mensual contra anual
        llamar("comparar_series", codigos="PN38705PM,PM04923AA", desde="2020", hasta="2021")
    with pytest.raises(ToolError, match="XX999"):                    # código inexistente
        llamar("comparar_series", codigos="PN38705PM,XX999", desde="2020-01", hasta="2020-12")
