---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria de la ENAHO del INEI (2024 o 2019) por área urbana/rural, sexo, grupo de edad o departamento, o compara departamentos entre 2019 y 2024, siempre con estimaciones ponderadas. Úsala cuando pidan graficar, visualizar o comparar pobreza de la ENAHO.
argument-hint: [area|sexo|edad|departamento|cambio] [año]
---
# Graficar la ENAHO

1. Si no existe `salidas/indicadores_<año>.csv` (o, para `cambio`, los de 2019 y 2024), usa primero la skill
   `limpiando-enaho` para ese año.
2. Traduce el pedido a un tipo: `area` (urbana/rural), `sexo`, `edad`, `departamento`, `cambio`
   (departamentos 2019 vs 2024, en puntos porcentuales).
3. Corre desde `tarea_4/`: `uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --tipo <tipo> --anio <año>`
4. El script lee solo cifras ponderadas de `indicadores_<año>.csv`, dibuja barras desde cero, ordenadas, de un
   color, con el valor escrito, título analítico con periodo, unidad y nota «Fuente: INEI, ENAHO <año>».
   Guarda un PNG de 200 dpi en `figuras/`.
5. Responde con la ruta del PNG y las cifras que imprime el script. No describas diferencias como causales.
