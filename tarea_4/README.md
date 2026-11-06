# Tarea 4 · Agente de investigación socioeconómica: MCP del BCRP + Skills de ENAHO

**Estudiante:** Hideki Harada Oyakawa · Python Intermedio (PUCP / d2cml) · [Issue #201](https://github.com/d2cml-ai/Data-Science-Python/issues/201)

## 1. Objetivo

Construir un agente en Claude Code que responda preguntas sobre la realidad socioeconómica del Perú con datos
oficiales y verificables: series del **BCRP** mediante un servidor **MCP** propio y microdatos de la **ENAHO (INEI)**
mediante **Skills** que limpian, grafican, mapean y cruzan la información.

**Pregunta de investigación:** *¿Los departamentos con mayor pobreza monetaria antes de la pandemia (2019) mostraron
una recuperación económica más débil entre 2019 y 2024, y cómo se distribuía la pobreza departamental en 2024?*
La pregunta es descriptiva: no se estima ningún efecto causal (ver [informe](informes/informe_final.md)).

## 2. Arquitectura

```text
            pregunta en lenguaje natural
                        │
                  Claude Code (agente)
          ┌─────────────┴──────────────┐
   MCP "bcrp" (mcp/server.py)     Skills (.claude/skills/)
   buscar_series · serie          limpiando-enaho ──► personas/hogares_<año>.parquet, indicadores_<año>.csv, validacion.txt
   resumen · comparar_periodos    graficando-enaho ─► figuras/*.png
   panel_departamental            mapeando-enaho ───► mapas/*.png
   recurso bcrp://serie/{codigo}  cruzando-bcrp-enaho ► cruce_departamental.csv + figuras de cruce
   prompt informe(tema)                 ▲
          │                             │ lee salidas/bcrp_*.csv escritos por panel_departamental
          └──► API BCRP          datos/ (zip INEI, ignorados por git)
                        │
               informes/informe_final.md
```

Toda cifra sale de una herramienta o un script: el modelo no hace cuentas a mano.

## 3. Herramientas MCP (`mcp/server.py`, FastMCP)

| Herramienta | Qué hace |
|---|---|
| `buscar_series(texto, frecuencia, limite)` | Busca entre las ~17 mil series del catálogo oficial del BCRP |
| `serie(codigo, desde, hasta)` | Descarga los datos (mensual, trimestral, diaria o anual), salta `n.d.`, reintenta si la API devuelve HTML y da la URL fuente |
| `resumen(codigo, desde, hasta)` | Primero, último, cambio, variación %, promedio, máximo y mínimo con su periodo |
| **`comparar_periodos`** (propia) | Compara un indicador en dos intervalos (p. ej. 2017-19 vs 2022-24): promedios, sumas, diferencia, variación e índice B/A; rechaza intervalos solapados |
| **`panel_departamental`** (propia, extra) | Baja de una vez una serie anual para los 25 departamentos (IGV, crédito, inversión regional), la asigna al código ubigeo de la ENAHO, la deflacta con el IPC y guarda `salidas/bcrp_<indicador>_<desde>_<hasta>_<real|nominal>.csv` |
| Recurso `bcrp://serie/{codigo}` | Ficha de la serie: nombre, categoría, frecuencia, unidad, descripción |
| Prompt `informe(tema, desde, hasta)` | Plantilla de informe que exige citar código, periodo y fuente y no afirmar causalidad |

**Pruebas:** `uv run pytest -v` → **10 passed** (8 originales de la Sesión 04 sin cambios + 2 propias de
`comparar_periodos`). Salida en [`evidencias_ia/mcp/pruebas.txt`](evidencias_ia/mcp/pruebas.txt).

## 4. Skills (`.claude/skills/`)

| Skill | Entra | Sale | Reglas clave |
|---|---|---|---|
| `limpiando-enaho` | `datos/<código>-Modulo34.zip` y `-Modulo02.zip` (2024 o 2019) | `salidas/personas_<año>.parquet`, `hogares_<año>.parquet`, `indicadores_<año>.csv`, `validacion_<año>.txt` | Llaves como texto, residentes habituales, `merge(validate="m:1")`, se detiene si falla una validación esencial |
| `graficando-enaho` | `indicadores_<año>.csv` | `figuras/pobreza_{area,sexo,edad,departamento}_<año>.png`, `pobreza_cambio_2019_2024.png` | Ponderado, barras desde 0, título analítico, unidad y fuente, 200 dpi |
| `mapeando-enaho` | `indicadores_<año>.csv` + GeoJSON | `mapas/pobreza_departamento_<año>.png`, `salidas/comparacion_mapa_2024.txt` | Une `ubigeo[:2]` = `FIRST_IDDP`, exige 25 unidades, Lima y Callao separados, escala secuencial desde 0 |
| `cruzando-bcrp-enaho` (extra) | indicadores 2019 y 2024 + paneles BCRP | `salidas/cruce_departamental.csv`, `cruce_resumen.txt`, `figuras/bcrp_recuperacion_real.png`, `figuras/cruce_pobreza2019_recuperacion.png` | Une por `ccdd`, exige 25, Spearman y terciles, advierte que no es causal |

Las skills de gráficos, mapas y cruce piden ejecutar antes `limpiando-enaho` si no existe la base procesada.

**Validación ENAHO 2024** ([`salidas/validacion.txt`](salidas/validacion.txt)): pobreza nacional **27.58 %**
(ref. 27.6 %), **108,664** residentes habituales, **25/25** departamentos, urbano 24.81 % / rural 39.30 %,
sin duplicados en la unión. Los 25 departamentos coinciden con la referencia de la Sesión 16
([`salidas/comparacion_mapa_2024.txt`](salidas/comparacion_mapa_2024.txt)).
**ENAHO 2019:** 20.19 % (oficial INEI 20.2 %).

**Método de ponderación:** nacional, área y departamento con la sumaria y `factor07 × mieperho` (método oficial del
INEI; reproduce exactamente la referencia departamental). Sexo y edad con personas y `facpob07` (27.53 % nacional;
la diferencia de 0.05 pp con el otro método se explica por la unidad de análisis).

## 5. Datos

| Fuente | Enlace | Uso |
|---|---|---|
| INEI, ENAHO 2024, módulo 34 | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip | Pobreza 2024 |
| INEI, ENAHO 2024, módulo 02 | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip | Personas 2024 |
| INEI, ENAHO 2019, módulos 34 y 02 | `.../STATA/687-Modulo34.zip`, `.../STATA/687-Modulo02.zip` | Pobreza prepandemia |
| Límites departamentales | [GeoJSON del curso](https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson) (copia en `referencias/`) | Mapas |
| BCRP, series estadísticas | https://estadisticas.bcrp.gob.pe/estadisticas/series/ | PBI, IPC, IGV, crédito, inversión regional |

Los zip del INEI van en `datos/` (ignorada por git). ENAHO 2019 se añade a los datos obligatorios porque la
pregunta necesita la pobreza prepandemia; se procesa con la misma skill.

## 6. Instalación

```bash
git clone https://github.com/haradaoyakawahideki/diplomado-python-tarea4
cd diplomado-python-tarea4/tarea_4
uv sync
mkdir -p datos && cd datos
for c in 966 687; do for m in 34 02; do
  curl -LO https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/${c}-Modulo${m}.zip; done; done
cd ..
```

## 7. Conectar el MCP a Claude Code

`.mcp.json` ya declara el servidor `bcrp` (`uv run mcp/server.py`). Al abrir `claude` dentro de `tarea_4/`, acepten
el servidor del proyecto y comprueben con `/mcp`. Equivalente manual:
`claude mcp add --scope project bcrp -- uv run mcp/server.py`.

## 8. Reproducir

```bash
uv run pytest -v                                                          # 10 passed
uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024      # validacion.txt
uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2019
for t in area sexo edad departamento cambio; do uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo $t; done
uv run .claude/skills/mapeando-enaho/scripts/mapear.py --anio 2024
uv run python -c "import sys; sys.path.insert(0,'mcp'); from server import panel_departamental as p; [p(i) for i in ('igv','credito','inversion_regional')]"
uv run .claude/skills/cruzando-bcrp-enaho/scripts/cruzar.py
uv run evaluacion/evaluar.py                                              # experimento A/B (usa claude -p)
```

## 9. Evaluación

Ver [`evaluacion/comparacion.md`](evaluacion/comparacion.md) y [`evaluacion/resultados.csv`](evaluacion/resultados.csv).

| | Sin MCP/Skills (A) | Con MCP/Skills (B) |
|---|---:|---:|
| Correctas | **7/10** | **9/10** |
| BCRP / ENAHO / mixtas | 3/4 · 3/4 · 1/2 | 4/4 · 4/4 · 1/2 |
| Tiempo promedio | 17.4 s | 17.6 s |
| Respondidas solo de memoria | 5 | 1 |

El único error del modo B vino de un archivo de `panel_departamental` sin rotular la unidad (real vs nominal), ya
corregido; ver el análisis completo en `comparacion.md`.

## 10. Limitaciones y problemas encontrados

- La pobreza departamental de la ENAHO tiene error muestral (pocas centenas o miles de hogares por departamento).
- El BCRP no publica PBI departamental: se usan indicadores aproximados (IGV recaudado, crédito, inversión regional),
  deflactados con el IPC de **Lima**; el IGV refleja dónde se recauda, no solo dónde se consume.
- Con 25 departamentos, las correlaciones son frágiles y no permiten conclusiones causales.
- La serie de IPC base 2009 (PN01270PM) está descontinuada desde 2022; se usa PN38705PM (Dic.2021 = 100).
- La API del BCRP a veces devuelve HTML en lugar de JSON: `serie` reintenta y guarda en caché.
- La caché de fuentes de Matplotlib del sistema estaba corrupta y hubo que regenerarla.
- La primera versión del evaluador lanzaba `claude -p` saltándose permisos; el modo automático lo bloqueó y se
  cambió a una lista explícita de herramientas permitidas por modo.

## 11. Ejemplo de ejecución completa

Ver [`evidencias_ia/integracion/`](evidencias_ia/integracion/): una sola sesión de `claude -p` que usa varias
herramientas MCP (`buscar_series`, `resumen`, `comparar_periodos`, `panel_departamental`) y varias skills
(`limpiando-enaho`, `graficando-enaho`, `mapeando-enaho`, `cruzando-bcrp-enaho`) y escribe el informe.

## 12. Evidencias del uso de IA

Todo se desarrolló con Claude Code. Las conversaciones están en [`evidencias_ia/`](evidencias_ia/):
`mcp/`, `skills/`, `integracion/`, `evaluacion/` (registros `.jsonl` de cada pregunta en ambos modos).
