# Respaldo de recopilación tras una hora sin revisión

24 de noviembre de 2026. Worker de Administración v0.73.

## Cambio acotado

El respaldo considera atrasada una revisión cuando `sources_checked_at` tiene **más de 60 minutos**, en lugar de dos horas. Se aplica el mismo umbral en el Worker y en `scripts/check_collection_watchdog.py`, que vuelve a leer `main` después de obtener el bloqueo compartido de GitHub.

El cron de Cloudflare continúa en `*/15 * * * *` y el horario principal de GitHub en `7 * * * *`. En condiciones normales, el respaldo detectará una revisión omitida entre los 60 y 75 minutos desde la última recopilación real. Después hay que sumar el tiempo de cola y de lectura de las fuentes; no se garantiza una actualización pública exactamente cada 60 minutos.

La respuesta pública `/health` identifica el Worker v0.73 y añade `watchdog_stale_after_minutes: 60` para comprobar qué versión está desplegada. Las capacidades existentes se conservan.

## Protecciones conservadas

- No se usa `fetched_at`: una publicación manual no retrasa la revisión real de fuentes.
- Se conserva la comprobación de ejecuciones activas, la pausa de una hora entre intentos y la agrupación de comprobaciones simultáneas en el Worker.
- El bloqueo compartido `soller-ara-social-publish` y la segunda lectura de antigüedad impiden recopilar o publicar otra vez si una ejecución anterior ya actualizó los datos.
- Fechas inválidas, fallos de lectura y respuestas no verificables siguen sin provocar peticiones de publicación a ciegas.
- No cambian fuentes, filtros, selección, límites de publicaciones, comprobantes sociales, credenciales, cron ni las opciones manuales. El presupuesto persistente de Free News API continúa limitado a 2.700 solicitudes mensuales.

## Validación y activación

Las pruebas comprueban el límite exacto de una hora, su equivalencia con zonas horarias, el rescate entre una y dos horas, la independencia de las publicaciones manuales, la espera de procesos activos, los intentos repetidos, errores de los proveedores y el caso de un respaldo en cola que se convierte en una operación vacía tras una revisión normal. Todas las peticiones de estas pruebas están simuladas.

La validación completa supera 169 pruebas Python, las 16 suites JavaScript y las 12 comprobaciones de sintaxis. No se alteran fechas reales ni se crean noticias de prueba.

La parte de GitHub queda preparada al actualizar el repositorio. El cambio del disparador externo requiere desplegar el archivo completo `worker/admin-worker.js` en el Worker existente `soller-ara-admin`, conservando sus variables, secretos y su cron. No hay que crear un Worker ni un cron nuevos. Hasta desplegar v0.73, el respaldo externo anterior seguirá esperando dos horas, aunque la comprobación de GitHub ya acepte una hora.

Comprobar `/health` después del despliegue: `ok: true`, `version: "0.73"`, `watchdog_stale_after_minutes: 60`. Esto acredita el código desplegado; los eventos `COLLECTION_WATCHDOG` y las ejecuciones de GitHub sirven para comprobar la actividad del cron.

Para volver al comportamiento anterior, restaurar Worker y comprobación de GitHub desde el commit `f8e8a0eeebe28d8f48143401844b59374b4d1d5e`. El respaldo puede pausarse con la opción existente `COLLECTION_WATCHDOG_ENABLED=false`, sin detener el horario de GitHub ni el botón manual.
