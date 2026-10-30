/* Tablero «Aprender después de la pandemia». Lee data/datos.json (de scripts/analizar_datos.py) y data/regiones.geojson. */
"use strict";

const estado = { grado: "4P", area: "Matemática", indicador: "satisfactorio", region: "", mapa: "cambio", brecha: "area",
                 orden: { col: "neto", asc: true } };
const INDICADORES = {
  satisfactorio: { nombre: "% en nivel satisfactorio", corto: "satisfactorio", unidad: "%", ee: "satisfactorio_ee", mejorArriba: true },
  debajo: { nombre: "% debajo de lo esperado", corto: "debajo de lo esperado", unidad: "%", ee: null, mejorArriba: false },
  medida: { nombre: "puntaje promedio", corto: "puntaje", unidad: " pts", ee: "medida_ee", mejorArriba: true },
};
const NIVELES = [["previo", "Previo al inicio"], ["inicio", "En inicio"], ["proceso", "En proceso"], ["satisfactorio", "Satisfactorio"]];
let D, GEO;

// ---------------------------------------------------------------- utilidades

const $ = (s) => document.querySelector(s);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const num = (x, d = 1) => (x == null || Number.isNaN(x) ? "—" : x.toFixed(d).replace(".", ","));
const signo = (x, d = 1) => (x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + num(Math.abs(x), d));
const pp = (x) => `${signo(x)} pp`;
const ind = () => INDICADORES[estado.indicador];
const decimales = () => (estado.indicador === "medida" ? 0 : 1);
const combo = () => D.combinaciones[`${estado.grado}|${estado.area}`];
const P = () => D.periodos;

function filas(filtro) {
  return D.resultados.filter((r) => r.grado === estado.grado && r.area === estado.area && filtro(r));
}
function serie(dimension, grupo) {
  return filas((r) => r.dimension === dimension && r.grupo === grupo).sort((a, b) => a.anio - b.anio);
}
function valor(r) { return r ? r[estado.indicador] : null; }
function ee(r) { const c = ind().ee; return r && c && r[c] != null ? r[c] : 0; }
function enAnio(s, anio) { return s.find((r) => r.anio === anio); }

/** Cambio entre dos años y si es significativo (95 %); sin error estándar publicado, null. */
function cambio(a, b) {
  if (!a || !b) return { d: null, sig: null };
  const d = valor(b) - valor(a);
  if (!ind().ee) return { d, sig: null };
  const e = Math.sqrt(ee(a) ** 2 + ee(b) ** 2);
  return { d, sig: e > 0 ? Math.abs(d) > 1.96 * e : true };
}

/** Pérdida, recuperación y neto de cada región para el indicador elegido. */
function tablaRegiones() {
  const { antes, pandemia, ahora } = P();
  const regiones = [...new Set(filas((r) => r.dimension === "region").map((r) => r.grupo))];
  return regiones.map((g) => {
    const s = serie("region", g);
    const a = enAnio(s, antes), p = enAnio(s, pandemia), h = enAnio(s, ahora);
    const neto = cambio(a, h);
    const bueno = ind().mejorArriba ? neto.d > 0 : neto.d < 0;
    const estadoNeto = neto.sig === null ? "sin error publicado" : !neto.sig ? "igual a 2019"
      : bueno ? "mejor que 2019" : "peor que 2019";
    return { region: g, antes: valor(a), pandemia: valor(p), ahora: valor(h), perdida: valor(p) - valor(a),
             recuperacion: valor(h) - valor(p), neto: neto.d, sig: neto.sig, estado: estadoNeto };
  });
}

function temaPlotly(extra = {}) {
  return Object.assign({
    paper_bgcolor: css("--superficie"), plot_bgcolor: css("--superficie"),
    font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', size: 13, color: css("--tinta-2") },
    margin: { l: 48, r: 16, t: 8, b: 40 }, separators: ",.", showlegend: false,
    hoverlabel: { bgcolor: css("--superficie"), bordercolor: css("--eje"), font: { color: css("--tinta") } },
    xaxis: { gridcolor: css("--rejilla"), linecolor: css("--eje"), zeroline: false, tickfont: { color: css("--tenue") } },
    yaxis: { gridcolor: css("--rejilla"), linecolor: css("--eje"), zeroline: false, tickfont: { color: css("--tenue") } },
  }, extra);
}
const CONFIG = { responsive: true, displayModeBar: false, locale: "es" };

function franjaPandemia() {
  return { type: "rect", xref: "x", yref: "paper", x0: 2019.5, x1: 2021.5, y0: 0, y1: 1, fillcolor: css("--sombreado"),
           line: { width: 0 }, layer: "below" };
}
/** En pantallas angostas los años van cada dos y sin el rótulo de la franja. */
const angosto = (id) => document.getElementById(id).clientWidth < 480;
function textoFranja(id) {
  if (angosto(id)) return { visible: false };
  return { x: 2020.5, y: 1, xref: "x", yref: "paper", yanchor: "top", text: "cierre de<br>escuelas", showarrow: false,
           font: { size: 11, color: css("--tenue") } };
}

// ---------------------------------------------------------------- KPIs

function kpis() {
  const c = combo(), k = c.kpis, br = c.brechas[estado.brecha];
  const { antes, pandemia, ahora } = P();
  const grado = D.grados[estado.grado];
  let a = k.satisfactorio_antes, p = k.satisfactorio_pandemia, h = k.satisfactorio_ahora, donde = "nacional";
  let perdida = k.perdida.pp, recup = k.recuperacion.pp;
  if (estado.region) {
    const r = c.regiones.find((x) => x.region === estado.region);
    [a, p, h, perdida, recup, donde] = [r.antes, r.pandemia, r.ahora, r.perdida, r.recuperacion, estado.region];
  }
  const recuperado = perdida < 0 ? `${num(100 * recup / -perdida, 0)} %` : "—";
  const detalleRecup = perdida < 0 ? `de lo perdido (${pp(recup)} entre ${pandemia} y ${ahora})`
    : `no cayó en ${pandemia} (${pp(perdida)})`;
  const tiles = [
    { t: `Satisfactorio en ${ahora} · ${donde}`, v: `${num(h)} %`, d: `${antes}: ${num(a)} % · ${pandemia}: ${num(p)} %` },
    { t: `Cambio ${antes} → ${pandemia}`, v: pp(perdida), clase: perdida < 0 ? "flecha-mala" : "flecha-buena",
      d: perdida < 0 ? "puntos menos en satisfactorio tras el cierre de escuelas" : "subió pese al cierre de escuelas" },
    { t: `Recuperado al ${ahora}`, v: recuperado, d: detalleRecup },
    { t: `Regiones peor que en ${antes}`, v: `${k.regiones_debajo} de 26`,
      d: `${k.regiones_supera} ya lo superan; el resto, sin diferencia significativa` },
    { t: `Brecha ${br.nombre.toLowerCase()} en ${ahora}`, v: pp(br.ahora), d: `en ${antes} era ${pp(br.antes)} (nacional)` },
  ];
  $("#kpis").innerHTML = tiles.map((x) => `<div class="kpi"><p class="titulo">${x.t}</p>
    <div class="valor ${x.clase || ""}">${x.v}</div><div class="detalle">${x.d}</div></div>`).join("");
  $("#kpi-contexto").textContent = `${grado} · ${estado.area}. Los KPIs usan el % de estudiantes en nivel satisfactorio; ` +
    `«pp» = puntos porcentuales.` + (estado.region ? " Los tres primeros corresponden a la región elegida." : "");
}

// ---------------------------------------------------------------- gráficos

function gEvolucion() {
  const nac = serie("nacional", "Nacional");
  const trazos = [];
  const agregar = (s, nombre, color) => {
    trazos.push({
      x: s.map((r) => r.anio), y: s.map(valor), name: nombre, type: "scatter", mode: "lines+markers",
      line: { color, width: 2 }, marker: { size: 8, color, line: { color: css("--superficie"), width: 2 } },
      error_y: { type: "data", array: s.map((r) => 1.96 * ee(r)), visible: !!ind().ee, color, thickness: 1.2, width: 4 },
      hovertemplate: `<b>${nombre}</b> · %{x}<br>${ind().nombre}: %{y:.${decimales()}f}${ind().unidad}<extra></extra>`,
    });
  };
  agregar(nac, "Nacional", css("--serie-1"));
  if (estado.region) agregar(serie("region", estado.region), estado.region, css("--serie-2"));
  const ultimos = trazos.map((t) => ({ x: t.x.at(-1), y: t.y.at(-1), text: ` ${t.name}`, xanchor: "left", showarrow: false,
                                       font: { size: 12, color: css("--tinta-2") } }));
  $("#t-evolucion").textContent = `Evolución: ${ind().nombre}`;
  $("#s-evolucion").textContent = `${D.grados[estado.grado]} · ${estado.area} · ${estado.region || "todo el país"}`;
  Plotly.react("g-evolucion", trazos, temaPlotly({
    shapes: [franjaPandemia()], annotations: [textoFranja("g-evolucion"), ...ultimos],
    xaxis: { ...temaPlotly().xaxis, dtick: angosto("g-evolucion") ? 2 : 1, tickangle: 0,
             range: [D.anios[estado.grado][0] - 0.4, 2026.6] },
    yaxis: { ...temaPlotly().yaxis, ticksuffix: ind().unidad === "%" ? " %" : "", rangemode: estado.indicador === "medida" ? "normal" : "tozero" },
    margin: { l: 52, r: 110, t: 8, b: 36 },
  }), CONFIG);
}

function gNiveles() {
  const s = estado.region ? serie("region", estado.region) : serie("nacional", "Nacional");
  const colores = { previo: css("--nivel-previo"), inicio: css("--nivel-inicio"), proceso: css("--nivel-proceso"),
                    satisfactorio: css("--nivel-satisfactorio") };
  const trazos = NIVELES.map(([c, nombre]) => ({
    type: "bar", orientation: "h", name: nombre, y: s.map((r) => String(r.anio)), x: s.map((r) => r[c]),
    marker: { color: colores[c], line: { color: css("--superficie"), width: 2 } },
    hovertemplate: `<b>%{y}</b> · ${nombre}: %{x:.1f} %<extra></extra>`,
  }));
  // por posición (0, 1, 2…): con y = "2016" Plotly toma el año como número y estira el eje de categorías
  const etiquetas = s.map((r, i) => ({ x: 100, y: i, text: ` ${num(r.satisfactorio)} %`, xanchor: "left",
                                    showarrow: false, font: { size: 12, color: css("--tinta") } }));
  $("#s-niveles").textContent = `${D.grados[estado.grado]} · ${estado.area} · ${estado.region || "todo el país"} · a la derecha, el % satisfactorio`;
  $("#leyenda-niveles").innerHTML = NIVELES.map(([c, n]) => `<span><i style="background:${colores[c]}"></i>${n}</span>`).join("");
  Plotly.react("g-niveles", trazos, temaPlotly({
    barmode: "stack", bargap: 0.28, annotations: etiquetas,
    xaxis: { ...temaPlotly().xaxis, range: [0, 100], ticksuffix: " %", fixedrange: true },
    yaxis: { ...temaPlotly().yaxis, autorange: "reversed", type: "category", fixedrange: true, gridcolor: "rgba(0,0,0,0)" },
    margin: { l: 44, r: 54, t: 4, b: 32 },
  }), CONFIG);
}

function opcionesMapa() {
  const { antes, pandemia, ahora } = P();
  const anios = D.anios[estado.grado];
  const opciones = [["cambio", `Cambio ${antes} → ${ahora}`], ["perdida", `Cambio ${antes} → ${pandemia}`],
                    ["recuperacion", `Cambio ${pandemia} → ${ahora}`], ...anios.slice().reverse().map((a) => [String(a), `Nivel en ${a}`])];
  if (!opciones.some(([v]) => v === estado.mapa)) estado.mapa = "cambio";
  $("#f-mapa").innerHTML = opciones.map(([v, t]) => `<option value="${v}" ${v === estado.mapa ? "selected" : ""}>${t}</option>`).join("");
}

function gMapa() {
  const tabla = tablaRegiones();
  const esCambio = ["cambio", "perdida", "recuperacion"].includes(estado.mapa);
  const anio = Number(estado.mapa);
  const regiones = tabla.map((r) => r.region);
  const valores = esCambio
    ? tabla.map((r) => ({ cambio: r.neto, perdida: r.perdida, recuperacion: r.recuperacion }[estado.mapa]))
    : regiones.map((g) => valor(enAnio(serie("region", g), anio)));
  let escala, zmin, zmax, sufijo;
  if (esCambio) {
    const m = Math.max(...valores.map(Math.abs)) || 1;
    [zmin, zmax] = [-m, m];
    const [pos, neg] = ind().mejorArriba ? [css("--div-pos"), css("--div-neg")] : [css("--div-neg"), css("--div-pos")];
    escala = [[0, neg], [0.5, css("--div-medio")], [1, pos]];
    sufijo = ind().unidad === "%" ? " pp" : " pts";
  } else {
    const lim = estado.indicador === "medida" ? null : [0, Math.max(...valores)];
    [zmin, zmax] = lim || [Math.min(...valores), Math.max(...valores)];
    const rampa = [css("--sec-1"), css("--sec-2"), css("--sec-3"), css("--sec-4"), css("--sec-5")];
    escala = rampa.map((c, i) => [i / (rampa.length - 1), c]);
    sufijo = ind().unidad;
  }
  const bordes = regiones.map((g) => (g === estado.region ? css("--tinta") : css("--superficie")));
  const anchos = regiones.map((g) => (g === estado.region ? 2.5 : 0.8));
  const traza = {
    type: "choropleth", geojson: GEO, featureidkey: "properties.region", locations: regiones, z: valores,
    colorscale: escala, zmin, zmax, marker: { line: { color: bordes, width: anchos } },
    colorbar: { thickness: 10, len: 0.6, x: 0.98, ticksuffix: sufijo, outlinewidth: 0, tickfont: { color: css("--tenue") } },
    hovertemplate: `<b>%{location}</b><br>%{z:.${decimales()}f}${sufijo}<extra></extra>`,
  };
  const { antes, pandemia, ahora } = P();
  const titulo = esCambio ? { cambio: `${antes} → ${ahora}`, perdida: `${antes} → ${pandemia}`, recuperacion: `${pandemia} → ${ahora}` }[estado.mapa] : anio;
  const nombre = ind().nombre.replace(/^\p{L}/u, (c) => c.toUpperCase());
  $("#t-mapa").textContent = esCambio ? `Cambio en ${ind().corto}, ${titulo}` : `${nombre}, ${titulo}`;
  $("#s-mapa").textContent = esCambio
    ? `${ind().mejorArriba ? "Azul: mejoró; rojo: empeoró" : "Azul: bajó (mejor); rojo: subió (peor)"}. Gris: sin cambio.`
    : `${D.grados[estado.grado]} · ${estado.area}. Más oscuro, valor más alto.`;
  Plotly.react("g-mapa", [traza], temaPlotly({
    geo: { fitbounds: "locations", visible: false, bgcolor: css("--superficie"), projection: { type: "mercator" } },
    margin: { l: 0, r: 0, t: 0, b: 0 }, dragmode: false,
  }), CONFIG);
}

function gRegiones() {
  const t = tablaRegiones().sort((a, b) => (ind().mejorArriba ? a.neto - b.neto : b.neto - a.neto));
  const { antes, pandemia, ahora } = P();
  const y = t.map((r) => r.region);
  // una línea gris por región, del menor al mayor de sus tres valores
  const conectores = { type: "scatter", mode: "lines", line: { color: css("--eje"), width: 2 }, hoverinfo: "skip",
                       x: t.flatMap((r) => [Math.min(r.antes, r.pandemia, r.ahora), Math.max(r.antes, r.pandemia, r.ahora), null]),
                       y: t.flatMap((r) => [r.region, r.region, null]) };
  const puntos = [[antes, "antes", css("--antes")], [pandemia, "pandemia", css("--serie-2")], [ahora, "ahora", css("--serie-1")]]
    .map(([anio, c, color]) => ({
      type: "scatter", mode: "markers", name: String(anio), y, x: t.map((r) => r[c]),
      marker: { size: 10, color, line: { color: css("--superficie"), width: 2 } },
      hovertemplate: `<b>%{y}</b> · ${anio}: %{x:.${decimales()}f}${ind().unidad}<extra></extra>`,
    }));
  const sel = estado.region ? [{ type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: y.indexOf(estado.region) - 0.5,
                                 y1: y.indexOf(estado.region) + 0.5, fillcolor: css("--acento-suave"), line: { width: 0 }, layer: "below" }] : [];
  $("#s-regiones").textContent = `${ind().nombre} en ${antes}, ${pandemia} y ${ahora}. Arriba, las regiones que más ` +
    `${ind().mejorArriba ? "perdieron" : "empeoraron"} entre ${antes} y ${ahora}.`;
  $("#leyenda-regiones").innerHTML = [[antes, "--antes"], [pandemia, "--serie-2"], [ahora, "--serie-1"]]
    .map(([a, v]) => `<span><i style="background:${css(v)};border-radius:50%"></i>${a}</span>`).join("");
  Plotly.react("g-regiones", [conectores, ...puntos], temaPlotly({
    shapes: sel, hovermode: "closest",
    yaxis: { ...temaPlotly().yaxis, autorange: "reversed", type: "category", fixedrange: true, automargin: true, gridcolor: css("--rejilla") },
    xaxis: { ...temaPlotly().xaxis, ticksuffix: ind().unidad === "%" ? " %" : "", fixedrange: true, side: "top" },
    margin: { l: 130, r: 16, t: 28, b: 16 },
  }), CONFIG);
}

function gDispersion() {
  const t = tablaRegiones();
  const { antes, pandemia, ahora } = P();
  const xs = t.map((r) => r.perdida), ys = t.map((r) => r.recuperacion);
  const lim = Math.max(...xs.map(Math.abs), ...ys.map(Math.abs)) * 1.15;
  // se rotulan la región elegida, las dos que más empeoraron en 2019-2022 y la que más mejoró en 2022-2025
  const s = ind().mejorArriba ? 1 : -1;
  const destacadas = new Set([estado.region,
    ...[...t].sort((a, b) => s * (a.perdida - b.perdida)).slice(0, 2).map((r) => r.region),
    ...[...t].sort((a, b) => s * (b.recuperacion - a.recuperacion)).slice(0, 1).map((r) => r.region)].filter(Boolean));
  const traza = {
    type: "scatter", mode: "markers", x: xs, y: ys, text: t.map((r) => r.region),
    marker: { size: t.map((r) => (r.region === estado.region ? 14 : 10)),
              color: t.map((r) => (r.region === estado.region ? css("--serie-2") : css("--serie-1"))),
              line: { color: css("--superficie"), width: 2 } },
    hovertemplate: `<b>%{text}</b><br>${antes}→${pandemia}: %{x:+.${decimales()}f}<br>${pandemia}→${ahora}: %{y:+.${decimales()}f}<extra></extra>`,
  };
  const diagonal = { type: "line", x0: -lim, y0: lim, x1: lim, y1: -lim, line: { color: css("--tenue"), width: 1 } };
  const etiquetas = t.filter((r) => destacadas.has(r.region)).map((r) => ({
    x: r.perdida, y: r.recuperacion, text: r.region, showarrow: false, yshift: 12, font: { size: 11, color: css("--tinta-2") } }));
  $("#s-dispersion").textContent = `Cada punto es una región: cuánto cambió su ${ind().corto} en ${antes}→${pandemia} (eje horizontal) y en ${pandemia}→${ahora} (vertical).`;
  Plotly.react("g-dispersion", [traza], temaPlotly({
    shapes: [diagonal,
      { type: "line", x0: 0, x1: 0, y0: -lim, y1: lim, line: { color: css("--eje"), width: 1 } },
      { type: "line", y0: 0, y1: 0, x0: -lim, x1: lim, line: { color: css("--eje"), width: 1 } }],
    annotations: etiquetas, hovermode: "closest",
    xaxis: { ...temaPlotly().xaxis, range: [-lim, lim], title: { text: `${antes} → ${pandemia}`, font: { size: 12 } }, fixedrange: true },
    yaxis: { ...temaPlotly().yaxis, range: [-lim, lim], title: { text: `${pandemia} → ${ahora}`, font: { size: 12 } }, fixedrange: true },
    margin: { l: 56, r: 16, t: 8, b: 48 },
  }), CONFIG);
}

function gBrecha() {
  const br = combo().brechas[estado.brecha];
  const trazos = [[br.referencia, css("--serie-1")], [br.comparado, css("--serie-2")]].map(([g, color]) => {
    const s = serie(estado.brecha, g);
    return { x: s.map((r) => r.anio), y: s.map(valor), name: g, type: "scatter", mode: "lines+markers",
             line: { color, width: 2 }, marker: { size: 8, color, line: { color: css("--superficie"), width: 2 } },
             hovertemplate: `<b>${g}</b> · %{x}<br>${ind().nombre}: %{y:.${decimales()}f}${ind().unidad}<extra></extra>` };
  });
  const ultimos = trazos.map((t) => ({ x: t.x.at(-1), y: t.y.at(-1), text: ` ${t.name}`, xanchor: "left", showarrow: false,
                                       font: { size: 12, color: css("--tinta-2") } }));
  $("#t-brecha").textContent = `Brecha: ${br.referencia.toLowerCase()} y ${br.comparado.toLowerCase()}`;
  const enAhora = (g) => valor(enAnio(serie(estado.brecha, g), P().ahora));
  $("#s-brecha").textContent = `${ind().nombre}, nacional. Diferencia en ${P().ahora}: ` +
    `${signo(enAhora(br.referencia) - enAhora(br.comparado), decimales())}${ind().unidad === "%" ? " pp" : " pts"}.`;
  Plotly.react("g-brecha", trazos, temaPlotly({
    shapes: [franjaPandemia()], annotations: [textoFranja("g-brecha"), ...ultimos],
    xaxis: { ...temaPlotly().xaxis, dtick: angosto("g-brecha") ? 2 : 1, tickangle: 0,
             range: [D.anios[estado.grado][0] - 0.4, 2026.9] },
    yaxis: { ...temaPlotly().yaxis, ticksuffix: ind().unidad === "%" ? " %" : "", rangemode: estado.indicador === "medida" ? "normal" : "tozero" },
    margin: { l: 52, r: 96, t: 8, b: 36 },
  }), CONFIG);
}

// ---------------------------------------------------------------- tabla y descarga

function tabla() {
  const { antes, pandemia, ahora } = P();
  const cols = [["region", "Región"], ["antes", antes], ["pandemia", pandemia], ["ahora", ahora],
                ["perdida", `${antes}→${pandemia}`], ["recuperacion", `${pandemia}→${ahora}`], ["neto", `${antes}→${ahora}`],
                ["estado", "¿Significativo?"]];
  const { col, asc } = estado.orden;
  const t = tablaRegiones().sort((a, b) => {
    const x = a[col], y = b[col];
    return (typeof x === "string" ? x.localeCompare(y, "es") : x - y) * (asc ? 1 : -1);
  });
  const d = decimales();
  const icono = (e) => ({ "mejor que 2019": "▲", "peor que 2019": "▼", "igual a 2019": "＝" }[e] || "");
  $("#s-tabla").textContent = `${D.grados[estado.grado]} · ${estado.area} · ${ind().nombre}. Cambios en ${ind().unidad === "%" ? "puntos porcentuales" : "puntos de la escala"}.`;
  $("#tabla").innerHTML = `<thead><tr>${cols.map(([c, n]) => `<th data-col="${c}" scope="col">${n}${c === col ? (asc ? " ↑" : " ↓") : ""}</th>`).join("")}</tr></thead>
    <tbody>${t.map((r) => `<tr data-region="${r.region}" class="${r.region === estado.region ? "resaltada" : ""}">
      <td>${r.region}</td><td>${num(r.antes, d)}</td><td>${num(r.pandemia, d)}</td><td>${num(r.ahora, d)}</td>
      <td>${signo(r.perdida, d)}</td><td>${signo(r.recuperacion, d)}</td><td>${signo(r.neto, d)}</td>
      <td><span class="estado">${icono(r.estado)} ${r.estado}</span></td></tr>`).join("")}</tbody>`;
}

function descargar() {
  const cols = ["grado", "area", "dimension", "grupo", "anio", "evaluacion", "satisfactorio", "satisfactorio_ee", "proceso",
                "inicio", "previo", "debajo", "medida", "medida_ee"];
  const f = filas((r) => !estado.region || r.dimension !== "region" || r.grupo === estado.region);
  const csv = [cols.join(","), ...f.map((r) => cols.map((c) => (r[c] == null ? "" : `"${String(r[c]).replace(/"/g, '""')}"`)).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url,
    download: `umc_${estado.grado}_${estado.area}${estado.region ? "_" + estado.region.replace(/\s+/g, "_") : ""}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------- controles

/** Los filtros viven en la URL (#grado=2S&area=Lectura&region=Cusco…) para compartir o capturar una vista. */
const EN_URL = ["grado", "area", "indicador", "region", "mapa", "brecha"];
function leerURL(regiones) {
  const h = new URLSearchParams(location.hash.slice(1));
  const validos = { grado: Object.keys(D.grados), area: ["Matemática", "Lectura"], indicador: Object.keys(INDICADORES),
                    region: regiones, brecha: ["area", "gestion", "sexo"], mapa: null };
  for (const k of EN_URL) {
    const v = h.get(k);
    if (v && (!validos[k] || validos[k].includes(v))) estado[k] = v;  // el mapa se valida en opcionesMapa()
  }
}
function escribirURL() {
  const h = new URLSearchParams();
  for (const k of EN_URL) if (estado[k]) h.set(k, estado[k]);
  history.replaceState(null, "", `#${h}`);
}

function dibujar() {
  escribirURL();
  document.querySelectorAll("#f-grado button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.valor === estado.grado));
  document.querySelectorAll("#f-area button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.valor === estado.area));
  $("#f-indicador").value = estado.indicador;
  $("#f-region").value = estado.region;
  $("#f-brecha").value = estado.brecha;
  opcionesMapa();
  kpis();
  gEvolucion(); gNiveles(); gMapa(); gRegiones(); gDispersion(); gBrecha(); tabla();
}

function elegirRegion(g) {
  estado.region = estado.region === g ? "" : g;
  dibujar();
}

function conectar() {
  $("#f-grado").addEventListener("click", (e) => { if (e.target.dataset.valor) { estado.grado = e.target.dataset.valor; dibujar(); } });
  $("#f-area").addEventListener("click", (e) => { if (e.target.dataset.valor) { estado.area = e.target.dataset.valor; dibujar(); } });
  $("#f-indicador").addEventListener("change", (e) => { estado.indicador = e.target.value; dibujar(); });
  $("#f-region").addEventListener("change", (e) => { estado.region = e.target.value; dibujar(); });
  $("#f-mapa").addEventListener("change", (e) => { estado.mapa = e.target.value; escribirURL(); gMapa(); });
  $("#f-brecha").addEventListener("change", (e) => { estado.brecha = e.target.value; escribirURL(); kpis(); gBrecha(); });
  $("#limpiar").addEventListener("click", () => {
    Object.assign(estado, { grado: "4P", area: "Matemática", indicador: "satisfactorio", region: "", mapa: "cambio", brecha: "area" });
    dibujar();
  });
  $("#descargar").addEventListener("click", descargar);
  $("#tabla").addEventListener("click", (e) => {
    const th = e.target.closest("th");
    if (th) {
      const c = th.dataset.col;
      estado.orden = { col: c, asc: estado.orden.col === c ? !estado.orden.asc : true };
      tabla();
      return;
    }
    const tr = e.target.closest("tr[data-region]");
    if (tr) elegirRegion(tr.dataset.region);
  });
  for (const id of ["g-mapa", "g-regiones", "g-dispersion"]) {
    document.getElementById(id).on("plotly_click", (ev) => {
      const p = ev.points[0];
      elegirRegion(p.location || p.text || p.y);
    });
  }
  $("#boton-tema").addEventListener("click", () => {
    const oscuro = getComputedStyle(document.documentElement).colorScheme === "dark";
    document.documentElement.dataset.theme = oscuro ? "light" : "dark";
    try { localStorage.setItem("tema", document.documentElement.dataset.theme); } catch (e) {}
    dibujar();
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", dibujar);
}

async function iniciar() {
  try {
    [D, GEO] = await Promise.all([fetch("data/datos.json").then((r) => r.json()), fetch("data/regiones.geojson").then((r) => r.json())]);
  } catch (e) {
    $("#kpis").innerHTML = `<p>No se pudieron cargar los datos (${e.message}). Abre el tablero desde un servidor web, no como archivo local.</p>`;
    return;
  }
  const regiones = [...new Set(D.resultados.filter((r) => r.dimension === "region").map((r) => r.grupo))]
    .sort((a, b) => a.localeCompare(b, "es"));
  $("#f-region").insertAdjacentHTML("beforeend", regiones.map((g) => `<option value="${g}">${g}</option>`).join(""));
  leerURL(regiones);
  dibujar();
  conectar();
}
iniciar();
