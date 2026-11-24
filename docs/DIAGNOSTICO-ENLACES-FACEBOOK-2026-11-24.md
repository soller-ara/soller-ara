# Diagnóstico de los enlaces de Instagram rechazados por Facebook

Comprobaciones realizadas el 24 de noviembre de 2026, entre las 18:07 y las 18:12, Europe/Madrid. Se han utilizado únicamente consultas GET a Meta y a páginas públicas, y HEAD para comprobar las cabeceras de las imágenes. No se han enviado publicaciones de prueba ni se han reintentado los envíos originales. Las fotografías no se han descargado ni reutilizado.

## Resultado comprobado

Los dos rechazos originales ocurrieron al enviar sus enlaces de Instagram a `/{page-id}/feed`: `The url you supplied is invalid [code=1500, subcode=1611248]`. El rechazo se produjo después de guardar y desplegar las entradas de la web.

La revisión adicional confirma que las dos publicaciones rechazadas proceden de `@iesguillemcolomcasasnoves`, mientras que las dos aceptadas proceden de otras cuentas. Actualmente las cuatro páginas originales ofrecen título e imagen, y las cuatro imágenes comprobadas responden HTTP 200 con tipo `image/jpeg`. Esta coincidencia de cuenta es una diferencia observada, no una prueba de que el instituto haya prohibido compartir sus publicaciones.

| Fuente y referencia | Envío original a Facebook (Madrid) | Resultado original | Página pública ahora | Imagen ahora |
| --- | --- | --- | --- | --- |
| Botanic Atelier Floral, `Df7vOitMO6X` | 16:28:12 | Confirmado, con imagen en los adjuntos de Facebook | HTTP 200 | HTTP 200, JPEG |
| Toni Socias, `DgHcHqwFiBr` | 16:35:18 | Confirmado, con imagen en los adjuntos de Facebook | HTTP 200 | HTTP 200, JPEG |
| IES Guillem Colom Casasnoves, `DgIJB8qCJWd`, Bebras.cat | 17:33:34 | Rechazo `1500/1611248` | HTTP 200 | HTTP 200, JPEG |
| IES Guillem Colom Casasnoves, `DgIJXAnoYYU`, taller de cubs de Rubik | 17:38:09 | Rechazo `1500/1611248` | HTTP 200 | HTTP 200, JPEG |

## Comparación del procedimiento y de las direcciones

- El contenido de `scripts/publish_own_social.py` era idéntico en el commit de la primera aceptación (`f1059071e3c1204a8c8621716078d2c7c5e8dd49`) y el del primer rechazo (`9f4b594e521dd94bce1f3d14e4677ac3deb8a3ea`). El ajuste del respaldo horario no modificó ese publicador.
- Los cuatro envíos tenían `PUBLISH_FACEBOOK=true`, `PUBLISH_INSTAGRAM=false`, tipo `social_link`, y título y texto propios vacíos. La categoría de la web no forma parte de la solicitud a Facebook.
- Una prueba local sin red comprobó que la codificación de la solicitud preserva exactamente las cuatro direcciones originales, incluidos los signos `=`. No se detectaron espacios, truncamientos ni alteración de los enlaces.
- Las cuatro direcciones con parámetros de compartición responden HTTP 301 hacia su versión sin parámetros, y las cuatro versiones canónicas responden HTTP 200. No se ha probado a publicarlas sin parámetros: poder leerlas no garantiza que Facebook vaya a aceptar el envío.
- No se obtuvo una fecha original verificable en los metadatos públicos examinados. Por ello no se atribuye el rechazo a la antigüedad o reciente creación de las publicaciones.

## Meta: permisos y límites de las consultas

La comprobación autenticada identificó la página Sóller Ara y la tarea `CREATE_CONTENT`. El token tiene concedidos `pages_manage_posts` y `pages_read_engagement`, además de los permisos de Instagram ya utilizados por el proyecto. Las dos publicaciones originales aceptadas se pudieron consultar y sus adjuntos contienen imagen.

Esto permite distinguir la capacidad para publicar en la página propia de la lectura de cuentas ajenas o la inspección de enlaces de las plataformas de Meta. No hay un error de permisos de publicación en el mensaje original `1500/1611248`.

La consulta de información Open Graph mediante `GET /?id=<url>` devuelve `(#10) Facebook URLs cannot be crawled` para los ocho casos examinados: las cuatro referencias, con y sin parámetros. Ocurre también con las dos que se publicaron correctamente. Por tanto, ese rechazo de la API de consulta no explica la diferencia entre los envíos.

Los dos identificadores correspondientes a la recuperación posterior con enlaces de Sóller Ara no pudieron leerse en la comprobación actual. La API devuelve una respuesta ambigua de objeto no disponible o permisos. Este dato no se utiliza para afirmar que los originales no existan, que se hayan borrado, ni que haya un bloqueo general de la cuenta.

## Lo que falta para determinar la causa interna exacta

El error conservado en los envíos originales solo incluye mensaje, código y subcódigo. El publicador no conserva `fbtrace_id`, `error_user_title` ni `error_user_msg` si Meta los devuelve. No se puede reconstruir retrospectivamente un detalle que no se guardó, ni asegurar que la respuesta original incluyera campos adicionales.

Meta documenta que `fbtrace_id` permite a su soporte localizar una solicitud fallida y que caduca pronto. El [depurador oficial del primer enlace](https://developers.facebook.com/tools/debug/?q=https%3A%2F%2Fwww.instagram.com%2Fp%2FDgIJB8qCJWd%2F&locale=es_ES) no ha podido consultarse desde esta sesión. Obtener ese diagnóstico o conservar los detalles de un futuro rechazo permitiría avanzar. No se ha repetido una solicitud de publicación para intentar reproducir el error.

La conclusión es un rechazo de Facebook al compartir esos dos enlaces concretos de Instagram. No hay evidencia suficiente para afirmar una causa interna de Meta, un cambio de privacidad del instituto o un bloqueo temporal determinado. La accesibilidad comprobada ahora tampoco demuestra cuál fue la respuesta de Instagram a los servidores de Meta en el momento de los rechazos.

## Pruebas y evidencias

- [Comprobación autenticada de enlaces, permisos y adjuntos](https://github.com/soller-ara/soller-ara/actions/runs/45445068796).
- [Segunda comprobación pública, con cabeceras de las imágenes](https://github.com/soller-ara/soller-ara/actions/runs/45445775054).
- [Registro del primer envío rechazado y su ejecución original](https://github.com/soller-ara/soller-ara/actions/runs/45438437302/attempts/1).
- [Registro del segundo envío rechazado y su ejecución original](https://github.com/soller-ara/soller-ara/actions/runs/45439141530/attempts/1).
- [Documentación oficial sobre errores de Graph y campos de diagnóstico](https://developers.facebook.com/docs/graph-api/guides/error-handling/).

Los scripts y sus pruebas están únicamente en la rama `diagnostico-enlaces-facebook-20261124`. Han pasado 12 pruebas del diagnóstico sin conexiones externas y ambas ejecuciones de comprobación. No se ha modificado el código de la aplicación en `main`, el Worker, las fuentes ni las reglas de publicación. La alternativa sin fotografía continúa retirada.
