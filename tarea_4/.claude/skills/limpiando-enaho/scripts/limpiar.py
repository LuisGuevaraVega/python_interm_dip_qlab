"""Limpia la ENAHO del INEI (módulos 34 sumaria y 02 miembros) y arma una base de personas validada.

    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py                # ENAHO 2024 (código INEI 966)
    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --descargar    # baja los zip del INEI si faltan

Pipeline (siempre en este orden, sesión 16):
  1. Leer los .dta dentro de los zip con convert_categoricals=False y las llaves como texto (sin perder ceros).
  2. Normalizar los nombres de columna a minúscula (el año llega como «aÑo»).
  3. Filtrar residentes habituales: ((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1)).
  4. Unir personas y hogares por conglome, vivienda y hogar con merge(..., validate="m:1").
  5. Construir departamento = ubigeo[:2], urbano = estrato <= 5, pobre = pobreza <= 2 y la participación del
     gasto en alimentos (grupo 1 del gasto) en el gasto total del hogar.
  6. Validar (llaves, filas, factores, 25 departamentos, pobreza contra el INEI) y escribir salidas/validacion.txt.
  7. Guardar salidas/personas_2024.parquet y salidas/indicadores.csv (todo ponderado con facpob07).

Si una validación esencial falla, el script termina con código 1 y NO escribe la base: no se corrigen cifras a mano.
"""
import argparse
import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[4]          # .../tarea_4
CODIGO_INEI = {2024: 966}
URL_INEI = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{codigo}-Modulo{modulo}.zip"
LLAVES = ["conglome", "vivienda", "hogar"]

# Valores de referencia del INEI y de la sesión 16 (ENAHO 2024). Solo se usan para VALIDAR, nunca para corregir.
REFERENCIA = {"pobreza": 27.6, "residentes": 108_664, "departamentos": 25, "urbano": 24.8, "rural": 39.3,
              "extrema": 5.5, "hogares": 33_691, "filas_modulo02": 117_721}
TOLERANCIA = {"pobreza": 0.1, "urbano": 0.15, "rural": 0.15, "extrema": 0.15}

DEPARTAMENTOS = {"01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
                 "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
                 "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
                 "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
                 "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}
DOMINIOS = {1: "Costa norte", 2: "Costa centro", 3: "Costa sur", 4: "Sierra norte", 5: "Sierra centro",
            6: "Sierra sur", 7: "Selva", 8: "Lima Metropolitana"}
POBREZA = {1: "Pobre extremo", 2: "Pobre no extremo", 3: "No pobre"}
EDADES = [(0, 14, "0-14"), (15, 29, "15-29"), (30, 44, "30-44"), (45, 64, "45-64"), (65, 200, "65 y más")]
# Grupo 1 del gasto de la sumaria: alimentos dentro y fuera del hogar, comprados, autoconsumo, especie y donados
GASTO_ALIMENTOS = ["gru11hd", "gru12hd1", "gru12hd2", "gru13hd1", "gru13hd2", "gru13hd3", "gru13hd4",
                   "gru14hd", "gru14hd1", "gru14hd2", "gru14hd3", "gru14hd4", "gru14hd5", "gru14hd6"]


class ValidacionFallida(Exception):
    pass


def descargar(codigo, modulo, destino):
    url = URL_INEI.format(codigo=codigo, modulo=modulo)
    print(f"Descargando {url} ...")
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_bytes():
                f.write(parte)


def leer_dta(zip_path, patron, columnas):
    """Lee un .dta dentro del zip del INEI, sin convertir categorías y con las llaves como texto."""
    with zipfile.ZipFile(zip_path) as z:
        nombres = [n for n in z.namelist() if n.lower().endswith("/" + patron)]
        if len(nombres) != 1:
            raise ValidacionFallida(f"Se esperaba un archivo «{patron}» (y solo uno) en {zip_path.name} y hay: {nombres}")
        df = pd.read_stata(io.BytesIO(z.read(nombres[0])), convert_categoricals=False)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={c: "anio" for c in df.columns if c.startswith("a") and c.endswith("o") and len(c) == 3})
    faltan = set(columnas) - set(df.columns)
    if faltan:
        raise ValidacionFallida(f"Faltan columnas en {nombres[0]}: {sorted(faltan)}")
    df = df[columnas].copy()
    for c in LLAVES + ["codperso", "ubigeo"]:
        if c in df:
            df[c] = df[c].astype(str).str.strip()
    return df, nombres[0]


def pct(serie_bool, peso):
    peso = np.asarray(peso, dtype=float)
    return 100 * float(np.sum(np.asarray(serie_bool, dtype=float) * peso) / np.sum(peso))


def media(valor, peso):
    peso = np.asarray(peso, dtype=float)
    return float(np.sum(np.asarray(valor, dtype=float) * peso) / np.sum(peso))


def derivar(df):
    """Las variables de análisis, iguales para la base de hogares y la de personas."""
    df["ccdd"] = df.ubigeo.str[:2]
    df["departamento"] = df.ccdd.map(DEPARTAMENTOS)
    df["urbano"] = df.estrato <= 5
    df["area"] = np.where(df.urbano, "Urbana", "Rural")
    df["pobre"] = df.pobreza <= 2
    df["pobre_extremo"] = df.pobreza == 1
    df["pobreza_nombre"] = df.pobreza.map(POBREZA)
    df["dominio_nombre"] = df.dominio.map(DOMINIOS)
    alimentos = df[GASTO_ALIMENTOS].fillna(0).sum(axis=1)
    df["gasto_alimentos_pct"] = np.where(df.gashog2d > 0, 100 * alimentos / df.gashog2d, np.nan)
    return df


# Desagregaciones que existen en el hogar (método INEI) y las que solo existen en la persona (facpob07)
CORTES_HOGAR = {"Nacional": None, "Área": "area", "Dominio": "dominio_nombre",
                "Condición de pobreza": "pobreza_nombre", "Departamento": "departamento"}
CORTES_PERSONA = {"Sexo": "sexo", "Grupo de edad": "grupo_edad"}


def indicadores(p, h):
    """Tabla de indicadores ponderados.

    - pobreza_inei_pct: hogares de la sumaria expandidos con factor07 × mieperho (el cálculo oficial del INEI).
      Se usa para lo territorial (nacional, área, dominio, departamento).
    - pobreza_personas_pct: residentes habituales expandidos con facpob07. Es la única opción para
      características individuales (sexo, edad), cuya unidad es la persona.
    - gasto_alimentos_pct: participación del gasto en alimentos (grupo 1) en el gasto total del hogar, promedio
      ponderado por personas (facpob07).
    """
    filas = []
    for corte, col in {**CORTES_HOGAR, **CORTES_PERSONA}.items():
        grupos_p = p.groupby(col, sort=False) if col else [("Perú", p)]
        grupos_h = ({"Perú": h} if not col else dict(list(h.groupby(col, sort=False))) if corte in CORTES_HOGAR else {})
        for nombre, d in grupos_p:
            fila = {"desagregacion": corte, "grupo": nombre,
                    "codigo": d.ccdd.iloc[0] if corte == "Departamento" else "",
                    "pobreza_inei_pct": np.nan, "pobreza_extrema_inei_pct": np.nan,
                    "pobreza_personas_pct": round(pct(d.pobre, d.facpob07), 4),
                    "pobreza_extrema_personas_pct": round(pct(d.pobre_extremo, d.facpob07), 4),
                    "gasto_alimentos_pct": round(media(d.gasto_alimentos_pct, d.facpob07), 4),
                    "poblacion_expandida": round(float(d.facpob07.sum())), "personas_muestra": len(d),
                    "hogares_muestra": np.nan}
            if corte in CORTES_HOGAR:
                g = grupos_h[nombre]
                peso = g.factor07 * g.mieperho
                fila.update(pobreza_inei_pct=round(pct(g.pobre, peso), 4),
                            pobreza_extrema_inei_pct=round(pct(g.pobre_extremo, peso), 4), hogares_muestra=len(g))
            filas.append(fila)
    t = pd.DataFrame(filas)
    orden = {c: i for i, c in enumerate({**CORTES_HOGAR, **CORTES_PERSONA})}
    t["_o"] = t.desagregacion.map(orden)
    return t.sort_values(["_o", "codigo", "grupo"]).drop(columns="_o")


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--anio", type=int, default=2024)
    a.add_argument("--datos", type=Path, default=RAIZ / "datos")
    a.add_argument("--salidas", type=Path, default=RAIZ / "salidas")
    a.add_argument("--descargar", action="store_true", help="bajar del INEI los zip que falten")
    args = a.parse_args()
    if args.anio not in CODIGO_INEI:
        sys.exit(f"ERROR: solo está configurada la ENAHO {list(CODIGO_INEI)}; el año {args.anio} no tiene código INEI.")
    codigo = CODIGO_INEI[args.anio]
    args.datos.mkdir(exist_ok=True)
    args.salidas.mkdir(exist_ok=True)

    zips = {m: args.datos / f"{codigo}-Modulo{m}.zip" for m in ("34", "02")}
    for m, z in zips.items():
        if not z.exists():
            if not args.descargar:
                sys.exit(f"ERROR: falta {z}. Bájenlo de {URL_INEI.format(codigo=codigo, modulo=m)} "
                         "o corran el script con --descargar.")
            descargar(codigo, m, z)

    lineas, fallas = [], []

    def chequeo(nombre, ok, detalle, esencial=True):
        estado = "APROBADA" if ok else ("FALLIDA" if esencial else "ADVERTENCIA")
        lineas.append(f"[{estado:<11}] {nombre}: {detalle}")
        if not ok and esencial:
            fallas.append(nombre)

    # 1-2. Leer y normalizar
    col_hog = LLAVES + ["anio", "ubigeo", "dominio", "estrato", "mieperho", "factor07", "pobreza", "linea",
                        "linpe", "gashog2d"] + GASTO_ALIMENTOS
    col_per = LLAVES + ["codperso", "ubigeo", "p203", "p204", "p205", "p206", "p207", "p208a", "facpob07"]
    hog, f34 = leer_dta(zips["34"], f"sumaria-{args.anio}.dta", col_hog)
    per, f02 = leer_dta(zips["02"], f"enaho01-{args.anio}-200.dta", col_per)
    chequeo("Hogares en la sumaria", len(hog) == REFERENCIA["hogares"],
            f"{len(hog):,} filas (referencia {REFERENCIA['hogares']:,})", esencial=False)
    chequeo("Filas del módulo 02", len(per) == REFERENCIA["filas_modulo02"],
            f"{len(per):,} filas (referencia {REFERENCIA['filas_modulo02']:,})", esencial=False)
    chequeo("Llaves de la sumaria únicas", not hog.duplicated(LLAVES).any(),
            f"{hog.duplicated(LLAVES).sum()} duplicados de (conglome, vivienda, hogar)")
    chequeo("Llaves de personas únicas", not per.duplicated(LLAVES + ["codperso"]).any(),
            f"{per.duplicated(LLAVES + ['codperso']).sum()} duplicados de (conglome, vivienda, hogar, codperso)")
    chequeo("Llaves conservan ceros iniciales", hog.conglome.str.len().eq(6).all() and hog.ubigeo.str.len().eq(6).all(),
            f"conglome de 6 dígitos: {hog.conglome.str.len().eq(6).mean():.0%}; ubigeo de 6: {hog.ubigeo.str.len().eq(6).mean():.0%}")

    # 3. Residentes habituales
    residente = ((per.p204 == 1) & (per.p205 == 2)) | ((per.p204 == 2) & (per.p206 == 1))
    per = per[residente].copy()
    chequeo("Residentes habituales", len(per) == REFERENCIA["residentes"],
            f"{len(per):,} (referencia {REFERENCIA['residentes']:,})")

    # 4. Unión m:1 personas -> hogares
    antes = len(per)
    p = per.drop(columns="ubigeo").merge(hog, on=LLAVES, how="left", validate="m:1", indicator=True)
    sin_hogar = int((p._merge != "both").sum())
    chequeo("Unión m:1 sin duplicar filas", len(p) == antes, f"{antes:,} personas antes y {len(p):,} después")
    chequeo("Toda persona tiene hogar en la sumaria", sin_hogar == 0, f"{sin_hogar} personas sin hogar")
    p = p.drop(columns="_merge")

    # 5. Indicadores
    hog = derivar(hog)
    p = derivar(p)
    p["sexo"] = p.p207.map({1: "Hombre", 2: "Mujer"})
    p["edad"] = p.p208a
    p["grupo_edad"] = pd.cut(p.edad, [e[0] - 1 for e in EDADES] + [EDADES[-1][1]],
                             labels=[e[2] for e in EDADES]).astype(str)

    # 6. Validaciones de ponderación y territorio
    for col in ("facpob07", "factor07"):
        malos = int(p[col].isna().sum() + (p[col] <= 0).sum())
        chequeo(f"Factor {col} válido", malos == 0, f"{malos} personas con factor faltante o no positivo")
    pob, pob_inei = p.facpob07.sum(), (hog.factor07 * hog.mieperho).sum()
    chequeo("Población expandida plausible", 32e6 < pob < 36e6 and 32e6 < pob_inei < 36e6,
            f"{pob:,.0f} personas con facpob07 y {pob_inei:,.0f} con factor07 × mieperho")
    codigos = sorted(p.ccdd.unique())
    chequeo("25 códigos departamentales (01-25)", codigos == sorted(DEPARTAMENTOS) == sorted(hog.ccdd.unique()),
            f"{len(codigos)} códigos: {', '.join(codigos)}")
    sin_dato = sorted(set(p.ccdd) - set(DEPARTAMENTOS))
    chequeo("Ningún departamento sin nombre", not sin_dato, f"códigos desconocidos: {sin_dato or 'ninguno'}")
    chequeo("Participación de alimentos calculable", p.gasto_alimentos_pct.notna().all(),
            f"{p.gasto_alimentos_pct.isna().sum()} personas en hogares con gasto total no positivo", esencial=False)

    peso_inei = hog.factor07 * hog.mieperho
    inei = {"pobreza": pct(hog.pobre, peso_inei), "extrema": pct(hog.pobre_extremo, peso_inei),
            "urbano": pct(hog.pobre[hog.urbano], peso_inei[hog.urbano]),
            "rural": pct(hog.pobre[~hog.urbano], peso_inei[~hog.urbano])}
    personas = {"pobreza": pct(p.pobre, p.facpob07), "extrema": pct(p.pobre_extremo, p.facpob07),
                "urbano": pct(p.pobre[p.urbano], p.facpob07[p.urbano]),
                "rural": pct(p.pobre[~p.urbano], p.facpob07[~p.urbano])}
    simple = 100 * p.pobre.mean()
    for clave, nombre in (("pobreza", "Pobreza monetaria nacional"), ("urbano", "Pobreza urbana"),
                          ("rural", "Pobreza rural"), ("extrema", "Pobreza extrema nacional")):
        tol = TOLERANCIA[clave]
        d1, d2 = abs(inei[clave] - REFERENCIA[clave]), abs(personas[clave] - REFERENCIA[clave])
        chequeo(f"{nombre} (método INEI: sumaria, factor07 × mieperho)", d1 <= tol,
                f"{inei[clave]:.2f} % (referencia {REFERENCIA[clave]} %, diferencia {d1:.2f} pp, tolerancia {tol})")
        chequeo(f"{nombre} (personas residentes, facpob07)", d2 <= tol,
                f"{personas[clave]:.2f} % (diferencia {d2:.2f} pp)")
    chequeo("La ponderación importa (el promedio simple no sirve)", abs(simple - inei["pobreza"]) > 1,
            f"promedio simple sin factores: {simple:.2f} % frente a {inei['pobreza']:.2f} % ponderado", esencial=False)

    cabecera = [f"Validación ENAHO {args.anio} (INEI, código {codigo}) — {datetime.now():%Y-%m-%d %H:%M}",
                f"Archivos: {zips['34'].name}/{f34} y {zips['02'].name}/{f02}",
                "Unidad de análisis: la persona. Pobreza territorial con el método INEI (hogares de la sumaria × factor07 × "
                "mieperho); características individuales con residentes habituales × facpob07.", ""]
    resumen = ["", f"Aprobadas: {sum('[APROBADA' in l for l in lineas)} · Fallidas: {len(fallas)} · "
                   f"Advertencias: {sum('[ADVERTENCIA' in l for l in lineas)}",
               f"Resultado: {'VALIDACIÓN APROBADA' if not fallas else 'VALIDACIÓN FALLIDA: ' + ', '.join(fallas)}"]
    texto = "\n".join(cabecera + lineas + resumen) + "\n"
    (args.salidas / "validacion.txt").write_text(texto, encoding="utf-8")
    print(texto)
    if fallas:
        sys.exit(f"ERROR: {len(fallas)} validaciones esenciales fallaron. No se escribió la base procesada.")

    # 7. Guardar
    columnas_h = LLAVES + ["ubigeo", "ccdd", "departamento", "dominio", "dominio_nombre", "estrato", "urbano", "area",
                           "pobreza", "pobreza_nombre", "pobre", "pobre_extremo", "mieperho", "linea", "linpe",
                           "gashog2d", "gasto_alimentos_pct", "factor07"]
    columnas_p = LLAVES + ["codperso"] + columnas_h[3:] + ["sexo", "edad", "grupo_edad", "p203", "facpob07"]
    base = args.salidas / f"personas_{args.anio}.parquet"
    p[columnas_p].to_parquet(base, index=False)
    hog[columnas_h].to_parquet(args.salidas / f"hogares_{args.anio}.parquet", index=False)
    tabla = indicadores(p, hog)
    tabla.to_csv(args.salidas / "indicadores.csv", index=False, encoding="utf-8")
    print(f"Personas: {base} ({len(p):,}) · Hogares: hogares_{args.anio}.parquet ({len(hog):,}) · "
          f"Indicadores: {args.salidas / 'indicadores.csv'} ({len(tabla)} filas)")

if __name__ == "__main__":
    try:
        main()
    except ValidacionFallida as e:
        sys.exit(f"ERROR: {e}")
