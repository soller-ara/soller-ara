# Ayuda editorial en Enlaces de redes · Administración v0.93.4

El formulario incorpora un bloque **Ayuda para el titular y el resumen** debajo de los campos de texto. Muestra el contador del titular respecto al límite existente de 180 caracteres y el número de caracteres del resumen. Ofrece sugerencias orientativas cuando el titular es muy breve, genérico o una dirección web, el resumen repite el titular o contiene solo una URL, o falta identificar la cuenta original.

Las **Pautas de redacción** se despliegan a petición: titular concreto, resumen propio de una a tres frases con los datos confirmados y atribución de las opiniones. Las sugerencias no certifican que los hechos sean correctos o que el tono sea neutral; la revisión corresponde a la persona que publica.

La ayuda es opcional. No modifica el texto, los requisitos de los campos, los destinos ni la casilla Ara; no añade confirmaciones ni impide publicar. Un enlace destinado solo a la web puede seguir enviándose sin titular ni resumen. Para Instagram se conserva la validación existente que exige ambos. La edición conserva la desactivación de Instagram y solo actualiza la web.

La guía funciona con reglas locales y no consulta servicios externos ni genera texto. Sus contadores y consejos se actualizan al escribir, cambiar el destino, cargar una publicación para editarla, cancelar la edición y limpiar el formulario tras guardar. Las recomendaciones idénticas no se vuelven a anunciar a los lectores de pantalla por cada carácter escrito.

## Comprobación

`tests/test_editorial_guide.mjs` carga la guía junto con los manejadores reales de Administración. Comprueba que los consejos no alteran el borrador, los requisitos, Ara ni los destinos; que un enlace web sin texto sigue llegando a la confirmación; que Instagram mantiene sus requisitos; y que los avisos orientativos no bloquean datos válidos. También prueba la sincronización al editar, cancelar y restablecer el formulario y la ausencia de peticiones externas.

`tests/fixtures/editorial-guide.html` permite comprobar el formulario actual en escritorio y en marcos de 320 y 390 píxeles. Obtiene únicamente el HTML público del formulario y carga la guía; no carga el cliente de Administración, no usa credenciales y desactiva el botón de envío.

El cambio se despliega desde GitHub Pages. La portada conserva v0.90.5 y el Worker v0.72; no requiere actualizar Cloudflare.
