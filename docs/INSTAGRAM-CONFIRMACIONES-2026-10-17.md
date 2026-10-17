# Prioridad 2: confirmaciones de Instagram

La lectura de la cuenta propia `@soller.ara` del 17 de octubre revisó 228 publicaciones. De los 24 envíos que seguían pendientes, 22 tenían exactamente una coincidencia por URL original y atribución. Los dos restantes correspondían a referencias manuales eliminadas de la web, sin coincidencia en Instagram. El estado de un contenedor podía ser ERROR aunque su publicación ya existiese en la cuenta.

## Corrección permanente

`scripts/reconcile_instagram_deliveries.py` se ejecuta en la recogida habitual antes de reintentar Instagram manual y antes de publicar la cola automática. Si no quedan pendientes, termina sin consultar Meta. Con pendientes, lee la cuenta y todas sus páginas de resultados antes de modificar el registro.

- Una única coincidencia exacta confirma el envío y guarda su identificador, enlace y fecha real de Instagram.
- La fecha histórica `recorded_at` se conserva: confirmar un envío antiguo no equivale a publicarlo hoy. Se añaden `verified_at`, el estado anterior y el error anterior para mantener la trazabilidad.
- Varias coincidencias o ninguna coincidencia en una publicación existente dejan el caso pendiente. La ausencia no autoriza un reenvío desde este comprobador.
- Una referencia manual se cancela solamente si falta en los dos inventarios de publicaciones y su página individual, utiliza su URL local exacta y no tiene coincidencia en Instagram.
- Una lectura incompleta, un fallo de Meta, una cuenta distinta o un inventario inválido impiden escribir el registro. Facebook y los pasos habituales pueden continuar según su configuración; el comprobador nunca crea ni elimina publicaciones en Meta.
- Los resultados se guardan mediante el paso final existente del flujo, en la misma cola compartida con las publicaciones y la moderación.

No se modifican fuentes, permisos de Meta, límites, programación horaria, Worker ni diseño de las tarjetas. No hace falta actualizar Cloudflare.

## Pruebas

119 pruebas Python superadas, incluidas cinco nuevas sobre coincidencia exacta, atribución, URLs parecidas, ambigüedad, referencias eliminadas, idempotencia, conservación del historial y fallo de lectura sin escritura. También se comprobaron los YAML y comandos shell afectados.
