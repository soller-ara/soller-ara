# Sóller Ara

Projecte públic i sense ànim de lucre per reunir informació local de Sóller en un sol lloc, mantenint sempre visible la font original i l'accés a la publicació d'origen.

## Versió

Les versions corresponen a components diferents:

| Component | Versió |
| --- | --- |
| Administració | **0.93** |
| Portada pública | 0.89 |
| Worker de Cloudflare | 0.71 |
| Recopilador | 0.61 |

La revisió de fiabilitat, els errors corregits, les proves i l'estat de les fonts estan documentats a [REVISION-2026-10-07.md](docs/REVISION-2026-10-07.md).

## Publicacions pròpies i enllaç directe a xarxes

- Cada publicació pròpia de Sóller Ara genera una pàgina individual a `/noticies/<id>.html`.
- Aquesta pàgina inclou metadades Open Graph perquè Facebook pugui mostrar una previsualització amb el titular i la imatge.
- Facebook publica l'entrada amb l'enllaç directe a la notícia individual, no a la portada.
- Instagram rep la mateixa URL dins el text de la publicació. La capacitat que aquest URL sigui clicable depèn de les funcions disponibles al compte d'Instagram; Meta està provant enllaços clicables en captions per a determinats comptes Meta Verified.
- Facebook i Instagram estan desmarcats per defecte al workflow manual: només s'envia als destins seleccionats expressament.
- La distribució automàtica segueix la configuració de `social_distribution.json` i el registre conserva els enviaments confirmats i els reintents pendents d'Instagram.

### Enllaç estable per Instagram

Sóller Ara publica també `/enllacos.html`, una pàgina que llegeix `data/manual_posts.json` i mostra les darreres publicacions pròpies ordenades de més nova a més antiga.

URL preparada per utilitzar una sola vegada a la bio d'Instagram:

`https://soller-ara.github.io/soller-ara/enllacos.html`

Cada targeta d'aquesta pàgina apunta a la URL individual de la notícia. El caption d'Instagram conserva també l'URL exacta de la notícia, encara que la seva clicabilitat depèn de les funcions habilitades al compte.

## Novetats de la v0.68

- Cloudflare Web Analytics s'incorpora a les pàgines públiques i a les notícies pròpies actuals i futures.
- Administració queda exclosa; es respecten Do Not Track i Global Privacy Control.
- La política de privacitat explica les mètriques. El recompte comença des de l'activació i no identifica persones úniques.

## Novetats de la v0.67

- El logotip de la capçalera recorre suaument els tons del color actual, l'alba, el dia, el capvespre i la nit.
- L'animació dura 32 segons, manté el símbol llegible i s'atura automàticament quan el dispositiu té activada la reducció de moviment.
- Els avatars i les targetes socials continuen sent estàtics per evitar retalls o incompatibilitats a Facebook i Instagram.

## Novetats de la v0.66

- Sa Veu de Sóller conserva la previsualització oficial publicada i servida des del mateix domini del mitjà, sense copiar ni allotjar a Sóller Ara la fotografia o l'extracte.
- La targeta manté visible l'accés a la publicació original i deixa el control del contingut incrustat en mans del mitjà d'origen.

## Novetats de la v0.65

- Els mitjans de comunicació, inclosa Sa Veu de Sóller, es mostren només amb titular, data, font i enllaç original; no se'n reprodueixen fotografies, extractes ni finestres incrustades sense autorització.
- La web informa de manera visible que la recopilació està assistida per intel·ligència artificial i compta amb supervisió humana.

## Novetats de la v0.64

- La pestanya del navegador incorpora el logotip de Sóller Ara com a favicon i el manifest disposa d'icones per a instal·lació en mòbil.
- La portada incorpora títol i descripció millorats, URL canònica, metadades socials i dades estructurades de l'organització i del lloc web.
- S'afegeix un mapa del lloc per facilitar la descoberta de les pàgines públiques pels cercadors.
- A les noves publicacions d'Instagram, l'adreça de la informació original apareix immediatament després del titular i la font, abans del resum que la plataforma pot ocultar.

## Novetats de la v0.63

- Es prepara un avatar específic per als perfils de Facebook i Instagram, amb fons verd continu i marge segur per al retall circular.
- La capçalera i el peu de la web incorporen accessos directes als perfils propis de Sóller Ara a Instagram i Facebook.
- El logotip general de la web i les targetes socials no es modifica; l'adaptació circular queda reservada als avatars dels perfils.

## Novetats de la v0.62

- Les targetes noves d'Instagram utilitzen la versió web verificada del logotip i deixen de fallar per la còpia gran incompleta.
- L'URL completa de la informació original continua inclosa al text de cada publicació d'Instagram, encara que la plataforma no la faci clicable.
- Les dues fonts d'Instagram sense permís de lectura de Meta es mantenen com a accessos oficials, sense provocar avisos falsos de recopilació.
- Les descàrregues de fonts es reintenten quan hi ha errors temporals, com el temps d'espera detectat a IB3.

## Novetats de la v0.61

- Es corregeix la càrrega incompleta del logotip a la capçalera amb una versió web optimitzada de 256 × 256 píxels.
- El logotip es precarrega, manté sempre la proporció completa i reserva la seva mida per evitar salts o retalls durant la càrrega.

## Novetats de la v0.60

- El logotip aprovat de Sóller Ara, amb muntanyes i capella, substitueix l'antic monograma provisional a la web, Administració i les noves targetes pròpies per a Instagram.
- Les publicacions anteriors no es regeneren ni es modifiquen.
- Es prepara una portada panoràmica de Facebook amb les fotografies aportades; queda fora del desplegament públic fins a confirmar-ne les llicències d'ús.
- La mesura de visites i la identitat animada dia/nit queden documentades a [PENDIENTES.md](PENDIENTES.md).

## Novetats de la v0.59

- Sa Veu, MUCBO i Can Prunera mostren una previsualització oficial allotjada per la font mitjançant `oEmbed`; Sóller Ara no copia ni allotja les fotografies.
- La inserció només s'accepta per HTTPS, en el mateix domini de la notícia i amb la ruta oficial `/embed/`.
- `og:image` no es considera una autorització de reutilització. La resta de fonts continuen sense fotografia fins que tenguin permís, llicència compatible o un mecanisme oficial d'inserció.
- La decisió i l'auditoria queden documentades a [IMAGE_PREVIEW_POLICY.md](IMAGE_PREVIEW_POLICY.md).

## Novetats de la v0.58

- Administració comprova els canvis de distribució social directament contra la versió actual del repositori, sense esperar que GitHub Pages acabi de publicar-la.
- En actualitzar la pàgina, les caselles mostren immediatament la selecció guardada i no una còpia anterior del desplegament.
- Es manté una lectura alternativa des de la web pública si GitHub limita temporalment la consulta directa.

## Novetats de la v0.57

- Totes les fonts tenen ara una decisió explícita per a Facebook i Instagram, encara que sigui «sense distribució social».
- Les fonts noves que encara no tenguin aquesta decisió apareixen advertides al panell i fan fallar la validació abans del desplegament.
- IB3 Notícies · YouTube queda autoritzada per a les dues xarxes; les altres fonts incorporades recentment continuen recopilant per a la web però queden sense enviament social fins que s'activin des d'Administració.

## Novetats de la v0.56

- Administració permet pausar o reprendre la distribució automàtica sense aturar la recopilació de la web.
- Cada font té una selecció independent per a Facebook i Instagram. Els canvis es validen de nou abans de guardar-se i abans de cada enviament.
- S'incorpora una vista prèvia de la següent candidata amb el text de Facebook i la targeta pròpia d'Instagram; la vista prèvia no publica contingut.
- El panell espera la confirmació de GitHub abans de donar el canvi per guardat.
- Queda documentat a [PENDIENTES.md](PENDIENTES.md) l'estudi de les imatges Open Graph dels enllaços externs, condicionat a la comprovació tècnica i de drets.

## Novetats de la v0.55

- Desactivar una font atura les consultes noves i conserva les publicacions ja recopilades, amb les dates originals i dins del termini d'antiguitat configurat.
- Les publicacions conservades continuen subjectes a moderació. Es pot ocultar i restaurar una entrada amb la font desactivada, i tornar-la a activar reprèn la recopilació.
- Administració mostra el nombre de publicacions conservades de cada font desactivada. Aquestes fonts no es compten com a errors de recopilació ni s'envien a les xarxes automàticament.
- Es comprova el cicle complet amb dades de prova. Un fitxer anterior il·legible atura l'actualització abans de sobreescriure les entrades que cal conservar.

## Novetats de la v0.54

- Es corregeix l'absència del límit de 60 dies a Sóller 2010: els avisos antics que continuen al seu llistat ja no entren a la recopilació de Sóller Ara.
- S'aplica també el límit que faltava a les fonts inicials Ajuntament de Sóller, Sa Veu i Setmanari Sóller. Es conserven les dates originals i els terminis específics ja configurats per altres fonts.
- Una prova de regressió comprova el cas real dels avisos del 24 de març i del 6 d'agost, amb el rellotge fixat al 17 de setembre de 2026.

## Novetats de la v0.53

- S'afegeixen 12 fonts: 10 canals públics de YouTube d'institucions, associacions, un club esportiu i un creador cultural, més els feeds dels museus MUCBO i Can Prunera.
- Màxim 60 dies d'antiguitat; els canals d'abast insular tenen un filtre local sobre el títol, sense coincidències artificials pel nom del compte.
- Vídeos servits pel reproductor oficial de YouTube. Dels feeds dels museus només es mostren titular, data, font i enllaç.
- El panell distingeix institucions, associacions, clubs i creadors, i explica quan una font funciona però no té contingut recent que compleixi els filtres.
- Procedència i decisions de revisió documentades a [SOURCES_REVIEW.md](SOURCES_REVIEW.md).

## Novetats de la v0.52

- S'elimina l'accés duplicat «Autobusos TIB» i «TIB a Sóller» queda agrupat dins «Mobilitat ara».
- S'incorpora el canal oficial d'IB3 Notícies a YouTube, filtrat perquè només entrin vídeos relacionats amb Sóller i el seu entorn.
- Els vídeos es mostren amb el reproductor oficial de YouTube en mode de privacitat millorada i conserven l'enllaç a l'original.
- Es documenta el tractament de les previsualitzacions automàtiques dels enllaços a les xarxes socials.

## Novetats de la v0.51

- Distribució automàtica activada per Facebook i Instagram: màxim 3 notícies de les darreres 6 hores, una per font i execució.
- Les targetes pròpies es despleguen a GitHub Pages abans d'enviar-les a Instagram.
- El registre conserva els resultats encara que una xarxa falli; no es repeteixen enviaments confirmats.
- Fonts desactivades, moderació i límits es tornen a comprovar abans d'enviar.
- Administració llegeix dades públiques sense consumir la quota de la API de GitHub.
- El panell mostra l'últim enviament o error per xarxa i la versió v0.51 també apareix al peu de la web.

## Novetats de la v0.39

- El nou token Meta ha estat validat en mode de només lectura.
- Facebook: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts` i `business_management` concedits; la pàgina Sóller Ara retorna `CREATE_CONTENT`.
- Instagram: `instagram_basic` i `instagram_content_publish` concedits; `@soller.ara` es detecta correctament.
- Cada publicació pròpia genera una **URL individual permanent** dins `/noticies/`.
- Si no s'aporta fotografia, Sóller Ara genera una targeta social **JPEG 1080×1350** amb marca, categoria i titular.
- La pàgina individual incorpora Open Graph perquè Facebook pugui construir la previsualització des de la notícia concreta.
- Abans de publicar a Meta, el workflow comprova que la notícia i la imatge ja són públiques a GitHub Pages.
- Facebook publica l'enllaç directe a la notícia individual.
- Instagram utilitza la mateixa imatge i inclou la URL individual al text; la clicabilitat del text depèn de les funcions disponibles al compte.
- Existeix un workflow de validació que prova tota la generació sense publicar res a xarxes.

## Novetats de la v0.38

- Sóller Ara admet ara **publicacions pròpies** persistents, que no desapareixen quan s'actualitzen les fonts externes.
- S'afegeix el workflow **Sóller Ara · publicar contingut propi** per crear una entrada pròpia i, opcionalment, publicar-la també a les xarxes pròpies.
- Facebook pot publicar text o text + imatge.
- Instagram es pot seleccionar quan la publicació té una imatge pública; si no hi ha imatge, el flux ho impedeix per evitar una publicació incompleta.
- Les credencials de Meta continuen guardades únicament com a secrets de GitHub i mai s'envien al navegador.
- Les targetes pròpies no mostren l'enllaç «Original», perquè Sóller Ara és la font original.

## Novetats de la v0.37

- TIB mostra ara el títol complet de l'avís i intenta extreure el primer paràgraf informatiu de la pàgina oficial.
- Consell de Mallorca passa a revisar les primeres pàgines de **Totes les notícies**, amb prefiltre per URL abans de descarregar articles.
- El prefiltre local inclou Sóller, Fornalutx, Biniaraix, Serra de Tramuntana, Fàbrica Nova i Torre Picada.
- Es manté el fallback específic per HTML Liferay.

## Novetats de la v0.36

- TIB i Consell de Mallorca deixen de dependre d'un índex extern i es tornen a consultar directament des dels seus webs oficials.
- El recopilador utilitza ara una identificació de navegador compatible amb portals Liferay que serveixen contingut diferent segons el client.
- TIB llegeix els avisos `/es/w/...` i el Consell les notícies de Sala de Premsa, sempre filtrant per rellevància local.

## Novetats de la v0.35

- TIB passa a consultar-se mitjançant un índex de metadades sobre el domini oficial `tib.org`, evitant els problemes del HTML dinàmic de Liferay.
- S'afegeix **Consell de Mallorca** com a font oficial filtrada per Sóller, Port de Sóller, Fornalutx, Biniaraix i Serra de Tramuntana.
- Es crea `META_APP_REVIEW.md` amb el cas d'ús, estat tècnic, criteri de minimització de dades i material pendent per sol·licitar la revisió de Meta.

## Novetats de la v0.34

- S'incorporen els **avisos oficials TIB** relacionats amb Sóller, Port de Sóller, Fornalutx i les línies 203, 204, 231 i 232.
- Els avisos TIB entren directament al feed com a **Alertes**, sense crear un bloc separat que dupliqui informació.
- Es reforça la classificació per titular: detencions, robatoris, accidents, protestes i manifestacions es mantenen a **Notícies** encara que les metadades de la pàgina contenguin paraules d'altres categories.
- Es reforça també la detecció de contingut cultural (Art Sóller, artistes, exposicions, teatre, concerts i havaneres).

## Novetats de la v0.33

- S'elimina de la portada el bloc separat **Emergències i meteorologia** per evitar duplicar avisos que ja entren al feed.
- AEMET continua com a font automàtica: els avisos meteorològics no desapareixen, simplement deixen de tenir un bloc duplicat.
- S'incorporen **Diario de Mallorca**, **Última Hora** i **Mallorca Directo**.
- Diario de Mallorca es consulta mitjançant un índex de metadades de notícies que conserva el **titular, la data i l'URL original de diariodemallorca.es**; això evita la limitació del seu RSS, que només manté una finestra molt curta.
- Última Hora i Mallorca Directo es consulten des de les seves pàgines específiques de Sóller.
- En els mitjans de comunicació es manté la política de mostrar **titular, data i enllaç original**, sense copiar el cos de la notícia.

## Novetats de la v0.32

- S'incorporen **IB3 Notícies** i **dBalears** com a noves fonts automàtiques. IB3 es consulta directament pel seu cercador web de «Sóller» perquè el seu RSS general no sempre reflecteix les notícies més recents.
- Ambdues fonts generals es filtren abans de publicar perquè només entrin peces relacionades amb Sóller, Port de Sóller, la Vall de Sóller o la Serra de Tramuntana.
- Per als mitjans de comunicació es manté la política conservadora: **titular, data i enllaç original**, sense copiar el cos de la notícia.
- La recopilació continua executant-se cada hora mitjançant GitHub Actions i no depèn de Meta.
- La configuració queda preparada per continuar afegint RSS externs sense canviar la interfície de l'app.

## Novetats de la v0.31

- S'afegeix el canal RSS oficial de notícies del **Govern de les Illes Balears**.
- La font es filtra perquè només entrin peces que mencionin Sóller, Port de Sóller o Serra de Tramuntana.
- El filtre per paraules clau queda disponible per afegir més fonts generals sense omplir la portada de contingut no local.
- Els RSS poden configurar ara un `max_items` propi per revisar més entrades quan la font és molt àmplia.
- Aquesta via no depèn de Meta i manté el projecte operatiu encara que l'accés a contingut social públic continuï pendent d'App Review.

## Novetats de la v0.30

- La prioritat passa de publicar a **recopilar informació**.
- Nova prova de només lectura per comprovar si l'accés actual de Meta permet:
  - cercar publicacions recents amb `#soller`;
  - llegir publicacions que etiquetin `@soller.ara`.
- La prova s'executa automàticament una vegada en pujar aquesta versió i també es pot llançar manualment.
- Business Discovery de comptes concrets continua separat i pendent d'accés avançat.
- Cap contingut social de tercers es publica automàticament a Sóller Ara durant aquesta prova.

## Novetats de la v0.29

- Nou workflow manual **Meta · publicar prova Facebook**.
- Requereix escriure exactament `PUBLICAR` abans d'executar-se.
- Publica una imatge pròpia de Sóller Ara a la pàgina Facebook **Sóller Ara**.
- Utilitza el Page Access Token obtingut durant l'execució; no s'emmagatzema ni s'imprimeix.
- Cap actualització automàtica pot activar aquesta publicació.

## Novetats de la v0.28

- Confirmada la primera publicació real a Instagram `@soller.ara` des de GitHub Actions.
- Nou workflow manual **Meta · prova privada Facebook**.
- La prova de Facebook és només lectura: comprova `pages_manage_posts` i la tasca `CREATE_CONTENT` sense publicar res.
- Cap token ni Page Access Token s'imprimeix als logs.

## Novetats de la v0.27

- La imatge de prova d'Instagram es substitueix per un JPEG estàndard **1080 × 1080**, RGB.
- Nova URL `assets/meta-test-v2.jpg` per evitar qualsevol caché del fitxer anterior.
- No es canvien tokens ni permisos de Meta.

## Novetats de la v0.26

- La publicació d'Instagram obté primer el **Page Access Token** de la pàgina Sóller Ara.
- Les crides `/media`, estat del contenidor i `/media_publish` utilitzen aquest token de pàgina.
- La imatge de prova es serveix des de GitHub Pages, no des de `raw.githubusercontent.com`.
- El token de pàgina només viu durant l'execució de GitHub Actions i no s'imprimeix als logs.

## Novetats de la v0.25

- Nou workflow manual **Meta · publicar prova Instagram**.
- Requereix escriure exactament `PUBLICAR` abans d'executar-se.
- Publica una imatge pròpia del projecte a `@soller.ara` mitjançant el token de sistema de Meta.
- Cap actualització automàtica pot activar aquest workflow: només funciona amb `workflow_dispatch`.
- El text es pot modificar abans d'executar la prova.

## Novetats de la v0.24

- La prova manual de Meta passa a ser **només lectura**.
- Consulta `content_publishing_limit` de `@soller.ara` per validar l'accés de publicació sense crear contenidors ni publicar res.
- Això evita errors poc clars relacionats amb la descàrrega d'imatges durant les proves.

## Novetats de la v0.23

- Nou workflow manual **Meta · prova privada Instagram**.
- La prova crea només un contenidor tècnic a `@soller.ara`; no executa `/media_publish` i, per tant, no publica res.
- Serveix per validar de forma segura el permís `instagram_content_publish` amb el token de sistema guardat a GitHub Secrets.
- S'afegeix una imatge de prova pròpia del projecte per evitar reutilitzar contingut de tercers.

## Novetats de la v0.21

- Valida el compte propi `@soller.ara` amb Meta després del descobriment automàtic.
- Els errors de Meta ara mostren només el missatge/codi segur retornat per l'API; mai el token.
- Les integracions socials encara en proves no fan aparèixer les sis fonts estables com a caigudes.
- Business Discovery continua en diagnòstic fins saber exactament quin requisit de Meta falta.

## Novetats de la v0.20

- Si `META_ACCESS_TOKEN` està configurat però `META_IG_USER_ID` encara no existeix, GitHub Actions intenta descobrir automàticament la pàgina **Sóller Ara** i el seu `instagram_business_account.id`.
- El token de Meta mai s'imprimeix als logs.
- Si el descobriment automàtic funciona, el connector d'Instagram pot continuar sense copiar manualment l'ID.
- Si Meta no permet aquesta consulta amb el token de sistema, el connector queda inactiu sense afectar la resta de fonts.

## Novetats de la v0.19

- Preparada la integració oficial d'**Instagram amb Meta Business Discovery**.
- Els comptes d'Instagram configurats podran entrar automàticament com a targetes a **Tot / Ara / Xarxes**.
- Cada targeta social conservarà data, compte, enllaç original i un resum propi de Sóller Ara.
- Les fotos, carrusels i Reels es mostraran mitjançant l'**embed oficial d'Instagram**, no descarregant els fitxers.
- GitHub Actions queda preparat per rebre les credencials com a secrets, sense exposar-les al repositori.
- Comptes inicials preparats:
  - @serveissocialssoller
  - @emergencies112_ib
- X es manté com a accés directe perquè la seva API oficial de lectura és de pagament.
- Facebook queda pendent de Page Public Content Access / permisos de Meta.
- Es manté la correcció de **Ara** de la v0.18: ordre estrictament cronològic, més recent primer.

## Activació de Instagram

Vegeu `META_SETUP.md`. Fins que no existeixin `META_ACCESS_TOKEN` i `META_IG_USER_ID`, la integració Meta es manté preparada però inactiva i no afecta les sis fonts actuals.

## Cost

Cost addicional actual de Sóller Ara: **0 €**.


## Administración v0.41

Se ha iniciado la primera versión real del área privada de Administración.

Implementado:
- interfaz `/admin/` con acceso por clave;
- módulo Panel;
- módulo Publicar;
- módulo Moderación;
- backend privado preparado para Cloudflare Workers;
- sesión temporal firmada;
- límite básico de intentos fallidos;
- disparo seguro de workflows de GitHub;
- publicación propia desde Administración;
- ocultar/restaurar publicaciones externas;
- eliminar publicaciones propias;
- ningún token o contraseña en GitHub Pages;
- validación automática de JavaScript y comprobación de secretos.

Pendiente de conexión:
- desplegar el Worker privado;
- configurar `ADMIN_PASSWORD`, `SESSION_SECRET` y `GITHUB_TOKEN` como secrets;
- introducir la URL del Worker en `admin/config.js`;
- probar login y acciones reales desde el panel.

La interfaz pública puede existir en GitHub Pages, pero ninguna acción administrativa funciona hasta que el backend privado esté conectado.
