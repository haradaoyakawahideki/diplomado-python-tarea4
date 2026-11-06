---
name: cruzando-bcrp-enaho
description: Cruza paneles departamentales del BCRP (IGV, crédito, inversión regional, descargados con la herramienta MCP panel_departamental) con la pobreza monetaria de la ENAHO 2019 y 2024 para describir si los departamentos más pobres antes de la pandemia se recuperaron más o menos. Úsala cuando pidan relacionar pobreza y recuperación económica, actividad regional o indicadores del BCRP por departamento.
argument-hint: [desde hasta]
---
# Cruzar BCRP y ENAHO por departamento

1. Requisitos (créalos si faltan, en este orden):
   - `salidas/indicadores_2019.csv` y `salidas/indicadores_2024.csv` → skill `limpiando-enaho` con `2019` y `2024`.
   - `salidas/bcrp_<indicador>_2019_2024_real.csv` para `igv`, `credito` e `inversion_regional` → herramienta MCP
     `panel_departamental` del servidor `bcrp` (real=True). No copies cifras a mano en estos archivos.
2. Corre desde `tarea_4/`: `uv run ${CLAUDE_SKILL_DIR}/scripts/cruzar.py`
3. El script une por `ccdd` (ubigeo[:2]), exige 25 departamentos, calcula correlaciones de Spearman entre la
   pobreza 2019 y cada índice de recuperación, compara terciles de pobreza 2019 y guarda:
   `salidas/cruce_departamental.csv`, `salidas/cruce_resumen.txt`, `figuras/bcrp_recuperacion_real.png` y
   `figuras/cruce_pobreza2019_recuperacion.png`.
4. Al interpretar: son asociaciones entre 25 departamentos, no efectos causales. Menciona que los índices son
   nominales deflactados con el IPC de Lima, que el IGV refleja dónde se recauda (no solo dónde se consume) y que
   la pobreza departamental tiene error muestral.
