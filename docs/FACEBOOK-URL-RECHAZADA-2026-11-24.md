# Enlaces de redes: rechazo de URL por Facebook

## Incidencia comprobada

El 24 de noviembre de 2026, las dos últimas referencias de Instagram se guardaron en la web, pero Facebook rechazó su envío con `The url you supplied is invalid [code=1500, subcode=1611248]`.

| Entrada | Creación (Europe/Madrid) | Respuesta de Facebook | Ejecución |
| --- | --- | --- | --- |
| `soller-ara-711a34916e298494` | 17:33:20 | 17:33:34, rechazo explícito | [45438437302](https://github.com/soller-ara/soller-ara/actions/runs/45438437302) |
| `soller-ara-e175d2cb5467d844` | 17:36:56 | 17:38:09, rechazo explícito | [45439141530](https://github.com/soller-ara/soller-ara/actions/runs/45439141530) |

Ambas ejecuciones recibieron `PUBLISH_FACEBOOK=true` y `PUBLISH_INSTAGRAM=false`. El fallo no es una casilla desmarcada ni un permiso para consultar cuentas ajenas. Dos referencias manuales anteriores sí obtuvieron identificador de Facebook ese mismo día.

## Criterio vigente: detener el envío si Meta rechaza el original

Por indicación del usuario se ha retirado la alternativa que compartía la entrada individual de Sóller Ara tras el rechazo `1500/1611248`. El usuario prefiere que el envío falle antes que una publicación sin fotografía ni texto propio.

Una referencia `social_link` se envía exclusivamente con su enlace original. Si Meta lo rechaza, se conserva el error y se detiene el envío de Facebook, sin sustituir el enlace por el de nuestra web ni crear otra publicación. Se mantienen la atribución, la omisión de envíos confirmados y el tratamiento de errores de red o recibos ausentes. Los artículos propios y carteles conservan su comportamiento.

La aceptación de un enlace por Meta no demuestra que Facebook haya mostrado una imagen. La retirada de esta alternativa evita la sustitución que provocó estas dos publicaciones sin fotografía; no constituye una verificación de todas las vistas previas de Facebook.

## Antecedente

La alternativa retirada permitió recuperar ambas publicaciones el 24 de noviembre de 2026 a las 17:50 (Europe/Madrid), con identificadores de Facebook `1384755221378998_122135919285467310` y `1384755221378998_122135919363467310`. En la web se conservaron los identificadores, fechas y contenidos originales. Las páginas individuales carecían de una imagen de vista previa, por lo que la recuperación no conservó la presentación de los enlaces anteriores.

Retirar la alternativa no borra los envíos ya realizados ni altera sus recibos. No se vuelven a ejecutar sus workflows.

## Pruebas

Se simula el rechazo exacto `1500/1611248` y se comprueba una única solicitud con el enlace original, resultado de error e identificador remoto vacío. También se comprueba que los éxitos anteriores no se reenvían, incluso si hay un error posterior, y que los errores de red, permisos, límites o recibos ausentes no generan publicaciones alternativas. Las pruebas no contactan con Meta.
