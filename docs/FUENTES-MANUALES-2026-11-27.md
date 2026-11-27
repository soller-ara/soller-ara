# Incorporación de fuentes · 27 de noviembre de 2026

Tras la aprobación de las candidatas de la revisión semanal, se incorporan tres fuentes a **Administración → Fuentes → Fuentes para revisión manual**:

| Fuente | Acceso | Revisión necesaria |
| --- | --- | --- |
| Fundació Mallorca Literària · Agenda | https://www.mallorcaliteraria.cat/ca/agenda | Elegir actividades de Sóller y entorno y distinguir la fecha del acto de la fecha del anuncio. |
| Consell de Mallorca · Agenda local | https://www.conselldemallorca.es/agenda | Comprobar localización y vigencia en la ficha de la actividad, incluidas las del Museu de la Mar del Port de Sóller. |
| CEIP Es Fossaret · Sóller | https://sites.google.com/ceipesfossaret.com/inici/ | Verificar los avisos del centro; el curso escolar o la presencia de una página permanente no acreditan una fecha de publicación. |

## Uso

1. **Revisar web** abre la fuente en otra pestaña.
2. Elegir la noticia o actividad concreta y copiar su enlace, comprobando el vínculo local y las fechas originales.
3. **Preparar enlace** abre un borrador en «Enlaces de redes», con el nombre de la fuente y la categoría preparados. El campo del enlace queda vacío para pegar la ficha concreta, sin confundir la portada de una web con una publicación.
4. Revisar el formulario y elegir los destinos antes de publicar. Facebook e Instagram empiezan desmarcados. Si ya hay una edición abierta se conserva; sustituir un borrador exige la confirmación habitual.

## Modo de incorporación

La verificación de las páginas individuales de las dos agendas ha encontrado fechas de actos, sin una fecha original de publicación fiable para el recopilador. Es Fossaret mantiene contenidos de varios cursos en Google Sites. Se incorporan como canales manuales utilizables, sin inventar fechas ni presentar páginas antiguas como noticias nuevas.

El catálogo se guarda en `manual_sources` de `sources.json`, separado de las 60 fuentes automáticas. El recopilador recorre únicamente `sources`: estas tres referencias no generan publicaciones, no se cuentan como feeds correctos o erróneos y no afectan a la selección automática para redes. Las métricas de Fuentes distinguen «Fuentes automáticas» de «Consulta manual».

Se mantiene la atribución y la política de titular y enlace; no se descargan fotografías ni se reproducen textos completos. La incorporación no declara que exista permiso de lectura de Meta para los perfiles de estas entidades.

Administración **0.94.4**, con versión de caché actualizada para el módulo de Fuentes. No requiere modificar el Worker de Cloudflare. La comprobación de entrega se realiza sobre los archivos publicados y la validación del repositorio; no se crean publicaciones de prueba.

Validación previa al despliegue: 29 comprobaciones JavaScript y 176 pruebas Python superadas. Se comprueba que el catálogo manual no se recopila ni afecta al estado de los feeds, el tratamiento seguro de los enlaces y la conservación de una edición o borrador existente. La prueba visual utiliza datos locales: tarjetas, enlaces y preparación del borrador revisados en escritorio y anchuras de 320/390 px, sin envíos externos.
