# Store listing / Fiche AMO

## English

**Name:** SoNiC_0TAB0 — One IP per container

**Summary (≤250 chars):** Give each Firefox container its own Internet exit (HTTP, SOCKS5 or Tor proxy), check the IP the web really sees, and restore your tabs with their containers and routes.

**Description:**
SoNiC_0TAB0 lets every Firefox container use its own proxy, so that several accounts or identities can browse side by side with separate cookies *and* separate network exits.

* **One route per container** – HTTP, HTTPS, SOCKS5 (with user/password) or Tor. Several saved routes, templates for Tor.
* **Real IP test** – one click shows the IP seen by the Internet for each container and warns when two containers share the same IP, or when a "routed" container still shows your normal IP.
* **Backup route (optional)** – if the main route fails, Firefox tries the backup after 5 s and returns to the main one when it works again.
* **No leak by design** – if every route is unreachable the container has no access; it never silently falls back to your normal connection.
* **Sessions** – tabs are saved automatically with their container and route. Restore the previous session, save named sessions, and (optional) reopen missing tabs at startup.
* **Open with a route** – right-click a link or tab → open it in any container.
* **Reload / auto-reload** – a Reload button (and Alt+Shift+R) as an alternative to F5, automatic reload per tab (15 s to 30 min) from the panel or the tab's right-click menu, and an option to reload a tab each time you switch to it.
* **Shortcuts** – Alt+Shift+S saves the session, Alt+Shift+I tests the current container's IP (remap in Firefox → Add-ons → ⚙ → Manage Extension Shortcuts).
* **English / Français**, switchable in the panel.
* Works on its own. Optional companion: the SoNiC_0TAB0 Windows app, which can force a route onto a specific network card (box, phone 4G…).

**Privacy:** no data collected or sent anywhere. Settings and sessions stay in Firefox's local storage. The IP test loads api.ipify.org inside the container you test. The optional Windows-app detection only reads 127.0.0.1:10800 on your own computer (can be turned off).

**Notes to reviewer (permissions):** proxy + webRequest + webRequestBlocking (route per container, proxy credentials), contextualIdentities + cookies (list containers), tabs (IP test, sessions, menus), contextMenus (open with a route), notifications (restore / route failure messages), storage, `<all_urls>` (the proxy applies to every site). Session data is stored locally only.

## Français

**Nom :** SoNiC_0TAB0 — Une IP par conteneur

**Résumé :** Donnez à chaque conteneur Firefox sa propre sortie Internet (proxy HTTP, SOCKS5 ou Tor), vérifiez l'IP réellement vue par le web et restaurez vos onglets avec leurs conteneurs et leurs routes.

**Description :** voir la version anglaise ; l'extension est entièrement disponible en français (sélecteur de langue dans le panneau et les réglages).
