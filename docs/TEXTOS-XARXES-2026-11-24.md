# Preparació de textos i adreça de Sóller Ara a Instagram

Data: 24 de novembre de 2026. Administració v0.93.6.

## Comportament

- A «Enlaces de redes», el botó «Preparar texto automáticamente» completa només els camps buits de titular, resum i font. Utilitza publicacions que Administració ja té carregades, amb coincidència de l'enllaç original, data verificable dels darrers 60 dies i sense avisos caducats. No consulta Facebook ni Instagram per obtenir textos nous.
- La preparació és local i determinista: selecciona fins a dues frases del resum ja disponible, amb un màxim de 360 caràcters, exclusivament quan la política de la font ho permet. No incorpora cap model, clau, servei de pagament o nova dependència. Manté el text en l'idioma de la font i demana revisar-lo abans de publicar.
- Si només es permet titular, data i enllaç, prepara el titular i una referència explícita a l'original; no presenta aquesta referència com un resum. Si l'enllaç no té informació verificable guardada, deixa el formulari intacte i ho explica. Una incrustació visible no dona accés al seu text ni permís per copiar-lo.
- Es conserva el text escrit per l'usuari. Una atribució que no coincideix amb la font guardada, un enllaç ja publicat com a contingut propi o un error de preparació aturen únicament aquesta ajuda opcional. El botó no guarda, no publica, no activa Instagram, ni canvia categoria, idioma, visibilitat a Ara o permisos d'imatges.
- Les noves descripcions d'Instagram, tant manuals com automàtiques, afegeixen «Sóller Ara · https://soller-ara.github.io/soller-ara/» abans de les etiquetes. Es conserven els enllaços originals complets i l'atribució. Les targetes automàtiques pròpies també mostren la web al peu. Les publicacions antigues no es reediten.
- El límit de la descripció es manté en 2.200 caràcters. Es pot abreujar el cos opcional, indicant-ho amb punts suspensius. Si les referències obligatòries ja ocupen gairebé tot el límit, s'omet excepcionalment el peu promocional abans d'impedir un enviament que abans era vàlid. Mai es trunca silenciosament l'enllaç d'origen.
- El peu promocional no s'utilitza com a identificador d'una notícia en verificar els enviaments a Instagram. Es mantenen els comprovants, els contenidors i les proteccions existents davant respostes perdudes o pendents de verificació.

## Validació

- 163 proves Python correctes, inclosos els enviaments manuals i automàtics simulats, respostes de Meta perdudes, conciliació i absència de reenvii duplicat.
- Les 16 suites JavaScript i les 12 comprovacions de sintaxi del workflow d'Administració, correctes.
- Formulari no publicador comprovat al navegador a 320 i 390 píxels, amb dades reals ja guardades: preparació, atribució, data original i conservació dels controls. Enllaç de Facebook sense dades verificables: formulari intacte i missatge explícit.
- Targeta pròpia i descripció d'Instagram revisades visualment amb la web al peu. Eliminació conservadora d'una capçalera completa d'autor i dates de Drupal, sense eliminar dates o hores de l'activitat.
- No s'han fet publicacions de prova ni peticions a comptes socials durant les proves. Les consultes, les fonts i les regles de publicació no s'han modificat. El Worker de Cloudflare no requereix una nova versió.
