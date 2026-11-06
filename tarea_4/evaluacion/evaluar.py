"""Ejecuta las 10 preguntas de evaluacion/preguntas.csv en dos modos, cada una en una sesión nueva de `claude -p`.

    uv run evaluacion/evaluar.py              # ambos modos
    uv run evaluacion/evaluar.py --modo B     # solo uno

Modo A (sin MCP ni Skills): carpeta temporal vacía, --strict-mcp-config sin servidores y Skill deshabilitada.
    No ve salidas/, datos/ ni el proyecto: no puede leer respuestas ya calculadas.
Modo B (con MCP y Skills): carpeta tarea_4/, servidor bcrp de .mcp.json y las skills de .claude/skills.
Ambos: mismo modelo, misma instrucción y lista explícita de herramientas permitidas (sin saltarse permisos):
    comunes: Read, Glob, Grep, WebFetch, WebSearch, Bash(python3:*), Bash(curl:*)
    solo B:  Skill, mcp__bcrp, Bash(uv run:*)  (lo que necesitan las skills y el servidor)
Las respuestas esperadas se congelaron (commit b9e07a8) antes de la primera ejecución.
"""
import argparse
import csv
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EV = RAIZ / "evaluacion"
MODELO = "claude-opus-5-5"
COMUNES = ["Read", "Glob", "Grep", "WebFetch", "WebSearch", "Bash(python3:*)", "Bash(curl:*)"]
SOLO_B = ["Skill", "mcp__bcrp", "Bash(uv run:*)"]
INSTRUCCION = ("Responde con datos oficiales verificables; no inventes cifras. Si no puedes obtener el dato, dilo. "
               "Termina SIEMPRE con una línea final exacta 'RESPUESTA: <número>' (solo el número pedido en último "
               "lugar, sin unidades). Si la pregunta pide además un departamento o una pobreza, agrega antes una "
               "línea 'DATO_ENAHO: <departamento o número>'.")
TIMEOUT = 900


def correr(pregunta, modo):
    args = ["claude", "-p", f"{pregunta}\n\n{INSTRUCCION}", "--model", MODELO,
            "--output-format", "stream-json", "--verbose", "--strict-mcp-config"]
    if modo == "A":
        cwd = tempfile.mkdtemp(prefix="eval_modoA_")
        args += ["--mcp-config", '{"mcpServers":{}}', "--disallowedTools", "Skill", "--allowedTools", *COMUNES]
    else:
        cwd = str(RAIZ)
        args += ["--mcp-config", str(RAIZ / ".mcp.json"), "--allowedTools", *COMUNES, *SOLO_B]
    t0 = time.time()
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
        salida, error = p.stdout, (p.stderr.strip()[-300:] if p.returncode else "")
    except subprocess.TimeoutExpired as e:
        salida = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        error = "timeout"
    seg = round(time.time() - t0, 1)
    texto, herramientas, denegadas = "", [], 0
    for linea in salida.splitlines():
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for b in ev["message"].get("content", []):
                if b.get("type") == "tool_use":
                    n = b["name"]
                    if n == "Skill":
                        n += ":" + str(b.get("input", {}).get("skill", ""))
                    herramientas.append(n)
        if ev.get("type") == "result":
            texto = ev.get("result", "") or ""
            denegadas = len(ev.get("permission_denials", []) or [])
    if denegadas:
        error = (error + f" {denegadas} herramienta(s) denegada(s)").strip()
    return texto, herramientas, seg, error, salida


def numero(texto, etiqueta):
    m = re.findall(rf"{etiqueta}:\s*\**\s*([-−]?[\d.,]+)", texto)
    if not m:
        return None
    try:
        return float(m[-1].replace("−", "-").replace(",", "").rstrip("."))
    except ValueError:
        return None


def calificar(fila, texto):
    v = numero(texto, "RESPUESTA")
    if v is None:
        return None, "sin respuesta numérica"
    ok = abs(v - float(fila["verdad"])) <= float(fila["tolerancia"])
    if fila["tipo"] != "Mixta":
        return v, "correcta" if ok else "incorrecta"
    dato = (re.findall(r"DATO_ENAHO:\s*(.+)", texto) or [""])[-1].lower()
    enaho_ok = ("cajamarca" in dato) if fila["id"] == "mixta_caj" else bool(re.search(r"18[.,]5", dato))
    if ok and enaho_ok:
        return v, "correcta"
    fallas = [x for x, bien in (("dato BCRP", ok), ("dato ENAHO", enaho_ok)) if not bien]
    return v, f"incorrecta ({' y '.join(fallas)})"


def fuente(herr):
    partes = [n for n, c in (("MCP bcrp", any(h.startswith("mcp__bcrp") for h in herr)),
                             ("Skills", any(h.startswith("Skill") for h in herr))) if c]
    if partes:
        return " + ".join(partes)
    if any(h in ("WebFetch", "WebSearch") for h in herr):
        return "web"
    return "bash/archivos" if herr else "ninguna (conocimiento del modelo)"


def main(modos, ids):
    preguntas = [q for q in csv.DictReader(open(EV / "preguntas.csv", encoding="utf-8")) if not ids or q["id"] in ids]
    destino = EV / "resultados.csv"
    previas = list(csv.DictReader(open(destino, encoding="utf-8"))) if destino.exists() else []
    hechas = {(m, q["id"]) for m in modos for q in preguntas}
    previas = [r for r in previas if (r["modo"], r["id"]) not in hechas]
    log = RAIZ / "evidencias_ia" / "evaluacion"
    log.mkdir(parents=True, exist_ok=True)
    filas = []
    for modo in modos:
        for q in preguntas:
            print(f"[modo {modo}] {q['id']} ...", flush=True)
            texto, herr, seg, err, crudo = correr(q["pregunta"], modo)
            (log / f"{modo}_{q['id']}.jsonl").write_text(crudo, encoding="utf-8")
            v, nota = calificar(q, texto)
            filas.append({"modo": modo, "id": q["id"], "tipo": q["tipo"], "pregunta": q["pregunta"],
                          "verdad": q["verdad"], "tolerancia": q["tolerancia"], "respuesta_num": v,
                          "respuesta_texto": texto.strip().replace("\n", " ")[-600:], "fuente": fuente(herr),
                          "herramientas": ";".join(dict.fromkeys(herr)), "n_llamadas": len(herr),
                          "segundos": seg, "resultado": nota, "error": err})
            print(f"   -> {v} ({nota}) en {seg}s; {fuente(herr)}; {err}", flush=True)
            todas = previas + filas  # guarda después de cada pregunta
            with open(destino, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(todas[0].keys()))
                w.writeheader(); w.writerows(sorted(todas, key=lambda r: (r["modo"], r["id"])))
    print(f"Guardado {destino}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["A", "B"])
    ap.add_argument("--ids", nargs="*", help="solo estas preguntas")
    a = ap.parse_args()
    main([a.modo] if a.modo else ["A", "B"], a.ids)
