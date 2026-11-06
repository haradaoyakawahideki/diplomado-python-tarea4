# Comparación: Claude Code sin y con MCP/Skills

**Diseño.** 10 preguntas (4 BCRP, 4 ENAHO, 2 mixtas) con respuesta esperada y tolerancia fijadas antes de ejecutar
(commit `b9e07a8`). Las respuestas esperadas vienen de la API del BCRP consultada directamente (sin el servidor
MCP), de los informes técnicos del INEI y de la referencia de la Sesión 16. Cada pregunta corrió en una sesión nueva
de `claude -p` (modelo `claude-opus-5-5`, misma instrucción) con [`evaluar.py`](evaluar.py). Registros completos:
[`evidencias_ia/evaluacion/`](../evidencias_ia/evaluacion/).

| | Modo A: sin MCP ni Skills | Modo B: con MCP y Skills |
|---|---|---|
| Carpeta | temporal vacía (no ve `salidas/` ni `datos/`) | `tarea_4/` |
| MCP | ninguno (`--strict-mcp-config` vacío) | `bcrp` |
| Skills | deshabilitadas (`--disallowedTools Skill`) | las 4 del proyecto |
| Otras herramientas | Read, Glob, Grep, WebFetch, WebSearch, Bash(python3/curl) | las mismas + Bash(uv run) |

Una respuesta es correcta si el número de la línea `RESPUESTA:` está dentro de la tolerancia; en las mixtas,
además, el dato ENAHO (`DATO_ENAHO:`) debe ser correcto.

## Resultados

| Métrica | Modo A | Modo B |
|---|---:|---:|
| **Correctas** | **7/10** | **9/10** |
| BCRP / ENAHO / mixtas | 3/4 · 3/4 · 1/2 | 4/4 · 4/4 · 1/2 |
| Incorrectas | 3 | 1 |
| Sin respuesta | 0 | 0 |
| Tiempo promedio (mediana) | 17.4 s (11.6 s) | 17.6 s (18.5 s) |
| Respondidas solo de memoria | 5 | 1 |

| Pregunta | Esperado | Modo A | Modo B |
|---|---:|---|---|
| PBI real 2020 | −10.93 | −11.0 ✗ (memoria, redondeado) | −10.93 ✓ (`serie`) |
| IPC 12 m dic-2022 | 8.46 | 8.46 ✓ (memoria) | 8.46 ✓ (`serie`) |
| Tasa de referencia dic-2024 | 5.00 | 5.0 ✓ (memoria) | 5.0 ✓ (`serie`) |
| IGV Cajamarca 2024 | 181.89 | 182.0 ✓ (web) | 181.89 ✓ (`panel_departamental`) |
| Pobreza nacional 2024 | 27.6 | 27.6 ✓ (memoria) | 27.6 ✓ (archivos de la skill) |
| Pobreza rural 2024 | 39.3 | 39.3 ✓ (web) | 39.3 ✓ (`limpiando-enaho`) |
| Pobreza Cusco 2024 | 18.5 | 16.8 ✗ (web) | 18.5 ✓ (archivos de la skill) |
| Pobreza nacional 2019 | 20.2 | 20.2 ✓ (memoria) | 20.2 ✓ (memoria) |
| Mixta: Cajamarca + IGV nominal | 28.97 | 29.1 ✓ (web) | 3.82 ✗ (usó el panel real como nominal) |
| Mixta: Cusco + crédito nominal | 18.5 y 28.33 | 28.3 pero pobreza ✗ | 28.33 ✓ (`panel_departamental`) |

**Mejoraron con MCP/Skills:** PBI 2020, pobreza de Cusco y la mixta de Cusco. **Empeoró:** la mixta de Cajamarca.

## Principales errores

1. **Modo A, de memoria:** cifras redondeadas (PBI −11.0 en vez de −10.93). Son plausibles, pero no son la cifra
   oficial exacta, y no hay fuente que lo verifique.
2. **Modo A, web:** para Cusco tomó 16.8 % de una fuente secundaria; el dato de la ENAHO 2024 es 18.5 %.
3. **Modo B, mixta de Cajamarca:** el agente reutilizó `salidas/bcrp_igv_2019_2024.csv`, que
   `panel_departamental` había guardado **deflactado** (soles de 2019) sin indicarlo en el archivo, y lo presentó
   como nominal: 3.82 % real frente a 28.97 % nominal. Además, una orden de Bash fue denegada por la lista de
   herramientas permitidas. **Corrección posterior** (no se volvió a ejecutar para no sesgar el experimento): el
   archivo ahora se llama `..._real.csv` o `..._nominal.csv` y trae una columna `unidad`.
4. Cuando un archivo ya calculado está disponible, el modo B tiende a leerlo en vez de llamar a la herramienta
   (Grep/Read). Eso es correcto si el archivo es trazable, pero hereda cualquier ambigüedad del archivo (error 3).

## Conclusión

MCP y Skills mejoraron la exactitud (9/10 frente a 7/10) y, sobre todo, la **trazabilidad**: en el modo B cada
cifra BCRP viene con código de serie y URL, y cada cifra ENAHO viene de una base validada. El modo A acertó varias
cifras famosas de memoria (inflación 2022, pobreza nacional), pero falló en datos menos conocidos y no puede
mostrar de dónde salen. El tiempo promedio fue casi igual. El único error del modo B no vino del modelo sino de
un archivo mal rotulado: las herramientas deben dejar explícitas las unidades de lo que guardan.
Con 10 preguntas y una ejecución por modo, la diferencia es indicativa, no concluyente.
