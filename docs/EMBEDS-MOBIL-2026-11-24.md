# Incrustacions i navegació mòbil — 24 de novembre de 2026

## Diagnòstic

Les targetes oficials i els reproductors són documents de tercers dins un iframe. A 390 px, la mostra de Sa Veu té 586 px de contingut dins una finestra de 336 px: el gest damunt la vista prèvia desplaça aquest document i pot retenir la navegació de Sóller Ara. `overflow: hidden` al contenidor exterior no impedeix que el document interior consumeixi el gest.

## Canvi de presentació, v0.90.8

- En pantalles de fins a 760 px o amb un punter tàctil sense hover, les incrustacions del feed deixen passar el gest a la pàgina per defecte.
- «Interactua amb la publicació» activa expressament el contingut del proveïdor. Mentre està activat, «Continua desplaçant la pàgina» queda fixat a la part inferior i respecta l'àrea segura del dispositiu.
- Només hi pot haver una incrustació activa. Tornar a la navegació desactiva la captura del gest, sense reconstruir l'iframe, canviar-ne l'URL ni reiniciar el reproductor.
- S'inclouen les targetes oEmbed i els embeds de Facebook, Instagram, X, YouTube, TikTok i Vimeo. Les fotografies natives i els cartells propis no afegeixen aquest control.
- En escriptori ample, les incrustacions continuen sent interactives i els nous controls no es mostren. Les etiquetes estan traduïdes a català, castellà i anglès.

No es modifica el recopilador, els scripts d'enviament a xarxes, els permisos de Meta, les fonts, els límits, la moderació, les dades ni els registres socials. La versió del CSS i JavaScript i el peu de la portada passen conjuntament a 0.90.8.

## Instagram i fotografies de tercers

La publicació d'Instagram exigeix un fitxer d'imatge o vídeo; no accepta una targeta HTML oEmbed com a contingut del feed. L'oEmbed d'Instagram és per mostrar contingut d'Instagram en webs i aplicacions, no per inserir articles externs dins Instagram.

El codi actual de la distribució automàtica genera una targeta pròpia i la publica com a JPEG. Les catorze fonts `official_oembed` no tenen una autorització registrada per republicar les fotografies: nou indiquen `link_only_no_media_license`, tres `permission_pending` i dues `official_party_source`. Aquestes últimes identifiquen la font oficial d'un partit, no una llicència d'imatge. No s'extreuen fotografies dels iframes ni es converteixen les incrustacions en captures per enviar-les a Instagram. Es conserva la distribució existent.

La confirmació d'Instagram del 24/11/2026 a les 11:08 Europe/Madrid per una notícia del Setmanari acredita un enviament en el compte propi. Aquesta capacitat és independent de poder llegir comptes aliens o reutilitzar-ne les imatges.

Documentació de Meta contrastada el 24/11/2026:

- [Content Publishing](https://developers.facebook.com/documentation/instagram-platform/content-publishing)
- [IG User Media](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media)
- [Instagram oEmbed](https://developers.facebook.com/documentation/instagram-platform/oembed)

## Comprovacions

- Comparació al navegador de la versió anterior i la corregida, amb el mateix article real de Sa Veu a 390 px. Abans, l'interior de l'embed es desplaça de 0 a 250 px; amb la correcció es manté a 0 i avança la pàgina exterior.
- Prova de la vista de 320 px: no apareix desbordament horitzontal; el control de retorn queda dins el viewport. A 390 px, el botó també es manté fix i visible.
- Activació i desactivació del reproductor oficial de YouTube: la mateixa URL conserva el comportament esperat i recupera la navegació de la pàgina.
- Vista d'escriptori de 1363 px: l'iframe manté `pointer-events: auto` i els controls mòbils estan ocults.
- Superades 16 bateries JavaScript, 12 comprovacions de sintaxi i 150 proves Python. La prova nova cobreix l'activació expressa, una sola vista activa, el retorn, els tres idiomes, la preservació de l'iframe, els embeds processats per SDK i les imatges natives. També es conserva la prova de compartir publicacions afegides amb «Veure més».

Les proves d'interacció s'han fet en vistes de navegador amb amplada mòbil, sense publicar entrades de prova ni enviar missatges.
