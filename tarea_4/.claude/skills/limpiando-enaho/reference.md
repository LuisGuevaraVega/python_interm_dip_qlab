# Referencia: ENAHO 2024 para `limpiando-enaho`

## Archivos del INEI

| Archivo (dentro del zip) | Una fila por | Filas | Llaves | Factor |
|---|---|---|---|---|
| `966-Modulo34/sumaria-2024.dta` | hogar | 33,691 | `conglome`, `vivienda`, `hogar` | `factor07` |
| `966-Modulo02/enaho01-2024-200.dta` | persona | 117,721 | las tres + `codperso` | `facpob07` |

Descarga: `https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo{34,02}.zip`.
El zip 34 trae también `sumaria-2024-12g.dta` (gasto en 12 grupos): no se usa.

## Reglas que el script aplica siempre

| Paso | Regla |
|---|---|
| Lectura | `pd.read_stata(..., convert_categoricals=False)`; llaves y `ubigeo` como texto (`conglome` y `ubigeo` de 6 dígitos con ceros iniciales) |
| Nombres | minúsculas; `aÑo` → `anio` |
| Residentes habituales | `((p204 == 1) & (p205 == 2)) \| ((p204 == 2) & (p206 == 1))` → 108,664 |
| Unión | personas → hogares por `conglome`, `vivienda`, `hogar` con `merge(..., how="left", validate="m:1", indicator=True)`; se exige que no cambie el número de filas y que nadie quede sin hogar |
| Departamento | `ccdd = ubigeo[:2]` (01 Amazonas … 07 Callao … 15 Lima … 25 Ucayali). Lima y Callao separados |
| Área | `urbano = estrato <= 5` (centros poblados de 2,000 a más habitantes) |
| Pobreza | `pobreza`: 1 pobre extremo, 2 pobre no extremo, 3 no pobre → `pobre = pobreza <= 2`, `pobre_extremo = pobreza == 1` |
| Gasto en alimentos | suma del grupo 1 de la sumaria (`gru11hd`, `gru12hd1`, `gru12hd2`, `gru13hd1`–`gru13hd4`, `gru14hd`, `gru14hd1`–`gru14hd6`: comprado, autoconsumo, especie, donaciones, dentro y fuera del hogar) ÷ `gashog2d` (gasto total bruto anual) × 100 |

## Ponderación y unidad de análisis

- **Método INEI (pobreza territorial):** cada hogar de la sumaria pesa `factor07 × mieperho` (las personas que
  representa). Reproduce la referencia: 27.58 % nacional, 24.81 % urbana, 39.30 % rural, 5.50 % extrema y los 25
  departamentos de la sesión 16 sin diferencia al décimo.
- **Personas (características individuales):** cada residente habitual pesa `facpob07`. Da 27.53 % nacional; difiere
  del método INEI hasta 0.5 pp en departamentos con muestra chica (Huánuco, Puno) porque el conjunto de residentes
  habituales no coincide exactamente con `mieperho` (que excluye trabajadoras del hogar y pensionistas).
- La participación del gasto en alimentos es un atributo del hogar asignado a cada persona; se promedia con `facpob07`.
- El promedio simple sin factores da 25.61 %: subestima la pobreza en 2 pp. Por eso nunca se usa.

## Validaciones (salidas/validacion.txt)

| Validación | Esencial | Criterio |
|---|---|---|
| Llaves únicas en sumaria y personas | sí | 0 duplicados |
| Ceros iniciales | sí | `conglome` y `ubigeo` de 6 caracteres |
| Residentes habituales | sí | exactamente 108,664 |
| Unión m:1 | sí | mismas filas antes y después; 0 personas sin hogar |
| Factores | sí | sin faltantes ni valores ≤ 0; población expandida entre 32 y 36 millones |
| Departamentos | sí | los 25 códigos 01–25 |
| Pobreza nacional | sí | a ≤ 0.1 pp de 27.6 % (en ambos métodos) |
| Pobreza urbana / rural / extrema | sí | a ≤ 0.15 pp de 24.8 / 39.3 / 5.5 % |
| Filas originales, gasto calculable | no (advertencia) | 33,691 hogares, 117,721 filas |

Si una esencial falla, el script sale con código 1 y no escribe las bases.

## Otras variables útiles

| Variable | Base | Qué es |
|---|---|---|
| `dominio` | ambas | 1 costa norte … 7 selva, 8 Lima Metropolitana |
| `linea`, `linpe` | ambas | línea de pobreza total y alimentaria (soles por persona al mes) |
| `gashog2d` | ambas | gasto total bruto anual del hogar (soles) |
| `p203` | personas | parentesco con el jefe del hogar (1 = jefe) |
| `p207`, `p208a` | personas | sexo (1 hombre, 2 mujer) y edad en años |
