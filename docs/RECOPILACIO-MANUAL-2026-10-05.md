# Revisió manual i reintents d'Instagram — 5 d'octubre de 2026

## Enviaments manuals ajornats

Abans del canvi, les publicacions d'Enllaços de xarxes ajornades per una pausa
de Meta quedaven al registre, però no tenien reintent automàtic. Ara cada nou
ajornament manual d'Instagram conserva una petició explícita de reintent.
La revisió de fonts existent processa aquestes peticions abans de la cua social
de fonts, fins a tres entrades per revisió i respectant la pausa compartida.

Només es reintenten enviaments seleccionats expressament. S'ometen entrades
ocultades o eliminades i qualsevol èxit anterior d'Instagram. El reintent
utilitza el contingut manual vigent, inclosos canvis de text i imatge, i no
publica de nou a Facebook. Un nou límit de Meta conserva els pendents; altres
errors queden registrats per revisar-los. No es recuperen automàticament errors
històrics sense una petició de reintent.

S'activa el reintent dels dos enllaços d'avui sobre actuacions i trànsit de la
Policia Local (`soller-ara-f40083871318b8d6` i `soller-ara-ce3feda8c0a51520`).
No es garanteix una hora de publicació: depèn que Meta admeti l'enviament.

## Cerca immediata

Administració → Fonts incorpora «Buscar y publicar ahora». El Worker 0.71
accepta la petició amb sessió vàlida i activa `update-sources.yml` a la branca
configurada. Si la mateixa revisió ja és en curs, reutilitza aquella execució.
El botó segueix l'identificador de l'execució per mostrar-ne el resultat real.
«Actualizar estado» continua servint només per consultar les dades.

El cron continua sent `7 * * * *`. Es mantenen fonts, filtres, límits, opcions
de xarxes i control de duplicats. Els dos fluxos que envien publicacions a Meta
comparteixen una cua de concurrència (`queue: max`, sense cancel·lar l'execució)
per evitar enviaments simultanis i conflictes del registre social. La creació
manual consulta la branca actual en començar una execució en espera.

El botó resta pendent d'activació fins que es desplegui el Worker 0.71 a
Cloudflare. Els reintents funcionen des de GitHub independentment del Worker.

## Validació

73 proves Python i quatre conjunts de proves JavaScript correctes. Proves amb
Meta i GitHub simulats: pausa, èxit, nou límit, moderació, eliminació, contingut
editat, registre corrupte, deduplicació, autenticació del botó, seguiment d'una
execució concreta, reutilització d'una execució activa i errors del proveïdor.
No s'envien publicacions de prova reals.
