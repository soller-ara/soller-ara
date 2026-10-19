# Avisos oficiales vigentes · portada v0.90.3

La portada incorpora un bloque compacto entre la cabecera y los accesos útiles, visible en **Ara** y **Avisos** cuando hay avisos oficiales con vigencia comprobable. Se respetan los filtros de fuente y búsqueda; una publicación excluida de Ara tampoco aparece en el destacado de Ara. Las noticias conservan su orden y las publicaciones siguen disponibles en sus secciones habituales.

## Criterios del destacado

- Tipo de fuente `official`, categoría `alerts`, título y enlace válidos, publicación fechada sin estar en el futuro.
- Estado de origen `active` o `scheduled`, presencia actual confirmada en el feed (`alert_in_feed: true`) y última respuesta correcta de su fuente.
- Inicio y fin explícitos y válidos, con inicio ya alcanzado y fin todavía pendiente. La fecha original de publicación no se usa como fecha de caducidad.
- Última revisión real `sources_checked_at` de como máximo dos horas; una publicación manual que actualice `fetched_at` no renueva esa comprobación. Sin fecha verificable, con una fecha futura anómala o con datos de demostración no se presenta un destacado vigente.

Actualmente AEMET aporta estos intervalos. Los enlaces de policía, movilidad o TIB sin fechas explícitas de vigencia continúan en su sección; no se inventan periodos para destacarlos. Un bloque vacío permanece oculto y no comunica que no existan incidencias.

El título del aviso y el nombre de la fuente se conservan, con enlace al boletín original. Los horarios se muestran en la zona **Europe/Madrid**, indicada como hora de Mallorca, en catalán, español o inglés. El estilo del bloque es común: no asigna por su cuenta un nivel de riesgo a los avisos.

Los boletines de una misma fuente con título y periodo idénticos se agrupan solo en este bloque, conservando el enlace del boletín más reciente. Se muestran dos avisos inicialmente y los restantes bajo «Otros avisos vigentes». Los datos y las tarjetas originales no se modifican.

## Actualización y conservación del funcionamiento

Cada minuto y al volver a la pestaña se recalcula únicamente este bloque. Así puede aparecer un aviso cuyo periodo ya ha empezado o desaparecer uno que ha terminado, incluso sin una nueva recopilación. Los estados activo/previsto de las tarjetas también se calculan con el comienzo del periodo cuando se renderizan. El temporizador no reescribe el feed, recarga los embeds ni desplaza la página.

No se modifican fuentes, cron, filtros de recopilación, contenido guardado, límites sociales, envíos, confirmaciones ni Worker. La versión visible pública y las claves de caché de HTML/CSS/JS son v0.90.3; Administración y Worker mantienen sus propias versiones.

## Comprobaciones

`tests/test_current_alerts.mjs` cubre inicio/fin, estados previstos, fechas inválidas y futuras, tipo de fuente, revisión atrasada o fallida, independencia de `fetched_at`, exclusión de Ara, filtros, agrupación de boletines, idiomas, horario de Mallorca, escapes y retirada por reloj sin reescribir los datos ni el feed. Se integra en la validación habitual de GitHub.

Pruebas locales: 133 pruebas Python y 11 baterías JavaScript correctas. La comprobación visual se realiza sobre la web desplegada y en la plantilla de pantalla de 320 y 390 píxeles; no equivale a una prueba en un dispositivo físico.
