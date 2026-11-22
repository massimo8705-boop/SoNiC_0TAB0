# -*- coding: utf-8 -*-
"""SoNiC_0TAB0 - logique pure (sans dépendance Windows, donc testable partout).

Contient : configuration, proxys, mesure d'IP / détection de fuite, rotation Tor,
serveur de routes SOCKS5 local (sortie par carte réseau), raccourcis, sessions.
"""
import copy
import difflib
import http.server
import json
import os
import re
import select
import socket
import struct
import threading
import urllib.request
from urllib.parse import unquote, urlparse

APPDATA = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
APP_NAME = "SoNiC_0TAB0"
_OLD_DATA = os.path.join(APPDATA, "TabDock")          # ancien nom : on récupère profils et sessions
DATA = os.path.join(APPDATA, APP_NAME)
if os.path.isdir(_OLD_DATA) and not os.path.exists(DATA):
    try:
        os.rename(_OLD_DATA, DATA)
    except OSError:
        DATA = _OLD_DATA                                # SoNiC_0TAB0 encore ouvert : on garde l'ancien dossier
CONFIG = os.path.join(DATA, "config.json")
SESSIONS = os.path.join(DATA, "sessions")
PROFILES = os.path.join(DATA, "profiles")

ACTION_LABELS = {
    "capture": "Capturer la fenêtre active",
    "new_browser": "Nouveau navigateur isolé",
    "next_tab": "Onglet suivant",
    "prev_tab": "Onglet précédent",
    "detach": "Détacher l'onglet actif",
    "toggle": "Afficher / masquer SoNiC_0TAB0",
    "save_session": "Sauvegarder la session",
    "new_ip": "Nouvelle IP (rotation)",
    "leak_check": "Test de fuite d'IP",
    "reload": "Actualiser l'onglet actif (F5)",
}
DEFAULTS = {
    "browser": "", "profile": "profil1", "url": "about:blank", "proxies": [],
    "autosave_session": True, "autorestore": True,
    "icon": "gif", "run_as_admin": False,
    "start_foreground": True, "start_maximized": True,
    "block_webrtc": True,
    "features": {"rotation": True, "leak": True, "routes": True},
    "rotation": {"mode": "pool", "auto_min": 0, "pool": [], "tor_host": "127.0.0.1",
                 "tor_port": 9051, "tor_password": "", "tor_cookie": ""},
    "leak_min": 0,
    "routes": [],
    "hotkeys": {"capture": "ctrl+alt+g", "new_browser": "ctrl+alt+n", "next_tab": "ctrl+alt+right",
                "prev_tab": "ctrl+alt+left", "detach": "ctrl+alt+d", "toggle": "ctrl+alt+space",
                "save_session": "ctrl+alt+s", "new_ip": "ctrl+alt+r", "leak_check": "ctrl+alt+l",
                "reload": "ctrl+alt+f5"},
    "reload_on_select": False,    # actualiser automatiquement un onglet quand on le sélectionne
    "goto_scoped": "ctrl",        # Ctrl+1…9 : actifs SEULEMENT quand SoNiC_0TAB0 est la fenêtre active
    "goto_global": "ctrl+alt",    # Ctrl+Alt+1…9 : actifs partout (vide = désactivé)
    "scoped_tabs": True,          # Ctrl+Tab / Ctrl+Maj+Tab (fenêtre active seulement)
}


def _merge(base, new):
    out = copy.deepcopy(base)
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            return _merge(DEFAULTS, json.load(f))
    except Exception:
        return copy.deepcopy(DEFAULTS)


def save_config(cfg):
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Proxys
# --------------------------------------------------------------------------
def parse_proxy(p):
    p = (p or "").strip()
    if not p:
        return None
    if "://" not in p:
        p = "http://" + p
    u = urlparse(p)
    scheme = u.scheme.lower().replace("socks5h", "socks5").replace("socks4a", "socks4")
    return {"scheme": scheme, "host": u.hostname or "",
            "port": u.port or (1080 if scheme.startswith("socks") else 8080),
            "user": unquote(u.username) if u.username else None,
            "pw": unquote(u.password) if u.password else None}


def normalize_proxy(p):
    d = parse_proxy(p)
    if not d:
        return ""
    auth = f"{d['user']}:{d['pw'] or ''}@" if d["user"] else ""
    return f"{d['scheme']}://{auth}{d['host']}:{d['port']}"


def proxy_for_browser(p):
    """Version sans identifiants (les navigateurs affichent leur propre invite)."""
    d = parse_proxy(p)
    return f"{d['scheme']}://{d['host']}:{d['port']}" if d else ""


def firefox_prefs(proxy, block_webrtc, restore=True):
    lines = ['user_pref("browser.shell.checkDefaultBrowser", false);',
             'user_pref("browser.startup.homepage_override.mstone", "ignore");',
             'user_pref("browser.startup.page", 3);' if restore else 'user_pref("browser.startup.page", 1);']
    d = parse_proxy(proxy)
    if d:
        lines += ['user_pref("network.proxy.type", 1);', 'user_pref("network.proxy.no_proxies_on", "");']
        if d["scheme"].startswith("socks"):
            lines += [f'user_pref("network.proxy.socks", "{d["host"]}");',
                      f'user_pref("network.proxy.socks_port", {d["port"]});',
                      'user_pref("network.proxy.socks_version", 5);',
                      'user_pref("network.proxy.socks_remote_dns", true);']
        else:
            lines += [f'user_pref("network.proxy.http", "{d["host"]}");',
                      f'user_pref("network.proxy.http_port", {d["port"]});',
                      f'user_pref("network.proxy.ssl", "{d["host"]}");',
                      f'user_pref("network.proxy.ssl_port", {d["port"]});']
        if block_webrtc:
            lines.append('user_pref("media.peerconnection.enabled", false);')
    else:
        lines.append('user_pref("network.proxy.type", 0);')
    return "\n".join(lines) + "\n"


def build_command(path, profile, url, proxy, restore=False, block_webrtc=True):
    safe = "".join(c for c in profile if c.isalnum() or c in "-_ ").strip() or "defaut"
    pdir = os.path.join(PROFILES, safe)
    os.makedirs(pdir, exist_ok=True)
    if restore and url in ("", "about:blank"):
        url = ""
    proxy = proxy_for_browser(proxy)
    if "firefox" in os.path.basename(path).lower():
        with open(os.path.join(pdir, "user.js"), "w", encoding="utf-8") as f:
            f.write(firefox_prefs(proxy, block_webrtc))
        cmd = [path, "-no-remote", "-profile", pdir]
        cmd += ["-new-window", url] if url else []
        return cmd
    cmd = [path, f"--user-data-dir={pdir}", "--no-first-run", "--no-default-browser-check"]
    if restore:
        cmd.append("--restore-last-session")
    if proxy:
        cmd.append(f"--proxy-server={proxy}")
        if block_webrtc:
            cmd.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
    if url:
        cmd += ["--new-window", url]
    return cmd


# --------------------------------------------------------------------------
# SOCKS5 (client) + mesure d'IP publique
# --------------------------------------------------------------------------
def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connexion fermée")
        buf += chunk
    return buf


def socks5_connect(phost, pport, host, port, timeout=8, user=None, pw=None):
    s = socket.create_connection((phost, pport), timeout)
    try:
        s.settimeout(timeout)
        s.sendall(b"\x05\x02\x00\x02" if user else b"\x05\x01\x00")
        ver, method = _recv_exact(s, 2)
        if ver != 5 or method == 0xFF:
            raise ConnectionError("méthode SOCKS refusée")
        if method == 2:
            u, p = (user or "").encode(), (pw or "").encode()
            s.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            if _recv_exact(s, 2)[1] != 0:
                raise ConnectionError("identifiants SOCKS refusés")
        h = host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(h)]) + h + struct.pack(">H", port))
        head = _recv_exact(s, 4)
        if head[1] != 0:
            raise ConnectionError(f"SOCKS: échec (code {head[1]})")
        atyp = head[3]
        _recv_exact(s, {1: 4, 4: 16}.get(atyp, 0) + 2 if atyp != 3 else _recv_exact(s, 1)[0] + 2)
        return s
    except Exception:
        s.close()
        raise


IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$|^[0-9a-fA-F:]{3,39}$")
IP_SERVICES = ["http://api.ipify.org", "http://icanhazip.com", "http://ifconfig.me/ip"]


def _get_via_socks(d, url, timeout):
    u = urlparse(url)
    s = socks5_connect(d["host"], d["port"], u.hostname, u.port or 80, timeout, d["user"], d["pw"])
    try:
        s.sendall(f"GET {u.path or '/'} HTTP/1.0\r\nHost: {u.hostname}\r\n"
                  "User-Agent: SoNiC_0TAB0\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    head, _, body = data.partition(b"\r\n\r\n")
    if b" 200" not in head.split(b"\r\n")[0]:
        raise ConnectionError("réponse HTTP inattendue")
    return body.decode("utf-8", "replace").strip()


def get_public_ip(proxy=None, timeout=8, services=None):
    """IP publique vue depuis l'extérieur, directement (proxy=None) ou via un proxy."""
    d = parse_proxy(proxy)
    err = None
    for url in services or IP_SERVICES:
        try:
            if d and d["scheme"].startswith("socks"):
                txt = _get_via_socks(d, url, timeout)
            else:
                handler = urllib.request.ProxyHandler(
                    {"http": normalize_proxy(proxy)} if d else {})
                with urllib.request.build_opener(handler).open(url, timeout=timeout) as r:
                    txt = r.read().decode("utf-8", "replace").strip()
            if IP_RE.match(txt):
                return txt
        except Exception as e:
            err = e
    raise ConnectionError(str(err) if err else "aucune réponse")


def check_proxies(proxies, services=None):
    """Compare l'IP directe et l'IP vue à travers chaque proxy. Retourne une liste de dicts."""
    try:
        direct = get_public_ip(None, services=services)
    except Exception as e:
        direct = None
    out = []
    for p in proxies:
        r = {"proxy": p, "direct": direct, "ip": None, "status": "", "leak": False}
        try:
            r["ip"] = get_public_ip(p, services=services)
            if direct and r["ip"] == direct:
                r["status"], r["leak"] = "FUITE : même IP que votre connexion directe", True
            else:
                r["status"] = "OK"
        except Exception as e:
            r["status"] = f"Proxy injoignable ({e})"
        out.append(r)
    return out


def tor_newnym(host="127.0.0.1", port=9051, password="", cookie=""):
    """Demande de nouveaux circuits Tor (nouvelle IP de sortie) via le port de contrôle."""
    s = socket.create_connection((host, int(port)), 5)
    try:
        s.settimeout(5)
        if password:
            auth = f'AUTHENTICATE "{password}"\r\n'
        elif cookie and os.path.isfile(cookie):
            with open(cookie, "rb") as f:
                auth = "AUTHENTICATE " + f.read().hex() + "\r\n"
        else:
            auth = "AUTHENTICATE\r\n"
        for cmd in (auth, "SIGNAL NEWNYM\r\n"):
            s.sendall(cmd.encode())
            if not s.recv(256).startswith(b"250"):
                raise ConnectionError("Tor a refusé la commande (mot de passe / cookie ?)")
        s.sendall(b"QUIT\r\n")
    finally:
        s.close()


def get_public_ip_bound(hook, timeout=8, services=None):
    """IP publique vue en sortant par une carte précise (`hook(sock)` force la carte)."""
    err = None
    for url in services or IP_SERVICES:
        try:
            u = urlparse(url)
            port = u.port or 80
            infos = socket.getaddrinfo(u.hostname, port, socket.AF_INET, socket.SOCK_STREAM)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(timeout)
                hook(s)
                s.connect(infos[0][4])
                s.sendall(f"GET {u.path or '/'} HTTP/1.0\r\nHost: {u.hostname}\r\n"
                          "User-Agent: SoNiC_0TAB0\r\nConnection: close\r\n\r\n".encode())
                data = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            finally:
                s.close()
            head, _, body = data.partition(b"\r\n\r\n")
            txt = body.decode("utf-8", "replace").strip()
            if b" 200" in head.split(b"\r\n")[0] and IP_RE.match(txt):
                return txt
        except Exception as e:
            err = e
    raise ConnectionError(str(err) if err else "aucune réponse")


# --------------------------------------------------------------------------
# Serveur de route SOCKS5 local : sort par une carte réseau précise
# --------------------------------------------------------------------------
class RouteServer(threading.Thread):
    """Proxy SOCKS5 écoutant UNIQUEMENT sur 127.0.0.1. `bind_hook(sock)` force la
    carte réseau de sortie ; s'il échoue la connexion est refusée (pas de repli
    silencieux sur la connexion par défaut, donc pas de fuite)."""

    def __init__(self, port, bind_hook=None, name="", fallbacks=None, on_switch=None, connect_timeout=15):
        """fallbacks : liste de (nom, bind_hook) essayées dans l'ordre si la sortie principale échoue.
        on_switch(texte) est appelée quand la sortie active change (bascule / retour à la principale).
        Il n'y a JAMAIS de repli sur la connexion par défaut du PC."""
        super().__init__(daemon=True)
        self.port, self.hook, self.label = port, bind_hook, name
        self.fallbacks = list(fallbacks or [])
        self.on_switch = on_switch
        self.connect_timeout = connect_timeout
        self.active = "principale"
        self._sw_lock = threading.Lock()
        self.error = None
        self._halt = threading.Event()
        self._srv = None
        self.ready = threading.Event()

    def run(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", self.port))
            s.listen(128)
            s.settimeout(0.5)
            self._srv = s
        except OSError as e:
            self.error = str(e)
            self.ready.set()
            return
        self.ready.set()
        while not self._halt.is_set():
            try:
                c, _ = s.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve_client, args=(c,), daemon=True).start()
        s.close()

    def stop(self):
        self._halt.set()

    def _note(self, who):
        with self._sw_lock:
            if who == self.active:
                return
            self.active = who
        if self.on_switch:
            try:
                if who == "principale":
                    self.on_switch(f"Route « {self.label} » : retour à la connexion principale.")
                else:
                    self.on_switch(f"Route « {self.label} » : connexion principale indisponible, "
                                   f"bascule sur la route de secours « {who} ».")
            except Exception:
                pass

    def _open_remote(self, addr):
        """Principale d'abord (donc retour automatique dès qu'elle revient), puis les secours."""
        tries = [("principale", self.hook)] + self.fallbacks
        last = None
        for i, (who, hook) in enumerate(tries):
            sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # délai court tant qu'il reste un secours, pour basculer vite
            sk.settimeout(min(self.connect_timeout, 5) if i < len(tries) - 1 else self.connect_timeout)
            try:
                if hook:
                    hook(sk)
                sk.connect(addr)
                self._note(who)
                return sk
            except Exception as e:
                last = e
                try:
                    sk.close()
                except Exception:
                    pass
        raise last or OSError("aucune sortie disponible")

    def _serve_client(self, c):
        remote = None
        try:
            c.settimeout(15)
            ver, n = _recv_exact(c, 2)
            _recv_exact(c, n)
            c.sendall(b"\x05\x00")
            ver, cmd, _, atyp = _recv_exact(c, 4)
            if cmd != 1:
                c.sendall(b"\x05\x07\x00\x01" + b"\0" * 6)
                return
            if atyp == 1:
                host = socket.inet_ntoa(_recv_exact(c, 4))
            elif atyp == 3:
                host = _recv_exact(c, _recv_exact(c, 1)[0]).decode()
            else:
                host = socket.inet_ntop(socket.AF_INET6, _recv_exact(c, 16))
            port = struct.unpack(">H", _recv_exact(c, 2))[0]
            try:
                infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                remote = self._open_remote(infos[0][4])
            except Exception:
                c.sendall(b"\x05\x04\x00\x01" + b"\0" * 6)
                return
            c.sendall(b"\x05\x00\x00\x01" + b"\0" * 6)
            c.settimeout(None)
            remote.settimeout(None)
            socks = [c, remote]
            while True:
                r, _, _ = select.select(socks, [], [], 60)
                if not r:
                    break
                done = False
                for a in r:
                    data = a.recv(65536)
                    if not data:
                        done = True
                        break
                    (remote if a is c else c).sendall(data)
                if done:
                    break
        except Exception:
            pass
        finally:
            for x in (c, remote):
                try:
                    if x:
                        x.close()
                except Exception:
                    pass


# --------------------------------------------------------------------------
# Petit service local (127.0.0.1 uniquement) : l'extension Firefox y lit les routes
# --------------------------------------------------------------------------
class ControlServer(threading.Thread):
    PORT = 10800

    def __init__(self, get_routes, port=None):
        super().__init__(daemon=True)
        self.get_routes, self.port = get_routes, port or self.PORT
        self.httpd = None
        self.error = None

    def run(self):
        get_routes = self.get_routes

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/routes.json"):
                    body = json.dumps({"app": "SoNiC_0TAB0", "routes": [
                        {"name": r["name"], "proxy": f"socks5://127.0.0.1:{r['port']}",
                         "adapter": r.get("iface_name", ""), "ip": r.get("ip", "")}
                        for r in get_routes()]}).encode()
                elif self.path.startswith("/ping"):
                    body = b'{"app":"SoNiC_0TAB0"}'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        try:
            self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        except OSError as e:
            self.error = str(e)
            return
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


# --------------------------------------------------------------------------
# Raccourcis clavier / sessions
# --------------------------------------------------------------------------
_KEYS = {"left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "space": 0x20, "tab": 0x09,
         "enter": 0x0D, "esc": 0x1B, "pageup": 0x21, "pagedown": 0x22, "home": 0x24, "end": 0x23,
         "insert": 0x2D, "delete": 0x2E}
_MODS = {"alt": 1, "ctrl": 2, "control": 2, "shift": 4, "win": 8}


def parse_hotkey(spec):
    """'ctrl+alt+g' -> (modifiers, vk) ; None si invalide (au moins un modificateur exigé)."""
    mods, vk = 0, None
    for part in (spec or "").lower().replace(" ", "").split("+"):
        if part in _MODS:
            mods |= _MODS[part]
        elif part in _KEYS:
            vk = _KEYS[part]
        elif re.fullmatch(r"f([1-9]|1\d|2[0-4])", part):
            vk = 0x70 + int(part[1:]) - 1
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            return None
    return (mods, vk) if mods and vk else None


def hotkey_map(cfg):
    m = dict(cfg["hotkeys"])
    if not cfg["features"].get("rotation"):
        m.pop("new_ip", None)
    if not cfg["features"].get("leak"):
        m.pop("leak_check", None)
    if cfg.get("goto_global"):
        for n in range(1, 10):
            m[f"goto_{n}"] = f"{cfg['goto_global']}+{n}"
    return m


def scoped_map(cfg):
    """Raccourcis actifs seulement quand la fenêtre SoNiC_0TAB0 est au premier plan
    (ils ne volent donc pas Ctrl+1…9 / Ctrl+Tab aux autres applications)."""
    m = {}
    if cfg.get("goto_scoped"):
        for n in range(1, 10):
            m[f"goto_{n}"] = f"{cfg['goto_scoped']}+{n}"
    if cfg.get("scoped_tabs"):
        m["next_tab"], m["prev_tab"] = "ctrl+tab", "ctrl+shift+tab"
    return m


def list_sessions():
    try:
        return sorted(f[:-5] for f in os.listdir(SESSIONS) if f.endswith(".json"))
    except OSError:
        return []


def save_session_file(name, data):
    os.makedirs(SESSIONS, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "-_ ._éèêàùçôî").strip() or "session"
    with open(os.path.join(SESSIONS, safe + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return safe


def load_session_file(name):
    with open(os.path.join(SESSIONS, name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def match_window(saved, candidates, used):
    """Retrouve parmi les fenêtres ouvertes (hwnd, titre, exe, pid) celle d'un onglet sauvegardé."""
    pool = [c for c in candidates if c[0] not in used and c[2] == saved.get("exe")]
    if not pool:
        return None
    best = max(pool, key=lambda c: difflib.SequenceMatcher(None, c[1], saved.get("title", "")).ratio())
    ratio = difflib.SequenceMatcher(None, best[1], saved.get("title", "")).ratio()
    return best[0] if ratio >= 0.5 or len(pool) == 1 else None


# --------------------------------------------------------------------------
# Affichage côte à côte, restauration de session
# --------------------------------------------------------------------------
def tile_layout(n, mode, W, H, gap=3):
    """Rectangles (x, y, w, h) pour n fenêtres. mode : None/'single' | 'cols' | 'rows' | 'grid'."""
    if n <= 0:
        return []
    if n == 1 or mode in (None, "", "single"):
        return [(0, 0, W, H)] + [(0, 0, W, H)] * (n - 1)
    if mode == "cols":
        cols = n
    elif mode == "rows":
        cols = 1
    else:
        cols = 2 if n in (2, 4) else 3
    rows = -(-n // cols)
    ch = (H - gap * (rows - 1)) // rows
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        k = min(cols, n - r * cols)          # la dernière ligne s'étire si incomplète
        cw = (W - gap * (k - 1)) // k
        out.append((c * (cw + gap), r * (ch + gap), cw, ch))
    return out


BROWSER_EXES = {"firefox.exe", "chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "launcher.exe",
                "vivaldi.exe", "chromium.exe"}


def reopen_command(exe_path):
    flag = "-new-window" if "firefox" in os.path.basename(exe_path).lower() else "--new-window"
    return [exe_path, flag]


def plan_restore(saved, running, used_hwnds, open_profiles):
    """Décide quoi faire pour chaque onglet sauvegardé. Actions :
    ('embed', ts, hwnd) fenêtre déjà ouverte · ('launch', ts) navigateur lancé par SoNiC_0TAB0 ·
    ('reopen', ts) navigateur capturé à la main, on le rouvre · ('already', ts) · ('missing', ts)"""
    used, plans = set(used_hwnds), []
    for ts in saved:
        L = ts.get("launch")
        if L:
            plans.append(("already" if L.get("profile") in open_profiles else "launch", ts))
            continue
        h = match_window(ts, running, used)
        if h:
            used.add(h)
            plans.append(("embed", ts, h))
        elif ts.get("exe") in BROWSER_EXES and ts.get("exe_path") and os.path.isfile(ts["exe_path"]):
            plans.append(("reopen", ts))
        else:
            plans.append(("missing", ts))
    return plans


# Intervalles d'actualisation automatique proposés (secondes -> libellé)
RELOAD_CHOICES = [(0, "Désactivée"), (15, "Toutes les 15 secondes"), (30, "Toutes les 30 secondes"),
                  (60, "Toutes les minutes"), (120, "Toutes les 2 minutes"), (300, "Toutes les 5 minutes"),
                  (600, "Toutes les 10 minutes"), (1800, "Toutes les 30 minutes")]
