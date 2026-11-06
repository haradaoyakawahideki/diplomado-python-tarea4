"""Cruza paneles departamentales del BCRP (salidas/bcrp_*.csv) con la pobreza ENAHO 2019 y 2024.

    uv run .claude/skills/cruzando-bcrp-enaho/scripts/cruzar.py [--desde 2019 --hasta 2024]
Descriptivo: correlaciones de Spearman y terciles; no estima efectos causales.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path.cwd()
SAL, FIG = RAIZ / "salidas", RAIZ / "figuras"
GEO = RAIZ / "referencias" / "peru_departamental_simple.geojson"
INDICADORES = {"igv": "IGV interno recaudado", "credito": "Crédito al sector privado",
               "inversion_regional": "Inversión del gobierno regional"}
AZUL, GRIS = "#2b5c8a", "#9aa5b1"


def leer(p, msg):
    if not p.exists():
        sys.exit(f"ERROR: falta {p.relative_to(RAIZ)}. {msg}")
    return pd.read_csv(p, dtype={"ccdd": str, "grupo": str})


def main(desde, hasta):
    pob = {}
    for a in (desde, hasta):
        i = leer(SAL / f"indicadores_{a}.csv", f"Corre la skill limpiando-enaho --anio {a}.")
        pob[a] = i.query("nivel == 'departamento'").set_index("grupo").pobreza_pct
    nombres = {f["properties"]["FIRST_IDDP"]: f["properties"]["NOMBDEP"].title()
               for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]}
    df = pd.DataFrame({f"pobreza_{desde}": pob[desde], f"pobreza_{hasta}": pob[hasta]})
    df.index.name = "ccdd"
    df["cambio_pobreza_pp"] = df[f"pobreza_{hasta}"] - df[f"pobreza_{desde}"]
    paneles = {}
    for k in INDICADORES:
        b = leer(SAL / f"bcrp_{k}_{desde}_{hasta}.csv", f"Usa la herramienta MCP panel_departamental('{k}').")
        paneles[k] = b.set_index("ccdd")
        df[f"indice_{k}"] = paneles[k]["indice"]
    if len(df) != 25 or df.isna().any().any():
        sys.exit(f"ERROR: la unión por ccdd no dio 25 departamentos completos:\n{df[df.isna().any(axis=1)]}")
    df.insert(0, "departamento", df.index.map(nombres))
    df["tercil_pobreza_" + str(desde)] = pd.qcut(df[f"pobreza_{desde}"], 3, labels=["menos pobre", "medio", "más pobre"])
    df.round(3).to_csv(SAL / "cruce_departamental.csv")

    # Correlaciones de Spearman (rangos) y medianas por tercil
    lineas = [f"Cruce BCRP × ENAHO por departamento (n = {len(df)}), {desde}-{hasta}. Descriptivo, no causal.", ""]
    x = df[f"pobreza_{desde}"]
    for k, nombre in INDICADORES.items():
        y = df[f"indice_{k}"]
        rho = x.rank().corr(y.rank())
        lineas.append(f"Spearman pobreza {desde} vs índice real {nombre} ({hasta}/{desde}×100): rho = {rho:+.2f}")
    rho_p = x.rank().corr(df.cambio_pobreza_pp.rank())
    lineas.append(f"Spearman pobreza {desde} vs cambio de pobreza {desde}-{hasta} (pp): rho = {rho_p:+.2f}")
    lineas += ["", "Medianas por tercil de pobreza " + str(desde) + ":"]
    cols = [f"pobreza_{desde}", f"pobreza_{hasta}", "cambio_pobreza_pp"] + [f"indice_{k}" for k in INDICADORES]
    med = df.groupby("tercil_pobreza_" + str(desde), observed=True)[cols].median().round(1)
    lineas.append(med.to_string())
    lineas += ["", "Índices: 100 = mismo nivel real que en " + str(desde) + "; deflactor IPC Lima PN38705PM (promedio anual).",
               "Con n = 25, |rho| < 0.40 no es distinguible de cero al 5 % (valor crítico aprox. 0.40)."]
    txt = "\n".join(lineas) + "\n"
    (SAL / "cruce_resumen.txt").write_text(txt, encoding="utf-8"); print(txt)

    # Figura BCRP: evolución nacional real (suma de departamentos), 2019 = 100
    FIG.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    anios = [c for c in paneles["igv"].columns if c.isdigit()]
    for (k, nombre), color, ls in zip(INDICADORES.items(), [AZUL, "#c05a2b", "#5a8a3a"], ["-", "--", ":"]):
        tot = paneles[k][anios].sum()
        serie = 100 * tot / tot[str(desde)]
        ax.plot([int(a) for a in anios], serie.values, color=color, ls=ls, marker="o", lw=2, label=nombre)
        ax.annotate(f"{serie.iloc[-1]:.0f}", (int(anios[-1]), serie.iloc[-1]), xytext=(5, 0),
                    textcoords="offset points", va="center", color=color, fontsize=9)
    ax.axhline(100, color=GRIS, lw=0.8)
    ax.axvspan(2019.6, 2020.4, color="#eee", zorder=0); ax.text(2020, ax.get_ylim()[0], " 2020", fontsize=8, color="#777", va="bottom")
    ax.set_ylabel(f"Índice real ({desde} = 100)"); ax.set_xticks([int(a) for a in anios])
    ax.set_title(f"Recaudación de IGV, crédito e inversión regional en términos reales, Perú {desde}-{hasta}",
                 loc="left", fontsize=11, fontweight="bold", pad=20)
    ax.text(0, 1.01, f"Suma de los 25 departamentos, soles de {desde} (deflactado con IPC Lima)",
            transform=ax.transAxes, fontsize=9, color="#444")
    ax.legend(frameon=False, fontsize=9); ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, -0.02, "Fuente: BCRP, series regionales anuales (IGV RD16447DA-RD16472DA, crédito RD16125DA ss., "
             "inversión regional RD16709DA-RD16734DA) e IPC PN38705PM.", fontsize=7, color="#555")
    fig.savefig(FIG / "bcrp_recuperacion_real.png", dpi=200, bbox_inches="tight"); plt.close(fig)

    # Dispersión: pobreza 2019 vs índice de recuperación (un panel por indicador)
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.6), sharex=True)
    for ax, (k, nombre) in zip(axs, INDICADORES.items()):
        ax.scatter(x, df[f"indice_{k}"], color=AZUL, s=22)
        for c, r in df.iterrows():
            ax.annotate(r.departamento, (r[f"pobreza_{desde}"], r[f"indice_{k}"]), fontsize=6, xytext=(2, 2),
                        textcoords="offset points", color="#444")
        ax.axhline(100, color=GRIS, lw=0.8, ls="--")
        rho = x.rank().corr(df[f"indice_{k}"].rank())
        ax.set_title(f"{nombre}\nSpearman rho = {rho:+.2f}", fontsize=10, loc="left")
        ax.set_xlabel(f"Pobreza monetaria {desde} (% personas)")
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].set_ylabel(f"Índice real {hasta} ({desde} = 100)")
    fig.suptitle(f"¿Se recuperaron menos los departamentos más pobres en {desde}? Pobreza {desde} frente a "
                 f"indicadores reales {hasta}", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.text(0.01, -0.03, f"Fuente: INEI, ENAHO {desde} (factor07 × mieperho); BCRP, series regionales deflactadas con "
             "IPC Lima. Cada punto es un departamento (n = 25). Asociación descriptiva, no causal.", fontsize=7, color="#555")
    fig.tight_layout()
    fig.savefig(FIG / "cruce_pobreza2019_recuperacion.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    print("Guardado: salidas/cruce_departamental.csv, salidas/cruce_resumen.txt, "
          "figuras/bcrp_recuperacion_real.png, figuras/cruce_pobreza2019_recuperacion.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--desde", type=int, default=2019)
    ap.add_argument("--hasta", type=int, default=2024); a = ap.parse_args(); main(a.desde, a.hasta)
