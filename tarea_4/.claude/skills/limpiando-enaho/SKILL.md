---
name: limpiando-enaho
description: Limpia los módulos 34 (sumaria) y 02 (miembros) de la ENAHO del INEI (2024 o 2019) y arma bases de personas y hogares con pobreza monetaria, departamento, área y factores de expansión, con validación contra cifras oficiales. Úsala cuando pidan limpiar, unir o analizar la ENAHO, o calcular pobreza nacional, urbana/rural, por departamento, región, sexo o edad.
argument-hint: [año: 2024 o 2019]
---
# Limpiar la ENAHO

1. Año: usa `$0` si viene; si no, 2024. Solo hay configuración para 2024 (código INEI 966) y 2019 (código 687).
2. Si faltan `datos/<código>-Modulo34.zip` o `datos/<código>-Modulo02.zip`, pide al usuario bajarlos
   (enlaces en `reference.md`). No inventes datos.
3. Corre exactamente, desde la carpeta `tarea_4/`:
   `uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio <año>`
4. Lee `salidas/validacion_<año>.txt`. Si dice `PROCESO DETENIDO` o alguna línea `FALLIDA`, detente y
   explica qué falló. Nunca ajustes cifras para que coincidan con la referencia.
5. Salidas: `salidas/personas_<año>.parquet`, `salidas/hogares_<año>.parquet`, `salidas/indicadores_<año>.csv`.
6. Toda cifra va ponderada: nacional, área y departamento con la sumaria y `factor07 × mieperho` (método oficial
   INEI, columna `metodo`); sexo y edad con personas y `facpob07`. Nunca promedios simples.
7. Para cifras que no están en `indicadores_<año>.csv`, calcula sobre los parquet con el peso correcto
   y muestra el código. Antes de usar una variable nueva, lee `reference.md`.
