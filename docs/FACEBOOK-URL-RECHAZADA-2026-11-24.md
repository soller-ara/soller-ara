# Enlaces de redes: rechazo de URL por Facebook

## Incidencia comprobada

El 24 de noviembre de 2026, las dos últimas referencias de Instagram se guardaron en la web, pero Facebook rechazó su envío con `The url you supplied is invalid [code=1500, subcode=1611248]`.

| Entrada | Creación (Europe/Madrid) | Respuesta de Facebook | Ejecución |
| --- | --- | --- | --- |
| `soller-ara-711a34916e298494` | 17:33:20 | 17:33:34, rechazo explícito | [45438437302](https://github.com/soller-ara/soller-ara/actions/runs/45438437302) |
| `soller-ara-e175d2cb5467d844` | 17:36:56 | 17:38:09, rechazo explícito | [45439141530](https://github.com/soller-ara/soller-ara/actions/runs/45439141530) |

Ambas ejecuciones recibieron `PUBLISH_FACEBOOK=true` y `PUBLISH_INSTAGRAM=false`. El fallo no es una casilla desmarcada ni un permiso para consultar cuentas ajenas. Dos referencias manuales anteriores sí obtuvieron identificador de Facebook ese mismo día.

## Corrección

Se conserva el envío del enlace original como primera opción. Únicamente cuando Graph devuelve el rechazo estructurado exacto `1500/1611248`, para una referencia `social_link`, se admite una segunda solicitud compartiendo la entrada individual ya publicada de Sóller Ara. El mensaje conserva la atribución y el enlace original. No se copian imágenes ni textos del origen.

No hay segunda solicitud ante tiempos de espera, errores de red, falta de identificador, permisos, límites de uso u otros errores de Graph. Si Facebook también rechaza la alternativa, se registra el error y se detiene. Los artículos propios y carteles mantienen su comportamiento. No cambia el Worker, las fuentes, el horario ni la publicación automática de Instagram.

## Pruebas y recuperación

Las pruebas simulan el rechazo exacto y la respuesta de éxito; comprueban el mensaje, el destino alternativo, el recibo, el límite de dos solicitudes y la omisión de envíos que ya tienen éxito registrado. También comprueban que los errores inciertos y otros rechazos no disparan una segunda solicitud. No se contacta con Meta durante las pruebas.

La recuperación de estas dos entradas debe utilizar sus ejecuciones originales: `PUBLISH_KEY=${{ github.run_id }}` conserva los identificadores existentes y `add_own_post.py` devuelve `OWN_SKIP` al encontrarlos. Antes de reintentar se comprueba que siguen presentes, no están ocultas y no existe ningún recibo de éxito. El resultado solo se considera publicado cuando `data/social_publish_log.json` contiene `status=success` y un identificador remoto. No se crea una entrada nueva ni se vuelve a enviar Instagram.
