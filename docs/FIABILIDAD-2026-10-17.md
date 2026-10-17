# Prioridad 1: fiabilidad de despliegue y actualización

## Cambios

- Se retira el disparador `workflow_run` que volvía a desplegar al terminar cada recopilación, aunque esa recopilación ya había desplegado la web.
- El despliegue genérico ignora los cambios limitados a la configuración y scripts que ya activan y despliegan desde `update-sources.yml`. Los cambios mixtos que también afectan a otros archivos pueden seguir solicitando ambos flujos: se mantiene la cola compartida para serializarlos.
- Los cinco flujos que despliegan la web usan una acción común con hasta tres intentos del mismo artefacto. Espera 20 y 40 segundos entre intentos; cada intento tiene un límite de cuatro minutos. Si todos fallan, el despliegue termina con error y no se ejecutan los pasos sociales que dependan de él. No se reejecuta un flujo de publicación completo.
- Administración 0.93.3 muestra una franja en todos los módulos con la fecha real de revisión, en hora de Mallorca. Avisa si han transcurrido más de dos horas, si la fecha falta o no es válida, si la lectura falla o si la última revisión registra fuentes con incidencias.
- La franja se comprueba cada minuto mientras Administración está abierta, visible y con sesión iniciada, y al volver a la pestaña. No utiliza `fetched_at`: una publicación manual no cuenta como revisión automática de fuentes.

## Alcance y límites

Se conserva `7 * * * *`, la cola compartida sin cancelación y la configuración de fuentes y redes. No se cambia el Worker ni se añaden publicaciones de prueba a producción. No hace falta actualizar Cloudflare.

El aviso es visible en Administración; no envía correos ni notificaciones externas. GitHub puede retrasar o descartar una ejecución programada. Este cambio hace visibles los retrasos, pero no añade un segundo programador independiente ni garantiza intervalos exactos de una hora.

## Validación previa

114 pruebas Python y ocho suites JavaScript correctas. Nuevas comprobaciones de antigüedad, fecha manual independiente, hora de Mallorca, fechas ausentes/futuras, incidencias por fuente, recuperación tras refrescar, errores de lectura y suspensión del sondeo con sesión cerrada o pestaña oculta. Todos los YAML y comandos shell de los flujos se han comprobado localmente.

La recuperación ante un rechazo real de Pages se comprobará cuando el proveedor devuelva uno: no se provoca una incidencia ni se publican noticias ficticias para forzarlo. El despliegue y la recogida reales posteriores al cambio permiten verificar el funcionamiento normal del nuevo camino.
