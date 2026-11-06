"""Mapa coroplético de pobreza monetaria por departamento (ENAHO), unido por código ubigeo.

    uv run .claude/skills/mapeando-enaho/scripts/mapear.py --anio 2024
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "DejaVu Sans"

RAIZ = Path.cwd()
SAL, MAP = RAIZ / "salidas", RAIZ / "mapas"
GEO = RAIZ / "referencias" / "peru_departamental_simple.geojson"
REF = RAIZ / "referencias" / "pobreza_departamento_2024.csv"


def main(anio):
    p = SAL / f"indicadores_{anio}.csv"
    if not p.exists():
        sys.exit(f"ERROR: no existe {p}. Corre primero la skill limpiando-enaho --anio {anio}.")
    ind = pd.read_csv(p, dtype={"grupo": str}).query("nivel == 'departamento'")
    ind = ind.rename(columns={"grupo": "ccdd"})[["ccdd", "pobreza_pct", "n_muestral"]]
    geo = gpd.read_file(GEO)
    geo["FIRST_IDDP"] = geo.FIRST_IDDP.astype(str).str.zfill(2)

    # Unión por código oficial, nunca por nombre
    m = geo.merge(ind, left_on="FIRST_IDDP", right_on="ccdd", how="left", validate="1:1")
    errores = []
    if len(m) != 25: errores.append(f"el mapa tiene {len(m)} unidades, no 25")
    if m.pobreza_pct.isna().any(): errores.append(f"sin dato: {m.loc[m.pobreza_pct.isna(), 'NOMBDEP'].tolist()}")
    if not {"07", "15"} <= set(m.FIRST_IDDP): errores.append("Lima (15) y Callao (07) no están separados")
    if errores:
        sys.exit("ERROR en la unión territorial: " + "; ".join(errores))

    fig, ax = plt.subplots(figsize=(7, 9))
    m.plot(column="pobreza_pct", cmap="Blues", vmin=0, vmax=50, edgecolor="white", linewidth=0.5, ax=ax,
           legend=True, legend_kwds={"label": "% de personas en pobreza monetaria", "shrink": 0.6})
    for _, f in m.iterrows():
        c = f.geometry.representative_point()
        ax.annotate(f"{f.pobreza_pct:.0f}", (c.x, c.y), ha="center", fontsize=6.5,
                    color="white" if f.pobreza_pct > 30 else "#222")
    hi, lo = m.loc[m.pobreza_pct.idxmax()], m.loc[m.pobreza_pct.idxmin()]
    ax.set_title(f"Pobreza monetaria por departamento, Perú {anio}\n"
                 f"de {lo.pobreza_pct:.1f} % en {lo.NOMBDEP.title()} a {hi.pobreza_pct:.1f} % en {hi.NOMBDEP.title()}",
                 loc="left", fontsize=11, fontweight="bold")
    ax.set_axis_off()
    fig.text(0.02, 0.02, f"Fuente: INEI, ENAHO {anio}, módulo 34 (factor07 × mieperho). Límites: repositorio del curso.\n"
             "25 departamentos; Lima y Callao por separado. Unión ubigeo[:2] = FIRST_IDDP.", fontsize=7, color="#555")
    MAP.mkdir(exist_ok=True); out = MAP / f"pobreza_departamento_{anio}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig)
    print(f"Guardado: {out} (25/25 departamentos con dato)")

    if anio == 2024 and REF.exists():
        r = pd.read_csv(REF, dtype={"ccdd": str})
        c = r.merge(ind, on="ccdd", suffixes=("_ref", "_calc"))
        c["dif"] = (c.pobreza_pct_calc.round(1) - c.pobreza_pct_ref).round(2)
        txt = (f"Comparación con referencias/pobreza_departamento_2024.csv (Sesión 16)\n"
               f"Departamentos comparados: {len(c)}/25; coinciden (redondeo a 0.1): {(c.dif == 0).sum()}; "
               f"diferencia máxima: {c.dif.abs().max():.2f} pp\n\n" + c.round(2).to_string(index=False) + "\n")
        (SAL / "comparacion_mapa_2024.txt").write_text(txt, encoding="utf-8"); print(txt.splitlines()[1])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--anio", type=int, default=2024)
    main(ap.parse_args().anio)
