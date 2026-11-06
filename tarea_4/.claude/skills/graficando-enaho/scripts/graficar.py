"""Gráficos de pobreza monetaria ENAHO a partir de salidas/indicadores_<año>.csv (ya ponderados).

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo area --anio 2024
    tipos: area | sexo | edad | departamento | cambio (departamentos 2019 -> 2024)
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "DejaVu Sans"

RAIZ = Path.cwd()
SAL, FIG = RAIZ / "salidas", RAIZ / "figuras"
GEO = RAIZ / "referencias" / "peru_departamental_simple.geojson"
AZUL, GRIS = "#2b5c8a", "#9aa5b1"


def nombres():
    g = json.loads(GEO.read_text(encoding="utf-8"))
    return {f["properties"]["FIRST_IDDP"]: f["properties"]["NOMBDEP"].title() for f in g["features"]}


def indicadores(anio):
    p = SAL / f"indicadores_{anio}.csv"
    if not p.exists():
        sys.exit(f"ERROR: no existe {p}. Corre primero la skill limpiando-enaho --anio {anio}.")
    return pd.read_csv(p, dtype={"grupo": str})


def nacional(ind):
    return float(ind.query("nivel == 'nacional'").pobreza_pct.iloc[0])


def pie(ax, anio, extra=""):
    ax.figure.text(0.01, 0.01, f"Fuente: INEI, ENAHO {anio}, módulos 34 y 02. Estimaciones ponderadas{extra}.",
                   fontsize=8, color="#555")


def barras(df, titulo, subtitulo, anio, nac, salida, horizontal=False, extra=""):
    fig, ax = plt.subplots(figsize=(8, 7 if horizontal else 4.8))
    if horizontal:
        df = df.sort_values("pobreza_pct")
        b = ax.barh(df.etiqueta, df.pobreza_pct, color=AZUL)
        ax.bar_label(b, fmt="%.1f", padding=3, fontsize=8)
        ax.axvline(nac, color=GRIS, ls="--", lw=1)
        ax.text(nac, len(df) - 0.4, f" Perú {nac:.1f} %", color="#555", fontsize=8)
        ax.set_xlabel("% de personas en pobreza monetaria"); ax.set_xlim(0, df.pobreza_pct.max() * 1.15)
    else:
        df = df.sort_values("pobreza_pct", ascending=False)
        b = ax.bar(df.etiqueta, df.pobreza_pct, color=AZUL, width=0.6)
        ax.bar_label(b, fmt="%.1f %%", padding=3)
        ax.axhline(nac, color=GRIS, ls="--", lw=1)
        ax.text(len(df) - 0.5, nac, f"Perú {nac:.1f} %", color="#555", fontsize=8, ha="right", va="bottom")
        ax.set_ylabel("% de personas en pobreza monetaria"); ax.set_ylim(0, df.pobreza_pct.max() * 1.18)
    ax.set_title(titulo, loc="left", fontsize=12, fontweight="bold", pad=20)
    ax.text(0, 1.01, subtitulo, transform=ax.transAxes, fontsize=9, color="#444")
    ax.spines[["top", "right"]].set_visible(False)
    fig.subplots_adjust(top=0.86, bottom=0.12)
    pie(ax, anio, extra)
    FIG.mkdir(exist_ok=True)
    fig.savefig(salida, dpi=200, bbox_inches="tight"); plt.close(fig)
    print(df[["etiqueta", "pobreza_pct"]].round(1).to_string(index=False)); print(f"Guardado: {salida}")


def main(tipo, anio):
    if tipo == "cambio":
        return cambio()
    ind = indicadores(anio); nac = nacional(ind)
    nivel = {"area": "area", "sexo": "sexo", "edad": "grupo_edad", "departamento": "departamento"}[tipo]
    df = ind.query("nivel == @nivel").assign(etiqueta=lambda d: d.grupo)
    if tipo == "departamento":
        df["etiqueta"] = df.grupo.map(nombres())
    if tipo == "edad":
        df = df.assign(orden=df.grupo.str.extract(r"(\d+)").astype(int)).sort_values("orden")
    hi, lo = df.loc[df.pobreza_pct.idxmax()], df.loc[df.pobreza_pct.idxmin()]
    titulos = {
        "area": lambda: f"En {anio}, la pobreza rural ({df.set_index('grupo').pobreza_pct['Rural']:.1f} %) superó a la urbana ({df.set_index('grupo').pobreza_pct['Urbana']:.1f} %)",
        "sexo": lambda: f"Pobreza monetaria por sexo, Perú {anio}: brecha de {abs(df.pobreza_pct.iloc[0] - df.pobreza_pct.iloc[1]):.1f} pp",
        "edad": lambda: f"Pobreza monetaria por grupo de edad, Perú {anio}: más alta en {hi.grupo} años",
        "departamento": lambda: f"Pobreza monetaria por departamento, {anio}: de {lo.pobreza_pct:.1f} % ({lo.etiqueta}) a {hi.pobreza_pct:.1f} % ({hi.etiqueta})",
    }
    subt = {"area": "% de personas pobres; urbano = estrato 1-5, rural = estrato 6-8",
            "sexo": "% de personas pobres; residentes habituales, ponderado con facpob07",
            "edad": "% de personas pobres; residentes habituales, ponderado con facpob07",
            "departamento": "% de personas pobres; Lima (15) y Callao (07) por separado; línea = promedio nacional"}
    extra = " (factor07 × mieperho)" if tipo in ("area", "departamento") else " (facpob07)"
    if tipo == "edad":
        df = df.set_index("orden").sort_index().reset_index()
        return barras_ordenadas(df, titulos[tipo](), subt[tipo], anio, nac, FIG / f"pobreza_edad_{anio}.png", extra)
    barras(df, titulos[tipo](), subt[tipo], anio, nac, FIG / f"pobreza_{tipo}_{anio}.png", tipo == "departamento", extra)


def barras_ordenadas(df, titulo, subtitulo, anio, nac, salida, extra):
    """Edad: el eje es ordinal, así que se mantiene el orden de los grupos en vez de ordenar por valor."""
    fig, ax = plt.subplots(figsize=(8, 4.8))
    b = ax.bar(df.etiqueta, df.pobreza_pct, color=AZUL, width=0.6)
    ax.bar_label(b, fmt="%.1f %%", padding=3)
    ax.axhline(nac, color=GRIS, ls="--", lw=1)
    ax.set_ylabel("% de personas en pobreza monetaria"); ax.set_xlabel("Edad (años)")
    ax.set_ylim(0, df.pobreza_pct.max() * 1.18)
    ax.set_title(titulo, loc="left", fontsize=12, fontweight="bold", pad=20)
    ax.text(0, 1.01, subtitulo, transform=ax.transAxes, fontsize=9, color="#444")
    ax.spines[["top", "right"]].set_visible(False)
    pie(ax, anio, extra); FIG.mkdir(exist_ok=True)
    fig.savefig(salida, dpi=200, bbox_inches="tight"); plt.close(fig)
    print(df[["etiqueta", "pobreza_pct"]].round(1).to_string(index=False)); print(f"Guardado: {salida}")


def cambio():
    a = indicadores(2019).query("nivel == 'departamento'").set_index("grupo").pobreza_pct
    b = indicadores(2024).query("nivel == 'departamento'").set_index("grupo").pobreza_pct
    df = pd.DataFrame({"p2019": a, "p2024": b}).assign(cambio=lambda d: d.p2024 - d.p2019)
    df["etiqueta"] = df.index.map(nombres())
    df = df.sort_values("cambio")
    fig, ax = plt.subplots(figsize=(8, 7.5))
    bb = ax.barh(df.etiqueta, df.cambio, color=[AZUL if v > 0 else GRIS for v in df.cambio])
    ax.bar_label(bb, fmt="%+.1f", padding=3, fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    nac = nacional(indicadores(2024)) - nacional(indicadores(2019))
    ax.set_xlabel("Cambio en la pobreza monetaria 2019→2024 (puntos porcentuales)")
    ax.set_title(f"La pobreza subió {nac:+.1f} pp en el Perú entre 2019 y 2024, con grandes diferencias regionales",
                 loc="left", fontsize=11, fontweight="bold", pad=20)
    ax.text(0, 1.01, "Diferencia en % de personas pobres por departamento; azul = aumento",
            transform=ax.transAxes, fontsize=9, color="#444")
    ax.spines[["top", "right"]].set_visible(False)
    ax.figure.text(0.01, 0.01, "Fuente: INEI, ENAHO 2019 y 2024, módulo 34. Ponderado con factor07 × mieperho.",
                   fontsize=8, color="#555")
    FIG.mkdir(exist_ok=True); out = FIG / "pobreza_cambio_2019_2024.png"
    fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig)
    df.round(2).to_csv(SAL / "pobreza_departamento_2019_2024.csv", index_label="ccdd")
    print(df.round(1).to_string()); print(f"Guardado: {out} y salidas/pobreza_departamento_2019_2024.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tipo", required=True, choices=["area", "sexo", "edad", "departamento", "cambio"])
    ap.add_argument("--anio", type=int, default=2024)
    a = ap.parse_args(); main(a.tipo, a.anio)
