# Publier l'extension (Firefox / AMO)

Textes prêts à coller (anglais + français) : `STORE_LISTING.md`.

Elle est autonome : aucune dépendance obligatoire envers l'application Windows.

1. Compte gratuit : https://addons.mozilla.org/developers/
2. « Submit a New Add-on » → choisir **On this site** (publique) ou **On your own** (signature seule, .xpi à héberger).
3. Envoyer `SoNiC_0TAB0-Firefox.zip` (le contenu doit être à la racine du zip : manifest.json au premier niveau).
4. Fiche : catégorie « Privacy & Security ». Description courte : « Une sortie Internet (proxy, SOCKS, Tor) par conteneur Firefox, avec test d'IP. »
5. Justification des permissions (champ « notes pour le relecteur ») :
   - proxy / webRequest / webRequestBlocking : router chaque conteneur vers son proxy et fournir ses identifiants ;
   - contextualIdentities / cookies : lister les conteneurs ;
   - tabs / contextMenus : menu « ouvrir avec une route » et test d'IP ;
   - <all_urls> : le proxy s'applique à tous les sites ; le test d'IP charge api.ipify.org dans le conteneur ;
   - notifications : messages de restauration de session et d'échec de route ;
   - requête vers 127.0.0.1:10800 : lecture facultative des routes de l'application SoNiC_0TAB0 (désactivable dans les réglages).
6. Politique de confidentialité : aucune donnée collectée ni transmise ; réglages et sessions restent dans le stockage local de Firefox.
7. Mise à jour d'une version déjà soumise : incrémentez `version` dans manifest.json (ici 2.3) et envoyez le nouveau zip.
