---
name: mapeando-enaho
description: Hace un mapa coroplético de la pobreza monetaria por departamento del Perú con la ENAHO del INEI (2024 o 2019), uniendo por código ubigeo con el GeoJSON departamental, con las 25 unidades y Lima y Callao separados. Úsala cuando pidan un mapa de pobreza, por departamento o región, con la ENAHO.
argument-hint: [año]
---
# Mapear la ENAHO

1. Si no existe `salidas/indicadores_<año>.csv`, usa primero la skill `limpiando-enaho` para ese año.
2. Corre desde `tarea_4/`: `uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py --anio <año>`
3. El script une `ubigeo[:2]` con `FIRST_IDDP` como texto (nunca por nombre), exige 25 departamentos con dato,
   mantiene Lima (15) y Callao (07) separados, usa una escala secuencial desde 0 con leyenda en
   «% de personas pobres» y guarda `mapas/pobreza_departamento_<año>.png`.
4. Para 2024 compara con `referencias/pobreza_departamento_2024.csv` (Sesión 16) y escribe
   `salidas/comparacion_mapa_2024.txt`. Si algo falla, informa el error; no completes datos a mano.
