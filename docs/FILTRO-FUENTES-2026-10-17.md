# Prioridad 4: unificación del filtro de fuentes

La versión pública 0.90.2 agrupa las opciones del desplegable por el nombre de la fuente en lugar de presentar por separado cada identificador automático o manual. Se normalizan mayúsculas, acentos, espacios y el separador central. La selección se conserva al cambiar de idioma y al recargar las opciones, mientras la fuente siga disponible.

Los nombres del catálogo tienen preferencia como etiqueta del filtro. Las tarjetas conservan íntegros su nombre original, su identificador y sus enlaces; no se reescriben publicaciones ni se modifica la recopilación o la configuración social.

## Variantes reconocidas

- MÉS / Mes / Més per Sóller: se agrupan por normalización.
- Ajuntament de Sóller, Fornalutx y Deià y Setmanari Sóller: reúnen las publicaciones automáticas y las referencias manuales con el mismo nombre.
- IES Guillem Colom Casasnovas: se agrupa con IES Guillem Colom Casasnoves.
- Partit Popular Sóller: se agrupa con Partido Popular · Sóller.
- Setmanari Veu de Sóller y Veu de Sóller: se agrupan con Sa Veu de Sóller.
- Socialistes de Sóller: se agrupa con PSIB-PSOE · Sóller. Socialistes de Mallorca conserva su opción propia.

Setmanari Sóller y Sa Veu de Sóller siguen siendo dos fuentes diferentes, al igual que los canales de YouTube identificados como tales. Las referencias sin nombre se agrupan en una opción traducida que indica que no consta la fuente.

Se resuelve además el caso de varias publicaciones con `source_id=soller-ara` y atribuciones diferentes: Publicació de xarxa y Sóller Ara tienen sus propias opciones. No se permite que el último nombre leído sobrescriba y oculte a los otros.

## Comprobación

Nueve suites JavaScript correctas, incluida una nueva que comprueba la unión de publicaciones automáticas y manuales, las atribuciones, la selección al cambiar de idioma, las variantes, los canales diferenciados, los IDs compartidos, las búsquedas, los nombres ausentes y el escape de HTML. No se confunden nombres como A+B y A B.

Referencias de identidad usadas para revisar las variantes de nombre:

- Sa Veu: https://saveu.cat/avis-legal/
- Denominación Setmanari Veu de Sóller: https://ajsoller.net/en/node/6660
- Agrupación local PSIB-PSOE / Socialistes de Sóller: https://www.psib-psoe.org/mallorca/el-psib-psoe-es-presenta-com-a-alternativa-a-soller-per-resoldre-la-saturacio-del-municipi-i-el-problema-de-la-manca-dhabitatge/

Estas equivalencias organizan etiquetas de navegación: no añaden permisos de Meta ni validan cuentas externas.
