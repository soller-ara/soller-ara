# Facebook a «Enlaces de redes»

24 de novembre de 2026. Administració v0.93.7.

El formulari ofereix Facebook com a destinació opcional, inicialment desmarcada. Es pot compartir un enllaç d'Instagram o d'una altra plataforma a la web i a la pàgina pròpia de Facebook sense inventar un titular o resum. El diàleg de confirmació indica les destinacions seleccionades.

Per a referències de xarxes es comparteix l'enllaç original complet, amb l'atribució indicada i el text propi que l'usuari hagi escrit. No es descarreguen imatges ni s'extreu text de les incrustacions. Facebook decideix quina previsualització mostra. Les publicacions pròpies i els cartells autoritzats conserven l'enllaç de la seva pàgina a Sóller Ara; el workflow transmet el tipus de contingut al publicador per distingir-los.

L'edició continua actualitzant només la web. En editar es desmarquen i deshabiliten les dues destinacions socials, i la petició força tots dos indicadors a fals encara que una casella s'hagi modificat externament. Cancel·lar l'edició torna a habilitar les opcions del formulari nou. No s'han reenviat les entrades anteriors.

La llista d'enllaços mostra «Facebook: publicado» quan hi ha un resultat confirmat, o un avís si l'enviament ha fallat. L'absència d'un resultat no s'etiqueta com a error. Un èxit anterior preval sobre un error posterior. Es mantenen la comprovació de publicació ja enviada i el bloqueig del doble clic.

Validació: 168 proves Python, les 16 suites JavaScript i les 12 comprovacions de sintaxi, correctes. Inclouen l'enviament d'una referència d'Instagram amb camps de text buits, el pas de la selecció des del formulari fins al workflow, atribució i enllaç íntegres, cancel·lació, doble clic, edició sense reenviar, comprovant d'èxit sense duplicat i errors de Facebook sense fals èxit. Les peticions a Meta d'aquestes proves són simulades.

El formulari real s'ha revisat al navegador mitjançant la pàgina de comprovació que no publica, a 320 i 390 píxels. Facebook i Instagram es poden seleccionar independentment, sense desbordament horitzontal del selector de destinacions.

No cal desplegar una nova versió del Worker de Cloudflare: l'API existent ja valida i transmet l'indicador Facebook. Les fonts, la recopilació automàtica, les credencials i els registres socials no s'han modificat.

Referència tècnica: [Meta · Page Feed](https://developers.facebook.com/docs/graph-api/reference/page/feed/).
