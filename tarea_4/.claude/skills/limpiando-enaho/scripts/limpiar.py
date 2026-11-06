"""Limpia la ENAHO (módulos 34 sumaria y 02 miembros) y arma una base de personas con pobreza y factor.

    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024
    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2019

Pipeline fijo (Sesión 16): leer -> normalizar -> filtrar residentes -> unir m:1 -> construir -> validar -> guardar.
Si una validación esencial falla, el script escribe validacion_<anio>.txt con el detalle y termina con código 1.
Ninguna cifra se ajusta para que coincida con la referencia.
"""
import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd

RAIZ = Path.cwd()
DATOS, SALIDAS = RAIZ / "datos", RAIZ / "salidas"
LLAVES = ["conglome", "vivienda", "hogar"]

# Código INEI del portal de microdatos y cifras oficiales para validar (ver reference.md)
ENCUESTAS = {
    2024: {"codigo": 966, "pobreza": 27.6, "residentes": 108_664, "urbano": 24.8, "rural": 39.3},
    2019: {"codigo": 687, "pobreza": 20.2, "residentes": None, "urbano": 14.6, "rural": 40.8},
}
TOL_NACIONAL, TOL_AREA = 0.1, 0.3
CODIGOS_DPTO = {f"{i:02d}" for i in range(1, 26)}


def leer(zip_path, nombre, columnas):
    """Lee un .dta dentro del zip sin convertir etiquetas y con las llaves como texto (conserva ceros)."""
    with zipfile.ZipFile(zip_path) as z:
        miembro = next(m for m in z.namelist() if m.lower().endswith(nombre))
        df = pd.read_stata(z.open(miembro), convert_categoricals=False)
    df.columns = [c.lower() for c in df.columns]  # "aÑo" -> "año"
    df = df.rename(columns={"año": "anio"})
    for c in LLAVES + ["codperso", "ubigeo"]:
        if c in df:
            df[c] = df[c].astype(str).str.strip()
    return df[[c for c in columnas if c in df]]


def ponderada(df, var, peso):
    return 100 * (df[var] * df[peso]).sum() / df[peso].sum()


def main(anio):
    cfg = ENCUESTAS[anio]
    cod = cfg["codigo"]
    z34, z02 = DATOS / f"{cod}-Modulo34.zip", DATOS / f"{cod}-Modulo02.zip"
    faltan = [p.name for p in (z34, z02) if not p.exists()]
    if faltan:
        sys.exit(f"ERROR: faltan {faltan} en datos/. Bájenlos de "
                 f"https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{cod}-Modulo34.zip (y Modulo02).")

    # 1-2. Leer y normalizar
    hog = leer(z34, f"sumaria-{anio}.dta", LLAVES + ["ubigeo", "dominio", "estrato", "mieperho", "pobreza", "factor07"])
    per = leer(z02, f"enaho01-{anio}-200.dta", LLAVES + ["codperso", "p204", "p205", "p206", "p207", "p208a", "facpob07"])
    n_hog, n_per = len(hog), len(per)

    # 3. Residentes habituales (condición de la Sesión 16)
    res = per[((per.p204 == 1) & (per.p205 == 2)) | ((per.p204 == 2) & (per.p206 == 1))].copy()

    # 4. Unir personas (m) con hogares (1)
    base = res.merge(hog, on=LLAVES, how="left", validate="m:1", indicator=True)

    # 5. Construir indicadores
    base["departamento"] = base.ubigeo.str[:2]
    base["urbano"] = (base.estrato <= 5).astype(int)
    base["area"] = base.urbano.map({1: "Urbana", 0: "Rural"})
    base["pobre"] = (base.pobreza <= 2).astype(int)
    base["pobre_extremo"] = (base.pobreza == 1).astype(int)
    base["sexo"] = base.p207.map({1: "Hombre", 2: "Mujer"})
    base["edad"] = base.p208a
    base["grupo_edad"] = pd.cut(base.edad, [-1, 13, 17, 29, 44, 59, 200],
                                labels=["0-13", "14-17", "18-29", "30-44", "45-59", "60+"]).astype(str)
    base["anio"] = anio

    # Estimación de hogares (oficial INEI): sumaria con factor07 × mieperho
    hog["pobre"] = (hog.pobreza <= 2).astype(int)
    hog["peso_personas"] = hog.factor07 * hog.mieperho
    pob_hogares = ponderada(hog, "pobre", "peso_personas")
    pob_personas = ponderada(base, "pobre", "facpob07")
    urb = ponderada(hog[hog.estrato <= 5], "pobre", "peso_personas")
    rur = ponderada(hog[hog.estrato > 5], "pobre", "peso_personas")
    ext = ponderada(hog.assign(e=(hog.pobreza == 1).astype(int)), "e", "peso_personas")

    # 6. Validar
    chequeos = []

    def chequear(nombre, ok, detalle, esencial=True):
        chequeos.append((nombre, bool(ok), detalle, esencial))

    chequear("Llaves de hogar únicas en la sumaria", not hog.duplicated(LLAVES).any(), f"{n_hog:,} hogares")
    chequear("Llaves de persona únicas en el módulo 02", not per.duplicated(LLAVES + ["codperso"]).any(), f"{n_per:,} filas")
    chequear("La unión no pierde personas (todas tienen hogar)", (base._merge == "both").all(),
             f"{(base._merge != 'both').sum()} sin hogar")
    chequear("La unión no duplica filas", len(base) == len(res), f"{len(res):,} antes, {len(base):,} después")
    if cfg["residentes"]:
        chequear("Residentes habituales = referencia", len(res) == cfg["residentes"],
                 f"{len(res):,} (ref. {cfg['residentes']:,})")
    else:
        chequear("Residentes habituales (sin referencia oficial publicada)", len(res) > 0, f"{len(res):,}", esencial=False)
    deps = set(base.departamento.unique())
    chequear("25 códigos departamentales (01-25)", deps == CODIGOS_DPTO, f"{len(deps)} códigos: faltan {sorted(CODIGOS_DPTO - deps)}, sobran {sorted(deps - CODIGOS_DPTO)}")
    chequear("Factores de expansión positivos y sin faltantes",
             base.facpob07.notna().all() and (base.facpob07 > 0).all() and (hog.factor07 > 0).all(),
             f"suma facpob07 = {base.facpob07.sum():,.0f} personas")
    chequear(f"Pobreza nacional (sumaria, factor07×mieperho) a ±{TOL_NACIONAL} pp de {cfg['pobreza']} %",
             abs(round(pob_hogares, 1) - cfg["pobreza"]) <= TOL_NACIONAL, f"{pob_hogares:.2f} %")
    chequear("Pobreza nacional (personas, facpob07), informativa", True, f"{pob_personas:.2f} %", esencial=False)
    chequear(f"Pobreza urbana a ±{TOL_AREA} pp de {cfg['urbano']} %", abs(urb - cfg["urbano"]) <= TOL_AREA, f"{urb:.2f} %", esencial=False)
    chequear(f"Pobreza rural a ±{TOL_AREA} pp de {cfg['rural']} %", abs(rur - cfg["rural"]) <= TOL_AREA, f"{rur:.2f} %", esencial=False)
    chequear("Pobreza extrema nacional, informativa", True, f"{ext:.2f} %", esencial=False)

    SALIDAS.mkdir(exist_ok=True)
    lineas = [f"Validación ENAHO {anio} (INEI, código {cod}) — generado por limpiar.py", ""]
    for nombre, ok, det, esencial in chequeos:
        marca = "APROBADA" if ok else ("FALLIDA " if esencial else "AVISO   ")
        lineas.append(f"[{marca}] {nombre}: {det}")
    fallidas = [c for c in chequeos if c[3] and not c[1]]
    lineas += ["", f"Resultado: {'TODAS LAS VALIDACIONES ESENCIALES APROBADAS' if not fallidas else f'{len(fallidas)} VALIDACIÓN(ES) ESENCIAL(ES) FALLIDA(S): PROCESO DETENIDO'}"]
    texto = "\n".join(lineas) + "\n"
    (SALIDAS / f"validacion_{anio}.txt").write_text(texto, encoding="utf-8")
    if anio == 2024:
        (SALIDAS / "validacion.txt").write_text(texto, encoding="utf-8")
    print(texto)
    if fallidas:
        sys.exit(1)

    # 7. Guardar
    cols = LLAVES + ["codperso", "anio", "ubigeo", "departamento", "dominio", "estrato", "urbano", "area",
                     "sexo", "edad", "grupo_edad", "pobreza", "pobre", "pobre_extremo", "facpob07", "factor07", "mieperho"]
    base[cols].to_parquet(SALIDAS / f"personas_{anio}.parquet", index=False)

    # Base de hogares (para estimaciones oficiales INEI: factor07 × mieperho)
    hog["departamento"] = hog.ubigeo.str[:2]
    hog["urbano"] = (hog.estrato <= 5).astype(int)
    hog["area"] = hog.urbano.map({1: "Urbana", 0: "Rural"})
    hog["pobre_extremo"] = (hog.pobreza == 1).astype(int)
    hog.assign(anio=anio).to_parquet(SALIDAS / f"hogares_{anio}.parquet", index=False)

    # Indicadores ponderados. Nacional, área y departamento: método oficial INEI (sumaria, factor07×mieperho),
    # que reproduce exactamente referencias/pobreza_departamento_2024.csv. Sexo y edad: personas con facpob07.
    def fila(nivel, grupo, g, var, peso, metodo):
        return (nivel, grupo, ponderada(g, var, peso), len(g), metodo)
    H, P = "hogares_factor07xmieperho", "personas_facpob07"
    filas = [fila("nacional", "Perú", hog, "pobre", "peso_personas", H),
             fila("nacional_extrema", "Perú", hog, "pobre_extremo", "peso_personas", H)]
    filas += [fila("area", a, g, "pobre", "peso_personas", H) for a, g in hog.groupby("area")]
    filas += [fila("departamento", d, g, "pobre", "peso_personas", H) for d, g in hog.groupby("departamento")]
    filas += [fila("sexo", x, g, "pobre", "facpob07", P) for x, g in base.groupby("sexo")]
    filas += [fila("grupo_edad", x, g, "pobre", "facpob07", P) for x, g in base.groupby("grupo_edad")]
    ind = pd.DataFrame(filas, columns=["nivel", "grupo", "pobreza_pct", "n_muestral", "metodo"]).assign(anio=anio)
    ind.to_csv(SALIDAS / f"indicadores_{anio}.csv", index=False, float_format="%.4f")
    print(f"Guardado: salidas/personas_{anio}.parquet ({len(base):,} personas) y salidas/indicadores_{anio}.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, default=2024, choices=sorted(ENCUESTAS))
    main(ap.parse_args().anio)
