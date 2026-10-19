# Publicaciones por bloques · portada v0.90.4

La portada muestra inicialmente 20 publicaciones. El botón «Veure més / Ver más / Show more» añade otras 20, hasta alcanzar todos los resultados. El contador muestra cuántas publicaciones están visibles y el total que coincide con los filtros. Al llegar al final desaparece el botón; ante una búsqueda vacía se mantiene el mensaje existente.

## Búsqueda y navegación

La selección se aplica al inventario completo antes de recortar cada bloque. Una búsqueda puede encontrar directamente una noticia antigua que todavía no se haya mostrado. Cambiar categoría, fuente o texto de búsqueda vuelve al primer bloque de los nuevos resultados. Cambiar el idioma conserva la cantidad de publicaciones que se habían abierto. Ara mantiene su orden cronológico y sus reglas de siete días y exclusión voluntaria; las otras secciones conservan su orden anterior.

El bloque de avisos oficiales vigentes sigue evaluando todos los resultados filtrados. Un aviso activo no deja de destacarse porque su tarjeta quede más allá de las primeras 20 publicaciones.

## Tarjetas y accesibilidad

Al ampliar se añaden nodos al final, conservando las tarjetas y los iframes existentes. Los controles de compartir funcionan también en las nuevas tarjetas mediante un único manejador del feed. Los widgets de X se procesan dentro de los artículos nuevos; Instagram solo recibe una petición de procesamiento si el nuevo bloque incluye un embed de Instagram. La presentación del contenido externo sigue dependiendo de su plataforma y sus permisos.

El foco se coloca en el primer artículo nuevo y se muestra su comienzo, para continuar la lectura en el nuevo bloque. El botón tiene un tamaño apto para pantallas táctiles, relación `aria-controls` con el feed y contador anunciado de forma discreta. Se mantiene la navegación normal por enlaces y botones.

Esta mejora reduce el número de tarjetas, imágenes e incrustaciones creadas inicialmente. El JSON completo sigue cargándose para poder buscar y filtrar en todo el archivo; no se implementa paginación de servidor ni se modifica el contenido almacenado, la recopilación o los envíos sociales.

## Verificación

`tests/test_feed_pagination.mjs` prueba límites de bloque, último bloque incompleto, contador, ausencia de duplicados, identidad de nodos existentes, búsqueda fuera del primer bloque, reinicio al filtrar, conservación de cantidad al cambiar idioma, orden de Ara, controles de compartir añadidos, procesamiento limitado de widgets y avisos vigentes más allá del primer bloque. También comprueba que un cambio del inventario provoque una reconstrucción coherente en lugar de añadir un prefijo antiguo.

Pruebas locales: 133 pruebas Python y 12 baterías JavaScript. Se comprueba en la web desplegada la carga inicial, la ampliación, los filtros y el diseño de 320 y 390 píxeles. Esta comprobación de anchuras no equivale a una prueba en un dispositivo físico.

Versión pública v0.90.4; claves de caché de CSS y JS actualizadas. Administración y Worker mantienen sus versiones y no necesitan cambios en Cloudflare.
