# Canvis de titular i duplicats a xarxes — 5 d'octubre de 2026

La revisió manual iniciada a les 10:47:56 CEST acabà correctament a les
10:51:19 CEST. Les 40 fonts respongueren sense errors. El botó es mantenia
desactivat mentre treballava, tal com estava previst.

La comprovació del registre detectà un duplicat de Facebook: Sa Veu canvià el
titular «La Mallorca 5000 té accent solleric» per «La Mallorca 5.000 té accent
solleric», conservant el mateix URL:
`https://saveu.cat/noticies/la-mallorca-5000-te-accent-solleric/`.
L'identificador inclou el titular i canvià de `1d8981f4f80cb5cc9e88` a
`1901aa629cadf937e002`. Facebook els rebé a les 10:44:52 i 10:51:15 CEST.

La deduplicació social comprova ara també **font + URL original + plataforma**
amb un èxit confirmat. S'aplica en preparar la cua, just abans de cada
enviament i a la vista prèvia d'Administració. Es mantenen els identificadors
existents, els criteris de recopilació, l'horari i els enviaments manuals.
El mateix enllaç continua podent aparèixer com a informació d'una altra font;
un èxit de Facebook no impedeix l'enviament pendent d'Instagram.

Els dos enviaments manuals d'Instagram segueixen pendents i la pausa de Meta
es manté fins a les 12:23:27 CEST. No s'esborren publicacions ja enviades a Meta.

Validació: 76 proves Python i quatre conjunts JavaScript correctes, incloent-hi
canvi de titular amb el mateix URL, una altra font i separació per plataforma.
Les proves no envien publicacions reals.
