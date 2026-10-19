# Búsqueda y fechas · portada v0.90.5

La búsqueda de la portada compara títulos, resúmenes, fuentes y fuentes relacionadas sin distinguir mayúsculas ni acentos. Por ejemplo, «Soller» encuentra «Sóller» y «Deia» encuentra «Deià». También normaliza los espacios y las distintas representaciones Unicode de los acentos. Los textos y atribuciones originales permanecen intactos.

El desplegable **Filtrar por fechas**, bajo los controles de fuente y búsqueda, permite indicar una fecha inicial, final o ambas. Los límites incluyen los días completos de publicación en **Europe/Madrid**, la hora de Mallorca. Se usa `published_at`, nunca la fecha de recopilación ni el horario de vigencia de un aviso. Las publicaciones sin una fecha válida siguen disponibles sin filtro; se excluyen cuando se limita por fechas.

El intervalo seleccionado permanece visible al cerrar el desplegable. Un intervalo invertido muestra un mensaje y no ofrece resultados hasta corregirlo o pulsar **Borrar fechas**. Los controles y mensajes están disponibles en catalán, castellano e inglés. Las fechas se mantienen al cambiar de idioma o sección, igual que la búsqueda y la fuente actuales.

Los filtros se aplican a todo el inventario antes de cargar los bloques de 20. Cambiar las fechas reinicia la carga al primer bloque; cambiar de idioma conserva el número mostrado. El filtro se combina con la sección, la fuente y el texto, así como con el bloque de avisos oficiales vigentes. En Ara sigue aplicándose su ventana de siete días y la exclusión voluntaria de las publicaciones manuales. Para consultar publicaciones más antiguas debe seleccionarse **Tot / Todo / All** o su sección correspondiente.

## Validación

`tests/test_search_dates.mjs` comprueba búsquedas sin acentos en todos los campos, Unicode, los tres idiomas, límites inclusivos en hora de Mallorca y el cambio de hora de octubre, fechas ausentes o inválidas, intervalos invertidos y su limpieza, combinación de filtros, resultados en bloques posteriores y reinicio de la paginación. También verifica que el filtro del bloque de avisos utiliza la fecha de publicación original.

La suite se incluye en la validación de GitHub Actions junto con las pruebas existentes. El cambio afecta a la portada; no requiere actualizar el Worker de Cloudflare.
