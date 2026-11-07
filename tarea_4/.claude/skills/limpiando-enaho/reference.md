# Referencia ENAHO para `limpiando-enaho`

## Archivos (portal de microdatos del INEI, formato Stata)

| Año | Código | Módulo 34 (sumaria) | Módulo 02 (miembros) |
|---|---|---|---|
| 2024 | 966 | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo34.zip | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo02.zip |
| 2019 | 687 | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/687-Modulo34.zip | https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/687-Modulo02.zip |

Se usan `sumaria-<año>.dta` (no la versión `-12g`) y `enaho01-<año>-200.dta`.

## Variables

| Variable | Módulo | Significado |
|---|---|---|
| `conglome`, `vivienda`, `hogar` | ambos | Llave del hogar (texto: conservar ceros) |
| `codperso` | 02 | Número de la persona dentro del hogar |
| `ubigeo` | ambos | Ubicación; `ubigeo[:2]` = departamento (01–25; 07 Callao, 15 Lima) |
| `estrato` | 34 | 1–5 urbano, 6–8 rural |
| `dominio` | 34 | 8 = Lima Metropolitana |
| `pobreza` | 34 | 1 pobre extremo, 2 pobre no extremo, 3 no pobre |
| `mieperho` | 34 | Miembros del hogar (residentes habituales) |
| `factor07` | 34 | Factor de expansión del hogar |
| `facpob07` | 02 | Factor de expansión de la persona |
| `p204` | 02 | ¿Es miembro del hogar? 1 sí, 2 no |
| `p205` | 02 | ¿Estuvo ausente más de 30 días? 1 sí, 2 no |
| `p206` | 02 | ¿Está presente hace más de 30 días? 1 sí, 2 no |
| `p207` | 02 | Sexo: 1 hombre, 2 mujer |
| `p208a` | 02 | Edad en años |

Residente habitual: `((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1))`.

## Cifras oficiales para validar

| Cifra | 2024 | 2019 | Fuente |
|---|---|---|---|
| Pobreza monetaria nacional | 27.6 % | 20.2 % | INEI, *Evolución de la pobreza monetaria* (informes técnicos 2025 y 2020); 2019 verificado en https://www.inei.gob.pe/media/MenuRecursivo/noticias/np_65_2020.pdf |
| Urbana / rural | 24.8 % / 39.3 % | 14.6 % / 40.8 % | 2024: Sesión 16; 2019: INEI, nota de prensa N.º 065-2020 y presentación del jefe del INEI (mayo 2020) |
| Residentes habituales | 108,664 | sin referencia publicada | Sesión 16 |
| Departamentos | 25 | 25 | `referencias/pobreza_departamento_2024.csv` (Sesión 16) |

Tolerancia: ±0.1 pp en la pobreza nacional (esencial); ±0.3 pp en urbana/rural (aviso).

Verificación 2019 (7 nov 2026): INEI publica 20.2 % nacional, 14.6 % urbana, 40.8 % rural y 2.9 % extrema; `limpiar.py` obtiene 20.19 %, 14.58 %, 40.78 % y 2.85 %.
