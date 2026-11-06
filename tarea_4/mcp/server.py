"""Servidor MCP del BCRP. Empiecen aquí: buscar_series ya funciona; completen los TODO hasta que pasen las pruebas.

    uv run pytest                                           # el contrato: las 8 pruebas deben pasar
    uv run server.py                                        # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run server.py # conectarlo a Claude Code

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, y serie para los datos. No calcules a mano: "
    "cita siempre el código de la serie y el periodo."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7, "Ago": 8,
         "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}


def _fecha_api(fecha, frecuencia):
    """Convierte '2025-01', '2025-01-15' o '2025' al formato que pide la API según la frecuencia."""
    partes = str(fecha).replace("/", "-").split("-")
    f = frecuencia.lower()
    if f == "anual":
        return partes[0]
    if f == "diaria":
        if len(partes) < 3:
            raise ToolError(f"La serie es diaria: usen fechas AAAA-MM-DD, no {fecha!r}.")
        return f"{partes[0]}-{int(partes[1]):02d}-{int(partes[2]):02d}"
    if len(partes) < 2:  # mensual o trimestral pedida con solo el año
        return f"{partes[0]}-1"
    p2 = partes[1].upper().lstrip("T")
    return f"{partes[0]}-{int(p2)}"


def _periodo(nombre, frecuencia):
    """'Ene.2025' -> '2025-01'; '01.Oct.26' -> '2026-10-01'; 'T1.25' -> '2025-T1'; '2025' -> '2025'."""
    f = frecuencia.lower()
    if f == "anual":
        return nombre
    if f == "trimestral":
        t, a = nombre.split(".")
        return f"{2000 + int(a) if len(a) == 2 else a}-{t.upper()}"
    if f == "diaria":
        d, m, a = nombre.split(".")
        return f"{2000 + int(a) if len(a) == 2 else a}-{MESES[m[:3].title()]:02d}-{int(d):02d}"
    m, a = nombre.split(".")
    return f"{a}-{MESES[m[:3].title()]:02d}"


@cache
def _descargar(codigo, desde, hasta):
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for intento in range(4):
        r = httpx.get(url, timeout=60, follow_redirects=True)
        try:
            return url, r.json()
        except ValueError:  # la API devolvió HTML: demasiados pedidos seguidos
            time.sleep(2 * (intento + 1))
    raise ToolError(f"La API del BCRP no devolvió datos para {codigo} ({desde} a {hasta}). Reintenten más tarde.")


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Descarga los datos oficiales de una serie del BCRP entre dos fechas.

    Fechas: "2025-01" (mensual), "2025-1" o "2025-T1" (trimestral), "2025-01-15" (diaria), "2025" (anual).
    Devuelve codigo, nombre, frecuencia, datos [{"periodo", "valor"}] y la URL fuente. Salta los "n.d.".
    """
    ficha = _ficha(codigo)
    fr = ficha["frecuencia"]
    url, j = _descargar(codigo, _fecha_api(desde, fr), _fecha_api(hasta, fr))
    datos = []
    for p in j.get("periods", []):
        v = p["values"][0]
        try:
            datos.append({"periodo": _periodo(p["name"], fr), "valor": float(v)})
        except (ValueError, TypeError):
            continue  # "n.d."
    if not datos:
        raise ToolError(f"La serie {codigo} no tiene datos entre {desde} y {hasta}.")
    return {"codigo": codigo, "nombre": ficha["nombre"], "frecuencia": fr, "datos": datos, "fuente": url}


def _estadisticas(datos):
    s = pd.DataFrame(datos)
    imax, imin = s.valor.idxmax(), s.valor.idxmin()
    primero, ultimo = s.iloc[0], s.iloc[-1]
    cambio = ultimo.valor - primero.valor
    return {
        "n": len(s),
        "primero": {"periodo": primero.periodo, "valor": primero.valor},
        "ultimo": {"periodo": ultimo.periodo, "valor": ultimo.valor},
        "cambio": round(cambio, 6),
        "variacion_pct": round(100 * cambio / primero.valor, 4) if primero.valor else None,
        "promedio": round(s.valor.mean(), 6),
        "maximo": {"periodo": s.periodo[imax], "valor": s.valor[imax]},
        "minimo": {"periodo": s.periodo[imin], "valor": s.valor[imin]},
    }


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Resume una serie del BCRP entre dos fechas: primero, ultimo, cambio, variacion_pct, promedio,
    maximo y minimo (con su periodo). Úsenla en lugar de hacer cuentas a mano. Mismas fechas que `serie`.
    """
    s = serie(codigo, desde, hasta)
    return {"codigo": codigo, "nombre": s["nombre"], "frecuencia": s["frecuencia"], "desde": desde,
            "hasta": hasta, **_estadisticas(s["datos"]), "fuente": s["fuente"]}


@mcp.tool(annotations=SOLO_LECTURA)
def comparar_periodos(codigo: str, desde_a: str, hasta_a: str, desde_b: str, hasta_b: str) -> dict:
    """Compara una misma serie del BCRP en dos intervalos (A = base, B = comparación), p. ej. antes y
    después de la pandemia: 2017-2019 frente a 2022-2024.

    Para cada intervalo da n, promedio, suma, primero, ultimo, maximo y minimo. Además:
    - diferencia_promedio = promedio B − promedio A, y variacion_promedio_pct = 100·(B/A − 1)
    - variacion_suma_pct: compara totales (útil en flujos anuales como recaudación o inversión)
    - indice_b_sobre_a = 100·promedio B / promedio A (100 = mismo nivel)
    Los valores son nominales si la serie lo es: para soles corrientes, comparen con la inflación (IPC).
    Los intervalos no pueden solaparse.
    """
    a, b = serie(codigo, desde_a, hasta_a), serie(codigo, desde_b, hasta_b)
    pa = {d["periodo"] for d in a["datos"]}
    if pa & {d["periodo"] for d in b["datos"]}:
        raise ToolError("Los intervalos A y B se solapan; elijan periodos distintos.")

    def bloque(s, desde, hasta):
        e = _estadisticas(s["datos"])
        return {"desde": desde, "hasta": hasta, "suma": round(sum(d["valor"] for d in s["datos"]), 6), **e}

    A, B = bloque(a, desde_a, hasta_a), bloque(b, desde_b, hasta_b)
    return {
        "codigo": codigo, "nombre": a["nombre"], "frecuencia": a["frecuencia"], "a": A, "b": B,
        "diferencia_promedio": round(B["promedio"] - A["promedio"], 6),
        "variacion_promedio_pct": round(100 * (B["promedio"] / A["promedio"] - 1), 4) if A["promedio"] else None,
        "variacion_suma_pct": round(100 * (B["suma"] / A["suma"] - 1), 4) if A["suma"] else None,
        "indice_b_sobre_a": round(100 * B["promedio"] / A["promedio"], 4) if A["promedio"] else None,
        "fuentes": [a["fuente"], b["fuente"]],
    }


# --- Panel departamental: una serie anual por departamento, con código ubigeo de la ENAHO ---
DEPARTAMENTOS = {"amazonas": "01", "ancash": "02", "apurimac": "03", "arequipa": "04", "ayacucho": "05",
                 "cajamarca": "06", "callao": "07", "cusco": "08", "huancavelica": "09", "huanuco": "10",
                 "ica": "11", "junin": "12", "la libertad": "13", "lambayeque": "14", "lima": "15",
                 "lima metropolitana": "15", "lima provincias": "15", "municipalidad metropolitana de lima": "15",
                 "loreto": "16", "madre de dios": "17", "moquegua": "18", "pasco": "19", "piura": "20",
                 "puno": "21", "san martin": "22", "tacna": "23", "tumbes": "24", "ucayali": "25"}
PANELES = {  # grupo del catálogo y filtro del nombre; todos anuales en millones de soles corrientes
    "igv": ("Impuesto General a las Ventas interno según departamento", "(millones de soles)"),
    "credito": ("Crédito directo del sistema financiero al sector privado por departamentos", "(total)"),
    "inversion_regional": ("Inversión bruta fija de los gobiernos regionales", "(millones de soles)"),
}
IPC = "PN38705PM"  # IPC Lima Metropolitana, índice Dic.2021 = 100 (mensual)
SALIDAS = AQUI.parent / "salidas"


def _ipc_anual(desde, hasta):
    d = pd.DataFrame(serie(IPC, f"{desde}-01", f"{hasta}-12")["datos"])
    d["anio"] = d.periodo.str[:4]
    return d.groupby("anio").valor.mean()


@mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
def panel_departamental(indicador: str, desde: int = 2019, hasta: int = 2024, real: bool = True) -> dict:
    """Descarga de una vez una serie anual del BCRP para los 25 departamentos y la guarda en
    salidas/bcrp_<indicador>_<desde>_<hasta>.csv con el código de departamento de la ENAHO (ccdd = ubigeo[:2]).

    indicador: "igv" (IGV interno recaudado por SUNAT), "credito" (crédito directo al sector privado, saldo a fin de
    año) o "inversion_regional" (inversión bruta fija del gobierno regional; para Lima suma la Municipalidad
    Metropolitana). Lima Metropolitana + Lima provincias se suman en ccdd 15. Excluye la fila "Total".
    real=True deflacta con el promedio anual del IPC de Lima (PN38705PM) a soles del año `desde`.
    Devuelve, por departamento, el valor de `desde` y `hasta` y el índice hasta/desde × 100 (100 = mismo nivel).
    """
    if indicador not in PANELES:
        raise ToolError(f"Indicador {indicador!r} no disponible. Opciones: {sorted(PANELES)}")
    grupo, filtro = PANELES[indicador]
    cat = catalogo()
    sel = cat[cat.grupo.str.contains(grupo, regex=False) & (cat.frecuencia == "Anual") & cat.nombre.str.contains(filtro, regex=False)]
    if sel.empty:
        raise ToolError(f"No encontré series anuales del grupo {grupo!r} en el catálogo del BCRP.")
    filas, codigos = [], []
    for _, f in sel.iterrows():
        nombre = _sin_tildes(f.nombre.split("(")[0]).strip()
        if nombre == "total":
            continue
        if nombre not in DEPARTAMENTOS:
            raise ToolError(f"No sé a qué departamento corresponde la serie {f.codigo} ({f.nombre}).")
        for d in serie(f.codigo, str(desde), str(hasta))["datos"]:
            filas.append({"ccdd": DEPARTAMENTOS[nombre], "anio": d["periodo"], "valor": d["valor"]})
        codigos.append(f.codigo)
    df = pd.DataFrame(filas).groupby(["ccdd", "anio"], as_index=False).valor.sum()
    if df.ccdd.nunique() != 25:
        raise ToolError(f"El panel de {indicador} tiene {df.ccdd.nunique()} departamentos, no 25.")
    if real:
        ipc = _ipc_anual(desde, hasta)
        df["valor"] = df.valor * ipc[str(desde)] / df.anio.map(ipc)
    ancho = df.pivot(index="ccdd", columns="anio", values="valor")
    ancho["indice"] = 100 * ancho[str(hasta)] / ancho[str(desde)]
    SALIDAS.mkdir(exist_ok=True)
    ruta = SALIDAS / f"bcrp_{indicador}_{desde}_{hasta}.csv"
    ancho.round(4).to_csv(ruta)
    unidad = f"millones de soles de {desde}" if real else "millones de soles corrientes"
    return {"indicador": indicador, "grupo": grupo, "unidad": unidad, "codigos": codigos,
            "deflactor": IPC if real else None, "archivo": str(ruta.relative_to(AQUI.parent)),
            "departamentos": [{"ccdd": c, "desde": round(r[str(desde)], 2), "hasta": round(r[str(hasta)], 2),
                               "indice": round(r.indice, 2)} for c, r in ancho.iterrows()],
            "fuente": f"{API}/<codigo>/json/{desde}/{hasta}"}


@mcp.resource("bcrp://serie/{codigo}", mime_type="application/json")
def ficha_serie(codigo: str) -> dict:
    """Ficha descriptiva de una serie del BCRP: nombre, categoría, frecuencia, inicio, unidad y última actualización."""
    f = _ficha(codigo)
    fila = catalogo().query("codigo == @codigo").iloc[0]
    return {**f, "unidad": fila.get("Unidad de medida", ""), "descripcion": fila.get("Descripción de la serie", ""),
            "url": f"https://estadisticas.bcrp.gob.pe/estadisticas/series/consulta/{codigo}"}


@mcp.prompt
def informe(tema: str, desde: str = "2019", hasta: str = "2024") -> str:
    """Plantilla para redactar un informe breve sobre un indicador del BCRP, citando código y periodo."""
    return (f"Redacta un informe breve sobre «{tema}» entre {desde} y {hasta} con datos oficiales del BCRP.\n"
            "1. Usa buscar_series para hallar el código; 2. usa resumen o comparar_periodos para las cifras;\n"
            "3. cada cifra debe citar código de serie, periodo y la URL fuente devuelta por la herramienta;\n"
            "4. no calcules a mano ni inventes valores: si una herramienta falla, dilo;\n"
            "5. describe asociaciones, no causas, y menciona si los valores son nominales.")


if __name__ == "__main__":
    mcp.run()
