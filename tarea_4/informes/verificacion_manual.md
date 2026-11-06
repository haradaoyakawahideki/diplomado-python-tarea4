# Verificación manual de cifras del informe

> **Por completar por el estudiante.** Comprobar cada cifra fuera del agente (web del BCRP / informe del INEI /
> abrir el archivo) y anotar lo observado. No copiar estos valores del informe: verificarlos en la fuente.

| # | Afirmación del informe | Valor en el informe | Cómo verificar | Valor observado | ¿Coincide? | Diferencia / comentario |
|---|---|---|---|---|---|---|
| 1 | PBI real 2020 (H1) | −10.93 % | https://estadisticas.bcrp.gob.pe/estadisticas/series/anuales/resultados/PM04923AA/html/2019/2024/ | | | |
| 2 | Inflación Lima 12 m, máximo jun-2022 (H1) | 8.81 % | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01273PM/html/2022-1/2022-12/ | | | |
| 3 | Pobreza nacional 2024 (H4) | 27.58 % | INEI, *Perú: Evolución de la pobreza monetaria 2015-2024* (informe técnico) y `salidas/validacion.txt` | | | |
| 4 (opcional) | Pobreza Cajamarca 2024 (H4) | 45.0 % | INEI, informe técnico 2024, cuadro por departamento / `referencias/pobreza_departamento_2024.csv` | | | |
| 5 (opcional) | IGV interno Cajamarca 2019 y 2024 (nominal) | 141.04 y 181.89 millones S/ | https://estadisticas.bcrp.gob.pe/estadisticas/series/anuales/resultados/RD16452DA/html/2019/2024/ | | | |

**Manejo de errores observado:** la búsqueda `buscar_series("ipc lima", frecuencia="Anual")` no devolvió resultados y
el agente lo informó y usó la serie mensual; una orden de Bash fue denegada por la lista de herramientas y el agente
la reemplazó por dos llamadas separadas (ver `evidencias_ia/integracion/resumen_ejecucion.md`).
