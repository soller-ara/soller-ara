# Respaldo de la revisión de fuentes · 19 de octubre de 2026

## Funcionamiento

El Worker de Administración v0.72 incorpora un manejador programado. Cloudflare comprueba cada 15 minutos la fecha `sources_checked_at` del JSON del repositorio. Si han pasado más de dos horas, consulta las últimas ejecuciones del recopilador e intenta activar **el mismo** `update-sources.yml`, con la entrada `watchdog: true`.

No usa `fetched_at`, que puede cambiar al publicar manualmente. No cambia el cron horario `7 * * * *`, los filtros, la selección de fuentes ni los límites y confirmaciones sociales. No publica directamente en Meta. Reutiliza el token GitHub ya configurado en el Worker para consultar Actions y solicitar ejecuciones; no necesita tokens nuevos, almacenamiento adicional ni acceso a los secretos de Meta.

Se abstiene si los datos están recientes, la fecha falta/no es válida, hay una revisión activa o en espera, o consta un intento en la última hora. Ante un fallo de lectura no supone que haya que publicar. Limita las peticiones de lectura a 15 segundos y la solicitud de ejecución a 20 segundos. Las comprobaciones concurrentes de una misma instancia comparten la operación; si una respuesta de solicitud es incierta no la vuelve a enviar inmediatamente.

La protección final frente a carreras está en GitHub: la ejecución solicita el bloqueo compartido existente `soller-ara-social-publish` y vuelve a leer `main`. Solo las solicitudes del respaldo realizan esta comprobación previa. Si otra revisión ya actualizó los datos, **se omite todo el trabajo de recopilación, despliegue y envío social**. Las ejecuciones horarias, por cambios de configuración y el botón manual continúan funcionando normalmente. Una fecha inválida en esta comprobación aborta la solicitud del respaldo.

Este mecanismo reduce la dependencia del arranque programado de GitHub. No puede resolver una caída de GitHub, la revocación del token o fallos del propio Cloudflare; los controles existentes siguen mostrando la antigüedad real de los datos.

## Activación en Cloudflare

Guardar el código en GitHub no actualiza por sí solo el Worker que se gestiona manualmente en Cloudflare.

1. Abrir el Worker existente **soller-ara-admin** en Workers & Pages y sustituir su código por el archivo completo [worker/admin-worker.js](../worker/admin-worker.js). Desplegar. Mantener sus variables y secretos existentes.
2. En **Settings → Triggers → Cron Triggers**, añadir una única expresión `*/15 * * * *`. No añadir copias si esa expresión ya existe. La configuración del repositorio `worker/wrangler.toml` ya contiene ese cron para despliegues con Wrangler.
3. Consultar `/health`: debe indicar versión **0.72** y capacidad **collection_watchdog**. Esto confirma el código disponible, pero **no certifica que el cron esté activado**.
4. En los eventos/logs de Cloudflare, comprobar un evento `COLLECTION_WATCHDOG`. Los estados esperados son `fresh`, `already_running`, `recent_attempt` o `dispatched`. Cloudflare documenta que un cron nuevo puede tardar hasta 15 minutos en propagarse. Si los datos están recientes, el resultado correcto es `fresh`, sin solicitar ni publicar nada.

Para pausar solo este respaldo se puede retirar el cron o configurar la variable de texto `COLLECTION_WATCHDOG_ENABLED` con valor `false`. El horario de GitHub y el botón manual siguen funcionando.

## Pruebas

- 133 pruebas Python y 10 baterías JavaScript superadas localmente.
- Worker con datos recientes y límite exacto de dos horas; publicación manual que cambia solo `fetched_at`; horas con zona; fechas inválidas, ausentes o futuras.
- Ejecuciones activas, pendientes y recientes fallidas; errores de proveedor; respuestas inválidas; timeout de solicitudes; llamadas concurrentes y espera tras una respuesta incierta.
- Solicitud marcada exclusivamente para `update-sources.yml`, sin llamadas a Meta ni secretos en logs.
- Comprobación de GitHub que omite una solicitud atrasada si una revisión normal ya ha renovado la fecha; programación y bloqueo existentes preservados.

Las pruebas usan respuestas simuladas y datos temporales. No se manipulan fechas en producción ni se crean publicaciones de prueba para forzar el respaldo.

Documentación oficial:
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
