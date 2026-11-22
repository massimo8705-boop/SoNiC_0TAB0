# SoNiC_0TAB0 1.6

Une fenêtre, des onglets qui sont de vraies fenêtres de Firefox / Chrome / Opera / Edge / Brave…,
groupes colorés par glisser-déposer, **affichage côte à côte**, sessions, **une sortie Internet par onglet**.

## Installer
1. **Extraire tout** le zip (clic droit → « Extraire tout… »), ne rien lancer depuis l'intérieur du zip.
2. Double-cliquez **`INSTALLER.cmd`** (il détecte Python et propose de l'installer si besoin).
   Erreurs : boîte de dialogue + `%TEMP%\sonic_0tab0_install.log`.
3. Sans installer : `SoNiC_0TAB0.cmd`.

Démarrage avec Windows : « user » ou « admin » (tâche planifiée, sans invite UAC). SoNiC_0TAB0 s'ouvre
au premier plan et restaure la dernière session.

## Utiliser
* **＋** (à droite des onglets) : capturer une fenêtre déjà ouverte, ou lancer un navigateur isolé. **☰** : menu.
* Ctrl+Alt+G sur n'importe quelle fenêtre = la capturer.
* Glisser un onglet SUR un autre = groupe ; bords = réorganiser ; vide à droite = sortir du groupe ;
  **le lâcher sous la barre (ou hors fenêtre) = le détacher à cet endroit**.
* **Ctrl+1 … Ctrl+9** : aller à l'onglet 1…9 (actif quand SoNiC_0TAB0 est au premier plan, y compris
  quand un navigateur intégré a le focus). **Ctrl+Alt+1…9** : idem depuis n'importe où. Ctrl+Tab / Ctrl+Maj+Tab : suivant / précédent.
* Clic milieu = fermer, double-clic = renommer, molette = changer d'onglet.
* **Côte à côte** : clic droit sur l'étiquette d'un groupe → Affichage → colonnes / lignes / grille.
* Clic droit onglet : renommer, groupe, couleur, **Détacher**, fermer.
* Secours : ☰ → Options → « Libérer toutes les fenêtres ».

## Une IP différente par onglet
1. ☰ → Réseau → **Mes connexions Internet** → *Détecter* : chaque carte réseau est testée et son IP publique
   affichée. **Deux cartes avec la même IP = même accès Internet** (ex. Wi-Fi + Ethernet de la même box).
   Pour une 2e IP : une carte Wi-Fi ne rejoint qu'**un seul** réseau (box OU hotspot du téléphone). Branchez le
   téléphone en USB → Paramètres → Connexions → Point d'accès mobile et modem → **Modem USB** : une 2e carte apparaît.
   (ou une clé Wi-Fi USB, ou un VPN).
2. *Créer les routes* : une route (proxy local 127.0.0.1) par IP différente. Si la carte tombe, la connexion
   est refusée (aucun repli silencieux).
3. ＋ → Nouveau navigateur : choisissez profil (cookies séparés) + route.
4. Opera + VPN : profil SoNiC_0TAB0, route vide, activez le VPN d'Opera dans ce profil.
5. Options : rotation d'IP (Tor ou pool), détection de fuite, WebRTC bloqué.

Adresse à saisir dans « proxy » : `socks5://127.0.0.1:10810` (127.0.0.1 = ce PC, 10810 = port de la route ;
choisissez plutôt « Route · … » dans la liste, l'adresse se remplit seule).

## Extension Firefox (autonome)
L'extension fonctionne **seule** (ses propres routes : SOCKS5/HTTP, identifiants, Tor, import/export) ; elle
ajoute en plus les routes de l'application si celle-ci est lancée (désactivable). Voir `firefox_extension/`.

## Installer l'extension : plusieurs IP dans UNE fenêtre Firefox
☰ → Réseau → Extension Firefox : essai temporaire ou installation définitive (signature Mozilla gratuite).
Bouton SoNiC_0TAB0 dans la barre Firefox : route par conteneur, **Tester** (affiche l'IP réelle, signale les
conteneurs qui ont la même IP), Ouvrir, nouveau conteneur routé. Clic droit sur un lien : ouvrir avec une route.

## Dépannage
* Journal : `%APPDATA%\SoNiC_0TAB0\sonic_0tab0.log`.
* Une fenêtre refuse l'intégration : message précis (administrateur ? application protégée ?).
* Ne tuez pas SoNiC_0TAB0 depuis le gestionnaire des tâches : fermez-le par sa croix (les fenêtres sont rendues).

## Thème
Images dans `%APPDATA%\SoNiC_0TAB0\theme` (voir `prepare_theme.py`, `PROMPTS_IMAGES.md`).

## Route de secours (v1.5)
Connexions Internet → sélectionnez une carte → **↪ Route de secours** : si la route tombe, les connexions passent
par l'autre route (notification), puis reviennent seules sur la principale. Jamais de repli sur la connexion normale.
L'IP vue par les sites change pendant la bascule. Extension (v2.1) : « secours » par conteneur dans les réglages.

## Extension v2.2
Anglais / français (sélecteur), icône d'onglet des réglages, panneau compact sans défilement horizontal,
**sessions** (onglets + conteneurs + routes sauvegardés automatiquement, restauration au démarrage, sessions nommées),
raccourcis Alt+Maj+S (enregistrer) / Alt+Maj+I (tester l'IP du conteneur actif), alerte « IP identique à la connexion normale ».

## Actualisation des onglets (application 1.6 / extension 2.3)
* **Application** : clic droit sur un onglet → *Actualiser (F5)*, *Actualiser sans cache (Ctrl+F5)*, *Actualisation automatique*
  (15 s … 30 min, ou « à chaque sélection de l'onglet »). Menu Options → *Actualiser l'onglet actif* et
  *Actualiser un onglet à chaque changement d'onglet* (option globale). Raccourci **Ctrl+Alt+F5**. Un ⟳ s'affiche sur les onglets concernés.
  La touche n'est envoyée que si SoNiC_0TAB0 est au premier plan et que Ctrl/Alt sont relâchées ; réglages enregistrés dans les sessions.
* **Extension** : bouton *Actualiser* / *sans cache* dans le panneau, actualisation automatique par onglet, clic droit sur l'onglet →
  « SoNiC_0TAB0 : actualisation auto », raccourci **Alt+Maj+R**, option globale « à chaque fois que je sélectionne un onglet ».
  Une actualisation peut faire perdre un texte en cours de saisie.
