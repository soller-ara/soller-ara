# Revisión y recuperación · 7 de octubre de 2026

Todas las horas indicadas son de Madrid.

## Bloqueo de la cola

La solicitud manual 37509470872, enviada el 6 de octubre a las 20:12,
seguía en estado `waiting` antes de ejecutar ningún paso. Retenía otra
solicitud manual y trece revisiones horarias. El entorno de GitHub Pages
permitía `main`, sin revisores ni temporizador; la causa interna de aquella
espera no está confirmada.

Con autorización del usuario se ejecutó una recuperación puntual mediante
la conexión de GitHub. A las 08:27 se cancelaron las doce revisiones antiguas,
se conservó la revisión más reciente 37581360305 y se relanzaron las dos
solicitudes manuales originales. Se conservaron sus IDs, entradas y claves de
publicación. El mecanismo temporal se retiró tras finalizar correctamente.

## Conflicto de despliegues confirmado

La revisión actual terminó correctamente. La primera solicitud manual guardó
su contenido, pero GitHub rechazó su despliegue porque otro despliegue estaba
en curso (`Deployment request failed ... due to in progress deployment`).
La segunda solicitud completó su proceso y publicó un feed que contiene ambas.

Los cinco workflows que despliegan GitHub Pages comparten ahora la misma cola,
sin cancelar trabajos ni solicitudes pendientes. Los trabajos de edición y
moderación también leen `main` al comenzar. Se mantienen el cron horario,
los criterios de las fuentes y las reglas de Facebook e Instagram.

## Estado de las fuentes y redes

La revisión recuperada registró 27 fuentes correctas y 13 feeds de YouTube con
HTTP 404. Las publicaciones de esas fuentes se conservaron; no se ha cambiado
su configuración basándose solo en este fallo. Instagram volvió a registrar
un límite de Meta y dejó pendiente un reintento, con pausa hasta las 10:30.

Las dos solicitudes manuales pendientes apuntaban al mismo original de Facebook:
una estaba en Agenda, con fuente Ajuntament de Deià; la otra en Política, con
fuente vacía. Se respetaron ambas solicitudes; no se borró ninguna publicación.

## Validación

77 pruebas de Python y las cuatro suites de JavaScript superadas. Se añadió
un contrato que comprueba que todos los workflows de Pages comparten la cola,
conservan solicitudes y utilizan `main`. Cloudflare responde y mantiene la
versión 0.71; Administración mantiene la versión 0.91.
