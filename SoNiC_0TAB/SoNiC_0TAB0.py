# -*- coding: utf-8 -*-
"""
SoNiC_0TAB0 - une fenêtre à onglets qui regroupe Firefox, Chrome, Opera, Edge...
Groupes colorés par glisser-déposer, affichage côte à côte, sessions, routes réseau
(une sortie Internet par onglet), rotation d'IP, détection de fuite, démarrage au premier plan.

Python 3.8+ sous Windows. Lancer :  pythonw SoNiC_0TAB0.py
Options : --startup --minimized --restore --admin
"""
import argparse
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
import zipfile
import tkinter as tk
import tkinter.font as tkfont
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox, simpledialog, ttk

TEST = bool(os.environ.get("TABDOCK_TEST"))
if sys.platform != "win32" and not TEST:
    sys.exit("SoNiC_0TAB0 fonctionne uniquement sous Windows.")
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import td_core as core  # noqa: E402
import td_win as w  # noqa: E402

BG, BAR, TAB, TABSEL, TABVIS = "#0a0e1f", "#070a16", "#141a33", "#23306b", "#1a2350"
FG, MUTED, ACCENT, ALERT = "#e8ecff", "#8b93b8", "#ffc857", "#ff6b6b"
PALETTE = [("Bleu", "#4f9dff"), ("Rouge", "#ff6b6b"), ("Vert", "#4ecb71"), ("Orange", "#ffb454"),
           ("Violet", "#b784f7"), ("Turquoise", "#2dd4bf"), ("Rose", "#f472b6"), ("Gris", "#a3a3a3")]
EXE_COLORS = {"firefox.exe": "#ff7139", "chrome.exe": "#4db66a", "msedge.exe": "#2f9bd6",
              "opera.exe": "#ff1b2d", "launcher.exe": "#ff1b2d", "brave.exe": "#fb542b",
              "vivaldi.exe": "#ef3939"}
BAR_H, TAB_Y0, TAB_Y1 = 38, 5, 35
TEST_PAGES = {"Page vide": "about:blank", "Test d'IP (ipify)": "https://api.ipify.org",
              "Test de fuite (ipleak.net)": "https://ipleak.net",
              "Test WebRTC (browserleaks)": "https://browserleaks.com/webrtc"}
SPLITS = (("Onglet unique", None), ("Côte à côte (colonnes)", "cols"), ("Empilés (lignes)", "rows"),
          ("Grille", "grid"))


def log(msg):
    try:
        os.makedirs(core.DATA, exist_ok=True)
        with open(os.path.join(core.DATA, "sonic_0tab0.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + msg + "\n")
    except OSError:
        pass


def asset(name):
    """Thème : %APPDATA%\\SoNiC_0TAB0\\theme\\<nom> (vos images) sinon assets\\<nom> (fourni)."""
    user = os.path.join(core.DATA, "theme", name)
    if os.path.isfile(user):
        return user
    for base in (getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__))):
        p = os.path.join(base, "assets", name)
        if base and os.path.isfile(p):
            return p
    return None


def core_browsers():
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    la = os.environ.get("LOCALAPPDATA", "")
    cands = {"Firefox": [r"Mozilla Firefox\firefox.exe"], "Chrome": [r"Google\Chrome\Application\chrome.exe"],
             "Edge": [r"Microsoft\Edge\Application\msedge.exe"],
             "Brave": [r"BraveSoftware\Brave-Browser\Application\brave.exe"],
             "Opera": [r"Opera\opera.exe", r"Programs\Opera\opera.exe", r"Opera\launcher.exe",
                       r"Programs\Opera\launcher.exe"],
             "Opera GX": [r"Programs\Opera GX\opera.exe", r"Programs\Opera GX\launcher.exe"],
             "Vivaldi": [r"Vivaldi\Application\vivaldi.exe"]}
    found = {}
    for name, rels in cands.items():
        for base in (pf, pf86, la):
            for rel in rels:
                p = os.path.join(base, rel)
                if base and os.path.isfile(p):
                    found.setdefault(name, p)
    return found


class Animator:
    def __init__(self, label, path, delay=180):
        self.label, self.frames, self.i, self.delay, self.run = label, [], 0, delay, False
        k = 0
        while path:
            try:
                self.frames.append(tk.PhotoImage(file=path, format=f"gif -index {k}"))
            except tk.TclError:
                break
            k += 1
        if self.frames:
            label.configure(image=self.frames[0])

    def start(self):
        if not self.run and len(self.frames) > 1:
            self.run = True
            self._tick()

    def _tick(self):
        if self.run:
            self.i = (self.i + 1) % len(self.frames)
            self.label.configure(image=self.frames[self.i])
            self.label.after(self.delay, self._tick)


class SoNiC_0TAB0:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.cfg = core.load_config()
        self.tabs, self.groups, self.current = [], {}, None
        self.gcount, self.hits = 0, []
        self.press, self.dragging, self.drop, self.mouse = None, False, None, (0, 0)
        self.q = queue.Queue()
        self.job_queue, self.job_busy = [], False
        self.routes, self.hotkeys = {}, None
        self.failed, self.embed_error = set(), ""
        self.tick = 0
        now = time.time()
        self.last_leak = self.last_rot = self.last_save = now
        self.imgs = {}

        w.set_app_id()
        root.title("SoNiC_0TAB0")
        root.geometry("1280x820")
        root.configure(bg=BG)
        root.report_callback_exception = self.on_exception
        self.font = tkfont.Font(family="Segoe UI", size=9)
        self.fontb = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.apply_icon()

        self.bar = tk.Canvas(root, height=BAR_H, bg=BAR, highlightthickness=0)
        self.bar.pack(fill="x")
        self.marker = tk.Label(self.bar, bg=BAR, bd=0, cursor="hand2")
        self.marker.bind("<Button-1>", lambda e: self.about())
        self.marker_anim = Animator(self.marker, asset("marker.gif"))
        self.marker_anim.start()
        self.host = tk.Frame(root, bg=BG)
        self.host.pack(fill="both", expand=True)
        self.build_placeholder()
        self.status = tk.StringVar(value="Prêt.  ☰ en haut à droite = menu · ＋ = ajouter un onglet.")
        tk.Label(root, textvariable=self.status, bg=BAR, fg=MUTED, anchor="w",
                 font=("Segoe UI", 8)).pack(fill="x")

        root.update_idletasks()
        self.host_hwnd = self.host.winfo_id()
        self.top_hwnd = w.top_hwnd(self.host_hwnd)
        self.scoped_on = False
        w.add_clip_styles(self.host_hwnd)
        self.host.bind("<Configure>", lambda e: self.layout())
        b = self.bar
        b.bind("<Configure>", lambda e: self.redraw())
        b.bind("<ButtonPress-1>", self.on_press)
        b.bind("<B1-Motion>", self.on_motion)
        b.bind("<ButtonRelease-1>", self.on_release)
        b.bind("<Button-3>", self.on_right)
        b.bind("<Button-2>", self.on_middle)
        b.bind("<Double-Button-1>", self.on_double)
        b.bind("<MouseWheel>", self.on_wheel)
        root.bind("<Control-Tab>", lambda e: self.cycle(1))
        root.bind("<Control-Shift-Tab>", lambda e: self.cycle(-1))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.menu = self.build_menu()
        self.plus_menu = tk.Menu(root, tearoff=0)
        self.plus_menu.add_command(label="Capturer une fenêtre déjà ouverte…", command=self.dlg_capture)
        self.plus_menu.add_command(label="Nouveau navigateur (proxy / route)…", command=self.dlg_launch)
        self.redraw()
        self.start_routes()
        self.control = core.ControlServer(lambda: self.cfg["routes"])
        self.control.start()
        self.start_hotkeys()
        self.poll()

        if args.startup or args.restore:
            if self.cfg["autorestore"] or args.restore:
                root.after(900, lambda: self.restore_last(quiet=True))
            if args.startup and self.cfg["start_foreground"] and not args.minimized:
                root.after(300, lambda: self.bring_front(self.cfg["start_maximized"]))
        if args.minimized:
            root.iconify()
        if w.is_admin():
            root.title("SoNiC_0TAB0 (administrateur)")

    # ------------------------------------------------------------ erreurs / thème
    def on_exception(self, exc, val, tb):
        msg = "".join(traceback.format_exception(exc, val, tb))
        log(msg)
        self.status.set(f"Erreur interne : {val}  (détails : {os.path.join(core.DATA, 'sonic_0tab0.log')})")

    ICONS = {"gif": ("tabdock.ico", "icon64.png"), "image": ("tabdock_alt.ico", "icon64_alt.png"),
             "duo": ("tabdock_duo.ico", "icon64_duo.png")}

    def apply_icon(self):
        ico, png64 = self.ICONS.get(self.cfg["icon"], self.ICONS["gif"])
        try:
            self.root.iconbitmap(default=asset(ico))
        except Exception:
            try:
                png = tk.PhotoImage(file=asset(png64))
                self.imgs["icon"] = png
                self.root.iconphoto(True, png)
            except Exception:
                pass

    def build_placeholder(self):
        c = self.ph = tk.Canvas(self.host, bg=BG, highlightthickness=0)
        c.place(x=0, y=0, relwidth=1, relheight=1)
        bgp = asset("background.png")
        if bgp:
            try:
                self.imgs["bg"] = tk.PhotoImage(file=bgp)
            except tk.TclError:
                pass
        self.ph_label = tk.Label(c, bg=BG, bd=0)
        self.ph_anim = Animator(self.ph_label, asset("banner.gif"))
        self.ph_anim.start()
        c.bind("<Configure>", self.layout_placeholder)

    def layout_placeholder(self, e=None):
        c = self.ph
        c.delete("all")
        W, H = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
        if "bg" in self.imgs:
            c.create_image(W // 2, H // 2, image=self.imgs["bg"])
        c.create_window(W // 2, H // 2 - 90, window=self.ph_label)
        c.create_text(W // 2, H // 2 + 90, fill=FG, font=("Segoe UI", 12), justify="center",
                      text="Aucun onglet pour l'instant\n\n"
                           "①  Ouvrez Firefox, Chrome, Opera… comme d'habitude\n"
                           "②  Cliquez sur ＋ puis « Capturer une fenêtre » (ou Ctrl+Alt+G sur la fenêtre voulue)\n"
                           "③  Glissez un onglet sur un autre pour les grouper, clic droit pour l'affichage côte à côte")

    def show_placeholder(self, on):
        if on:
            self.ph.place(x=0, y=0, relwidth=1, relheight=1)
            self.layout_placeholder()
        else:
            self.ph.place_forget()

    # --------------------------------------------------------------------- menus
    def build_menu(self):
        f = self.cfg["features"]
        m = tk.Menu(self.root, tearoff=0)
        s = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Session", menu=s)
        s.add_command(label="Sauvegarder la session…", command=self.session_save_dialog)
        s.add_command(label="Restaurer une session…", command=self.session_restore_dialog)
        s.add_command(label="Restaurer la dernière session", command=self.restore_last)
        s.add_separator()
        s.add_command(label="Ouvrir le dossier des sessions",
                      command=lambda: (os.makedirs(core.SESSIONS, exist_ok=True), os.startfile(core.SESSIONS)))
        n = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Réseau", menu=n)
        n.add_command(label="Mes connexions Internet (routes)…", command=self.dlg_connections)
        n.add_command(label="Nouveau navigateur (proxy / route)…", command=self.dlg_launch)
        n.add_command(label="Extension Firefox (conteneurs + routes)…", command=self.dlg_extension)
        if f["rotation"]:
            n.add_separator()
            n.add_command(label="Nouvelle IP — onglet actif", command=lambda: self.rotate_ip(False))
            n.add_command(label="Nouvelle IP — tous les onglets à proxy", command=lambda: self.rotate_ip(True))
        if f["leak"]:
            n.add_separator()
            n.add_command(label="Tester les fuites d'IP", command=lambda: self.leak_check(False))
        o = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Options", menu=o)
        o.add_command(label="Actualiser l'onglet actif   (Ctrl+Alt+F5)", command=lambda: self.reload_tab(self.current))
        self.reload_sel_var = tk.BooleanVar(value=bool(self.cfg.get("reload_on_select")))
        o.add_checkbutton(label="Actualiser un onglet à chaque changement d'onglet", variable=self.reload_sel_var,
                          command=self.toggle_global_reload_on_select)
        o.add_separator()
        o.add_command(label="Paramètres…", command=self.dlg_settings)
        self.icon_var = tk.StringVar(value=self.cfg["icon"])
        ic = tk.Menu(o, tearoff=0)
        o.add_cascade(label="Icône de l'application", menu=ic)
        for lbl, val in (("Chat à capuche (visage)", "gif"), ("Chat mage (scène)", "image"),
                         ("Chat mage + sphère (duo)", "duo")):
            ic.add_radiobutton(label=lbl, value=val, variable=self.icon_var, command=self.change_icon)
        o.add_command(label="Libérer toutes les fenêtres (secours)", command=self.liberate_all)
        if not w.is_admin():
            o.add_command(label="Relancer en administrateur", command=lambda: self.on_close(relaunch=True))
        a = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Aide", menu=a)
        a.add_command(label="Guide rapide", command=self.show_guide)
        a.add_command(label="Raccourcis clavier", command=self.show_keys)
        a.add_command(label="À propos", command=self.about)
        return m

    def change_icon(self):
        self.cfg["icon"] = self.icon_var.get()
        core.save_config(self.cfg)
        self.apply_icon()

    def liberate_all(self):
        for t in list(self.tabs):
            self.release(t)
        n = w.liberate_children(self.host_hwnd)
        self.status.set(f"Fenêtres rendues au bureau{' (+' + str(n) + ' coincées récupérées)' if n else ''}.")

    def show_guide(self):
        messagebox.showinfo(
            "Guide rapide",
            "AJOUTER DES ONGLETS\n"
            "• ＋ → « Capturer une fenêtre » : choisissez une fenêtre Firefox / Chrome / Opera… déjà ouverte.\n"
            "• Ou Ctrl+Alt+G sur la fenêtre voulue.\n"
            "• ＋ → « Nouveau navigateur » : SoNiC_0TAB0 lance un navigateur avec son propre profil (cookies séparés).\n\n"
            "GROUPER\n"
            "• Glissez un onglet SUR un autre (au centre) : un groupe coloré est créé.\n"
            "• Bords gauche/droite d'un onglet : réorganiser. Vide à droite : sortir du groupe.\n"
            "• Clic sur l'étiquette du groupe : replier. Clic droit : nom, couleur, affichage.\n\n"
            "CÔTE À CÔTE\n"
            "• Clic droit sur l'étiquette d'un groupe → « Côte à côte » : tous les onglets du groupe sont\n"
            "  visibles en même temps (colonnes, lignes ou grille).\n\n"
            "IP DIFFÉRENTES\n"
            "• Réseau → « Mes connexions Internet » : détecte vos accès (box, partage 4G du téléphone en USB, VPN)\n"
            "  et crée une route par accès. Choisissez-la ensuite dans « Nouveau navigateur ».\n\n"
            "DÉTACHER / SECOURS\n"
            "• Clic droit sur un onglet → Détacher. Options → « Libérer toutes les fenêtres » en cas de souci.")

    def show_keys(self):
        hk = self.cfg["hotkeys"]
        lines = [f"{core.ACTION_LABELS[a]} : {hk[a]}" for a in core.ACTION_LABELS if a in hk]
        if self.cfg.get("goto_scoped"):
            lines.insert(0, f"Aller à l'onglet 1 à 9 (dans SoNiC_0TAB0) : {self.cfg['goto_scoped']}+1…9")
        if self.cfg.get("scoped_tabs"):
            lines.insert(1, "Onglet suivant / précédent (dans SoNiC_0TAB0) : Ctrl+Tab / Ctrl+Maj+Tab")
        if self.cfg.get("goto_global"):
            lines.append(f"Aller à l'onglet 1 à 9 (partout) : {self.cfg['goto_global']}+1…9")
        messagebox.showinfo("Raccourcis", "\n".join(lines) + "\n\n(modifiables dans Options → Paramètres)")

    def about(self):
        win = tk.Toplevel(self.root)
        win.title("À propos de SoNiC_0TAB0")
        win.configure(bg=BG)
        win.resizable(False, False)
        p = asset("mascot_duo.png") or asset("banner.png")
        if p:
            try:
                self.imgs["about"] = tk.PhotoImage(file=p)
                tk.Label(win, image=self.imgs["about"], bg=BG, bd=0).pack()
            except tk.TclError:
                pass
        tk.Label(win, bg=BG, fg=FG, font=("Segoe UI", 10), justify="center", pady=8,
                 text="SoNiC_0TAB0 — un seul cadre, plusieurs navigateurs, plusieurs connexions.\n"
                      f"Données : {core.DATA}\nThème personnalisé : {os.path.join(core.DATA, 'theme')}").pack()

    # --------------------------------------------------------------- extension
    def ext_dir(self):
        for base in (os.path.dirname(os.path.abspath(sys.argv[0])), getattr(sys, "_MEIPASS", ""),
                     os.path.dirname(os.path.abspath(__file__))):
            d = os.path.join(base, "firefox_extension")
            if base and os.path.isfile(os.path.join(d, "manifest.json")):
                return d
        return None

    def make_ext_zip(self):
        d = self.ext_dir()
        if not d:
            return None
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        dest = os.path.join(desk if os.path.isdir(desk) else os.path.expanduser("~"), "SoNiC_0TAB0-Firefox.zip")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(d):
                for fn in files:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, d))
        return dest

    def firefox_path(self):
        p = core_browsers().get("Firefox")
        if not p:
            messagebox.showerror("Firefox", "Firefox est introuvable sur ce PC.")
        return p

    def ext_temp(self):
        d, ff = self.ext_dir(), self.firefox_path()
        if not (d and ff):
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(os.path.join(d, "manifest.json"))
        subprocess.Popen([ff, "-new-tab", "about:debugging#/runtime/this-firefox"])
        messagebox.showinfo("Essai temporaire",
                            "Firefox s'ouvre sur « Ce Firefox ».\n\n1. Cliquez « Charger un module temporaire… »\n"
                            "2. Choisissez le fichier manifest.json (son chemin est déjà copié : Ctrl+V).\n\n"
                            "Le bouton SoNiC_0TAB0 apparaît dans la barre d'outils. Il disparaît à la fermeture de "
                            "Firefox : pour une installation définitive, utilisez l'option 2.")

    def ext_sign(self):
        dest = self.make_ext_zip()
        if not dest:
            messagebox.showerror("Extension", "Dossier de l'extension introuvable.")
            return
        webbrowser.open("https://addons.mozilla.org/developers/addon/submit/distribution")
        messagebox.showinfo("Installation définitive (gratuit)",
                            f"Le fichier à envoyer est prêt :\n{dest}\n\nLe site de Mozilla s'ouvre :\n"
                            "1. Connectez-vous (compte Firefox gratuit).\n"
                            "2. Choisissez « Sur mon propre site » (non répertorié) puis envoyez ce fichier.\n"
                            "3. Après la validation automatique (quelques minutes), téléchargez le fichier .xpi signé.\n"
                            "4. Revenez ici : bouton 3 « Installer le .xpi signé ».")

    def ext_install_xpi(self):
        ff = self.firefox_path()
        if not ff:
            return
        x = filedialog.askopenfilename(filetypes=[("Extension Firefox", "*.xpi")])
        if x:
            subprocess.Popen([ff, x])

    def dlg_extension(self):
        win = tk.Toplevel(self.root)
        win.title("Extension Firefox — une IP par conteneur")
        win.transient(self.root)
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", wraplength=540, font=("Segoe UI", 10), pady=10, padx=14,
                 text="À QUOI ÇA SERT\nDans UNE seule fenêtre Firefox, chaque conteneur (onglets de couleur) peut "
                      "sortir par une connexion différente : box, 4G du téléphone, VPN…\n\n"
                      "COMMENT\n1. Réseau → « Mes connexions Internet » : créez vos routes.\n"
                      "2. Installez l'extension (boutons ci-dessous). Un bouton SoNiC_0TAB0 apparaît dans Firefox.\n"
                      "3. Dans ce bouton : choisissez une route par conteneur, cliquez « Tester » : l'IP "
                      "s'affiche. Deux conteneurs avec la même IP = même accès.").pack()
        for txt, cmd in (("1.  Essayer tout de suite (temporaire)", self.ext_temp),
                         ("2.  Installer pour de bon (gratuit, signature Mozilla)", self.ext_sign),
                         ("3.  J'ai le fichier .xpi signé : l'installer", self.ext_install_xpi),
                         ("Ouvrir le dossier de l'extension",
                          lambda: self.ext_dir() and os.startfile(self.ext_dir()))):
            ttk.Button(win, text=txt, command=cmd, width=52).pack(padx=14, pady=3)
        tk.Label(win, bg=BG, fg=MUTED, wraplength=540, justify="left", font=("Segoe UI", 8), pady=8, padx=14,
                 text="Firefox exige des extensions signées par Mozilla (la signature « non répertoriée » est "
                      "gratuite). Alternative sans extension : « Nouveau navigateur » lance un Firefox séparé avec "
                      "sa propre route, intégré comme onglet.").pack()

    # ------------------------------------------------------------------ démarrage
    def bring_front(self, maximize=False):
        r = self.root
        r.deiconify()
        if maximize:
            try:
                r.state("zoomed")
            except tk.TclError:
                pass
        r.lift()
        r.attributes("-topmost", True)
        r.after(700, lambda: r.attributes("-topmost", False))
        w.force_foreground(r.winfo_id())

    def start_hotkeys(self):
        if self.hotkeys:
            self.hotkeys.stop()
        self.scoped_on = False
        self.hotkeys = w.Hotkeys(core.hotkey_map(self.cfg), self.q, core.scoped_map(self.cfg))
        self.hotkeys.start()

    # --------------------------------------------------------------------- routes
    def start_routes(self):
        for r in self.cfg["routes"]:
            self.start_route(r)

    def backup_of(self, r):
        """Route de secours choisie pour r (autre route, donc autre carte réseau), ou None."""
        bp = r.get("backup_port")
        return next((x for x in self.cfg["routes"] if x["port"] == bp and x["port"] != r["port"]), None) if bp else None

    def start_route(self, r):
        if r["port"] in self.routes:
            return
        fb = []
        b = self.backup_of(r)
        if b:
            fb.append((b["name"], w.make_bind_hook(b["iface_index"], b.get("ip"))))
        s = core.RouteServer(r["port"], w.make_bind_hook(r["iface_index"], r.get("ip")), r["name"],
                             fallbacks=fb, on_switch=lambda t: self.q.put(("msg", "⚠ " + t)))
        s.start()
        s.ready.wait(1.5)
        if s.error:
            self.status.set(f"Route « {r['name']} » : port {r['port']} indisponible ({s.error})")
            return
        self.routes[r["port"]] = s

    def stop_route(self, port):
        s = self.routes.pop(port, None)
        if s:
            s.stop()

    def route_labels(self):
        return {f"Route · {r['name']} ({r.get('ip', '')}) → socks5://127.0.0.1:{r['port']}":
                f"socks5://127.0.0.1:{r['port']}" for r in self.cfg["routes"]}

    # ------------------------------------------------------------- tâches en file
    def enqueue(self, fn):
        self.job_queue.append(fn)
        self.pump()

    def pump(self):
        if self.job_busy or not self.job_queue:
            return
        self.job_busy = True
        fn = self.job_queue.pop(0)

        def done(*_):
            self.job_busy = False
            self.root.after(150, self.pump)
        try:
            fn(done)
        except Exception as e:
            log(traceback.format_exc())
            self.status.set(f"Erreur : {e}")
            done()

    # ---------------------------------------------------------------- embarquement
    def embed(self, hwnd, proxy="", label="", launch=None, quiet=False):
        if any(t["hwnd"] == hwnd for t in self.tabs) or hwnd in self.failed:
            return None
        pid = w.pid_of(hwnd)
        title = w.title_of(hwnd)
        r = w.embed_window(hwnd, self.host_hwnd)
        if not r["ok"]:
            self.failed.add(hwnd)
            self.embed_error = w.explain_embed_failure(pid, r["err"])
            log(f"embed échec hwnd={hwnd} pid={pid} titre={title!r} err={r['err']}")
            if quiet:
                self.status.set(f"Intégration impossible : {title[:50]}")
            else:
                messagebox.showerror("SoNiC_0TAB0 — intégration impossible", self.embed_error)
            return None
        tab = {"hwnd": hwnd, "title": title, "label": label, "exe": w.exe_of(pid),
               "exe_path": w.exe_path_of(pid), "gid": None, "proxy": proxy, "launch": launch,
               "style": r["style"], "rect": r["rect"], "leak": False,
               "auto_s": 0, "next_reload": 0.0, "reload_on_select": False}
        self.tabs.append(tab)
        self.show_placeholder(False)
        self.select(tab)
        return tab

    def release(self, tab, quiet=False, at=None):
        rect = tab["rect"]
        if at:                                   # posée là où l'on a lâché la souris
            wd, ht = max(500, rect[2] - rect[0]), max(350, rect[3] - rect[1])
            rect = (at[0] - 140, at[1] - 20, at[0] - 140 + wd, at[1] - 20 + ht)
        w.release_window(tab["hwnd"], tab["style"], rect)
        if not quiet:
            self.forget(tab)

    def close_window(self, tab):
        w.post_close(tab["hwnd"])

    def forget(self, tab):
        if tab not in self.tabs:
            return
        i = self.tabs.index(tab)
        self.tabs.remove(tab)
        self.prune_groups()
        if self.current is tab:
            self.current = None
            if self.tabs:
                self.select(self.tabs[min(i, len(self.tabs) - 1)])
            else:
                self.show_placeholder(True)
                self.host.configure(bg=BG)
                self.root.title("SoNiC_0TAB0")
        self.redraw()

    def visible_set(self):
        c = self.current
        if not c:
            return []
        g = self.groups.get(c["gid"]) if c["gid"] else None
        if g and g.get("split"):
            return [t for t in self.tabs if t["gid"] == c["gid"]]
        return [c]

    def select(self, tab, focus=True):
        self.current = tab
        vis = self.visible_set()
        for t in self.tabs:
            w.show(t["hwnd"], w.SW_SHOWNA if t in vis else w.SW_HIDE)
        self.layout()
        if focus:
            w.focus_window(tab["hwnd"])
        self.root.title(f"SoNiC_0TAB0 — {tab['label'] or tab['title']}")
        self.redraw()

    def layout(self):
        vis = self.visible_set()
        if not vis:
            return
        g = self.groups.get(self.current["gid"]) if self.current["gid"] else None
        mode = g.get("split") if g else None
        rects = core.tile_layout(len(vis), mode, self.host.winfo_width(), self.host.winfo_height(), 3)
        for t, (x, y, ww, hh) in zip(vis, rects):
            if w.is_window(t["hwnd"]):
                w.move(t["hwnd"], x, y, ww, hh)
        self.host.configure(bg=g["color"] if (g and mode) else BG)

    def relayout(self):
        if self.current in self.tabs:
            self.select(self.current, focus=False)

    def switch_to(self, tab):
        """Changement d'onglet voulu par l'utilisateur (clavier, molette) : sélectionne puis, si demandé, actualise."""
        prev = self.current
        self.select(tab)
        if tab is not prev:
            self.after_switch(tab)

    def cycle(self, d):
        if self.tabs and self.current in self.tabs:
            self.switch_to(self.tabs[(self.tabs.index(self.current) + d) % len(self.tabs)])

    # ------------------------------------------------------------- actualisation (F5)
    def after_switch(self, tab):
        if self.cfg.get("reload_on_select") or tab.get("reload_on_select"):
            self.root.after(250, lambda: self.reload_tab(tab))

    def reload_tab(self, tab=None, hard=False, _n=0):
        """Équivalent d'un F5 (Ctrl+F5 si hard) dans le navigateur de l'onglet.
        La touche n'est envoyée que si SoNiC_0TAB0 est au premier plan et que Ctrl/Alt/Maj sont relâchées."""
        tab = tab or self.current
        if not tab or tab not in self.tabs or not w.is_window(tab["hwnd"]):
            return
        if tab not in self.visible_set():
            self.select(tab, focus=False)
        if not w.is_foreground(self.top_hwnd):
            if _n == 0:
                self.bring_front(False)
            if _n < 8:
                self.root.after(200, lambda: self.reload_tab(tab, hard, _n + 1))
            else:
                self.status.set("Actualisation annulée : SoNiC_0TAB0 n'a pas pu passer au premier plan.")
            return
        if w.modifiers_down():                            # attend le relâchement de Ctrl+Alt de l'éventuel raccourci
            if _n < 12:
                self.root.after(120, lambda: self.reload_tab(tab, hard, _n + 1))
            else:
                self.status.set("Actualisation annulée : relâchez Ctrl / Alt / Maj puis réessayez.")
            return
        w.focus_window(tab["hwnd"])

        def send():
            if w.is_window(tab["hwnd"]) and w.is_foreground(self.top_hwnd):
                w.press_key(0x74, ctrl=hard)                  # VK_F5
                tab["next_reload"] = time.time() + tab.get("auto_s", 0)
                self.status.set(f"Actualisé : {self.trunc(tab['label'] or tab['title'], 60)}")
        self.root.after(120, send)

    def set_auto_reload(self, tab, secs):
        tab["auto_s"] = secs
        tab["next_reload"] = time.time() + secs
        self.status.set(f"Actualisation automatique : {dict(core.RELOAD_CHOICES)[secs].lower()} — « {self.trunc(tab['label'] or tab['title'], 40)} ».")
        self.redraw()

    def toggle_reload_on_select(self, tab):
        tab["reload_on_select"] = not tab.get("reload_on_select")
        self.redraw()

    def toggle_global_reload_on_select(self):
        self.cfg["reload_on_select"] = bool(self.reload_sel_var.get())
        core.save_config(self.cfg)
        self.status.set("Actualisation à chaque changement d'onglet : " + ("activée." if self.cfg["reload_on_select"] else "désactivée."))

    def auto_reload_tick(self):
        """Actualisations automatiques dues, uniquement pour les onglets visibles et quand SoNiC_0TAB0 est actif."""
        now = time.time()
        if not w.is_foreground(self.top_hwnd):
            return
        vis = self.visible_set() if self.current in self.tabs else []
        for t in vis:
            if t.get("auto_s") and now >= t.get("next_reload", 0):
                t["next_reload"] = now + t["auto_s"]            # reprogrammé d'abord : pas de rafale si l'envoi échoue
                self.reload_tab(t)
                break                                            # une seule à la fois

    # ------------------------------------------------------------------- groupes
    def new_group(self):
        self.gcount += 1
        gid = f"g{self.gcount}"
        self.groups[gid] = {"name": f"Groupe {self.gcount}", "color": PALETTE[(self.gcount - 1) % 8][1],
                            "collapsed": False, "split": None}
        return gid

    def prune_groups(self):
        used = {t["gid"] for t in self.tabs}
        for gid in list(self.groups):
            if gid not in used:
                del self.groups[gid]

    def normalize(self):
        seen, new = set(), []
        for t in self.tabs:
            g = t["gid"]
            if g is None:
                new.append(t)
            elif g not in seen:
                seen.add(g)
                new.extend(x for x in self.tabs if x["gid"] == g)
        self.tabs = new

    def units(self):
        out = []
        for t in self.tabs:
            if out and t["gid"] is not None and out[-1][0] == t["gid"]:
                out[-1][1].append(t)
            else:
                out.append((t["gid"], [t]))
        return out

    # -------------------------------------------------------------------- dessin
    def trunc(self, text, maxpx):
        text = text or ""
        if maxpx <= 10:
            return ""
        if self.font.measure(text) <= maxpx:
            return text
        n = max(1, min(len(text), int(maxpx / 6)))
        while n > 1 and self.font.measure(text[:n] + "…") > maxpx:
            n -= 1
        return text[:n] + "…"

    def poly(self, x0, y0, x1, y1, r, top_only=False, **kw):
        if top_only:
            pts = [x0, y1, x0, y0 + r, x0 + 2, y0 + 2, x0 + r, y0, x1 - r, y0, x1 - 2, y0 + 2, x1, y0 + r, x1, y1]
        else:
            pts = [x0, y0 + r, x0 + 2, y0 + 2, x0 + r, y0, x1 - r, y0, x1 - 2, y0 + 2, x1, y0 + r,
                   x1, y1 - r, x1 - 2, y1 - 2, x1 - r, y1, x0 + r, y1, x0 + 2, y1 - 2, x0, y1 - r]
        return self.bar.create_polygon(pts, **kw)

    def redraw(self):
        c = self.bar
        c.delete("all")
        self.hits = []
        W = max(c.winfo_width(), 420)
        units = self.units()
        chipw, slots = {}, 0
        for gid, ts in units:
            if gid:
                g = self.groups[gid]
                txt = g["name"] + (f" ({len(ts)})" if g["collapsed"] else "")
                chipw[gid] = min(170, self.fontb.measure(txt) + 22)
            if not (gid and self.groups[gid]["collapsed"]):
                slots += len(ts)
        reserved = 112 + 34                                   # marqueur + ☰ / bouton ＋
        avail = W - 12 - reserved - sum(chipw.values()) - 8 * len(units)
        tw = max(70, min(210, avail / slots if slots else 210))
        x = 8
        vis = self.visible_set()
        for gid, ts in units:
            g = self.groups.get(gid) if gid else None
            if g:
                collapsed = g["collapsed"]
                cw = chipw[gid]
                self.poly(x, 9, x + cw, 27, 5, fill=g["color"], outline="")
                label = g["name"] + (f" ({len(ts)})" if collapsed else "") + ("  ▥" if g.get("split") else "")
                c.create_text(x + 10, 18, anchor="w", fill="#10131f", font=self.fontb,
                              text=self.trunc(label, cw - 14))
                self.hits.append(((x, 9, x + cw, 27), "group", gid))
                x += cw + 4
                if collapsed:
                    x += 6
                    continue
            x0 = x
            for t in ts:
                sel = t is self.current
                fill = TABSEL if sel else TABVIS if t in vis else TAB
                self.poly(x, TAB_Y0, x + tw, TAB_Y1, 8, top_only=True, fill=fill, outline="")
                if sel:
                    c.create_line(x + 8, TAB_Y0 + 1, x + tw - 8, TAB_Y0 + 1, fill=ACCENT, width=2)
                c.create_oval(x + 9, 17, x + 17, 25, fill=EXE_COLORS.get(t["exe"], "#8b93b8"), outline="")
                name = (("⚠ " if t["leak"] else "◈ " if t["proxy"] else "") +
                        ("⟳ " if t.get("auto_s") or t.get("reload_on_select") else "") + (t["label"] or t["title"] or t["exe"]))
                c.create_text(x + 24, 20, anchor="w", fill=ALERT if t["leak"] else FG if sel else MUTED,
                              font=self.font, text=self.trunc(name, tw - 50))
                c.create_text(x + tw - 13, 20, text="✕", fill=MUTED, font=self.font)
                self.hits.append(((x, TAB_Y0, x + tw, TAB_Y1), "tab", t))
                self.hits.append(((x + tw - 24, TAB_Y0, x + tw, TAB_Y1), "close", t))
                if self.dragging and self.drop and self.drop[0] is t:
                    if self.drop[1] == "group":
                        c.create_rectangle(x, TAB_Y0, x + tw, TAB_Y1, outline=ACCENT, width=2)
                    else:
                        bx = x if self.drop[1] == "before" else x + tw
                        c.create_rectangle(bx - 2, TAB_Y0, bx + 2, TAB_Y1, fill=ACCENT, outline="")
                x += tw + 2
            if g:
                c.create_rectangle(x0, BAR_H - 3, x - 2, BAR_H, fill=g["color"], outline="")
            x += 6
        px = min(x + 2, W - reserved - 8)
        self.poly(px, 9, px + 28, 31, 6, fill=TAB, outline="")
        c.create_text(px + 14, 20, text="＋", fill=FG, font=("Segoe UI", 12))
        self.hits.append(((px, 9, px + 28, 31), "plus", None))
        c.create_window(W - 80, BAR_H // 2, window=self.marker)
        self.poly(W - 40, 7, W - 8, 31, 6, fill=TAB, outline="")
        c.create_text(W - 24, 19, text="☰", fill=FG, font=("Segoe UI", 12))
        self.hits.append(((W - 40, 7, W - 8, 31), "menu", None))
        if self.dragging and self.press:
            ex = self.mouse[0]
            t = self.press[0]
            out = self.drop and self.drop[1] == "detach"
            self.poly(ex - 60, TAB_Y0 + 2, ex + 60, TAB_Y1 - 2, 6, fill=ALERT if out else TABSEL, outline=ACCENT)
            c.create_text(ex, 20, fill=FG, font=self.font,
                          text="⇱ Relâcher = détacher" if out else self.trunc(t["label"] or t["title"], 108))

    def hit(self, x, y):
        for rect, kind, obj in reversed(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return kind, obj, rect
        return None

    # -------------------------------------------------------------------- souris
    def on_press(self, e):
        self.press, self.dragging, self.drop = None, False, None
        h = self.hit(e.x, e.y)
        if not h:
            return
        kind, obj, _ = h
        if kind == "close":
            self.close_window(obj)
        elif kind == "tab":
            self.press_prev = self.current
            self.select(obj, focus=False)        # focus donné au relâchement, sinon le glisser est coupé
            self.press = (obj, e.x, e.y)
        elif kind == "group":
            self.groups[obj]["collapsed"] = not self.groups[obj]["collapsed"]
            self.redraw()
        elif kind == "plus":
            self.plus_menu.tk_popup(e.x_root, e.y_root + 14)
        elif kind == "menu":
            self.menu.tk_popup(e.x_root - 110, e.y_root + 14)

    def on_motion(self, e):
        if not self.press:
            return
        if not self.dragging and (abs(e.x - self.press[1]) > 6 or abs(e.y - self.press[2]) > 6):
            self.dragging = True
        if not self.dragging:
            return
        self.mouse = (e.x, e.y)
        tab = self.press[0]
        h = self.hit(e.x, e.y)
        self.drop = None
        outside = e.y > BAR_H + 30 or e.y < -25 or e.x < -25 or e.x > self.bar.winfo_width() + 25
        if outside:
            self.drop = (None, "detach")
            self.status.set("Relâchez ici pour sortir l'onglet de SoNiC_0TAB0 (la fenêtre redevient indépendante).")
        elif h and h[0] in ("tab", "close") and h[1] is not tab:
            t = h[1]
            rect = next(r for r, k, o in self.hits if k == "tab" and o is t)
            rel = (e.x - rect[0]) / max(1, rect[2] - rect[0])
            self.drop = (t, "before" if rel < 0.3 else "after" if rel > 0.7 else "group")
        elif not h and e.x > 8:
            self.drop = (None, "end")
        self.redraw()

    def on_release(self, e):
        tab = self.press[0] if self.press else None
        was_drag, drop = self.dragging, self.drop
        self.press, self.dragging, self.drop = None, False, None
        if tab and tab in self.tabs:
            if was_drag and drop and drop[1] == "detach":
                self.release(tab, at=(e.x_root, e.y_root))
                self.status.set("Onglet détaché : la fenêtre est de nouveau indépendante.")
                return
            if was_drag and drop:
                self.apply_drop(tab, drop)
                self.relayout()
            elif not was_drag:
                w.focus_window(tab["hwnd"])      # simple clic : le clavier va au navigateur
                if tab is not getattr(self, "press_prev", tab):
                    self.after_switch(tab)
        self.redraw()

    def on_middle(self, e):
        h = self.hit(e.x, e.y)
        if h and h[0] in ("tab", "close"):
            self.close_window(h[1])

    def on_double(self, e):
        h = self.hit(e.x, e.y)
        if h and h[0] == "tab":
            self.rename_tab(h[1])

    def on_wheel(self, e):
        self.cycle(-1 if e.delta > 0 else 1)

    def apply_drop(self, tab, drop):
        target, mode = drop
        if mode == "end":
            tab["gid"] = None
            self.tabs.remove(tab)
            self.tabs.append(tab)
        elif mode == "group":
            if target["gid"] is None:
                target["gid"] = self.new_group()
            tab["gid"] = target["gid"]
            self.tabs.remove(tab)
            self.tabs.insert(max(i for i, t in enumerate(self.tabs) if t["gid"] == target["gid"]) + 1, tab)
        else:
            old = tab["gid"]
            self.tabs.remove(tab)
            self.tabs.insert(self.tabs.index(target) + (1 if mode == "after" else 0), tab)
            if old != target["gid"]:
                tab["gid"] = None
        self.normalize()
        self.prune_groups()

    # ---------------------------------------------------------------- menus contextuels
    def color_menu(self, parent, gid):
        m = tk.Menu(parent, tearoff=0)
        for name, col in PALETTE:
            m.add_command(label="■ " + name, foreground=col, command=lambda c=col: self.set_color(gid, c))
        return m

    def split_menu(self, parent, gid):
        m = tk.Menu(parent, tearoff=0)
        for label, mode in SPLITS:
            m.add_command(label=label, command=lambda md=mode: self.set_split(gid, md))
        return m

    def set_color(self, gid, col):
        self.groups[gid]["color"] = col
        self.relayout()
        self.redraw()

    def set_split(self, gid, mode):
        self.groups[gid]["split"] = mode
        first = next((t for t in self.tabs if t["gid"] == gid), None)
        if first and (self.current is None or self.current["gid"] != gid):
            self.select(first)
        else:
            self.relayout()
        self.redraw()

    def rename_group(self, gid):
        v = simpledialog.askstring("Groupe", "Nom du groupe :", initialvalue=self.groups[gid]["name"])
        if v:
            self.groups[gid]["name"] = v
            self.redraw()

    def rename_tab(self, tab):
        v = simpledialog.askstring("Onglet", "Nom de l'onglet (vide = titre automatique) :",
                                   initialvalue=tab["label"] or tab["title"])
        if v is not None:
            tab["label"] = v.strip()
            self.redraw()

    def on_right(self, e):
        h = self.hit(e.x, e.y)
        if not h:
            return
        kind, obj, _ = h
        m = tk.Menu(self.root, tearoff=0)
        if kind in ("tab", "close"):
            t = obj
            m.add_command(label="Actualiser   (F5)", command=lambda: self.reload_tab(t))
            m.add_command(label="Actualiser sans cache   (Ctrl+F5)", command=lambda: self.reload_tab(t, hard=True))
            ar = tk.Menu(m, tearoff=0)
            cur = tk.IntVar(value=t.get("auto_s", 0))
            for secs, lbl in core.RELOAD_CHOICES:
                ar.add_radiobutton(label=lbl, value=secs, variable=cur, command=lambda s_=secs: self.set_auto_reload(t, s_))
            ar.add_separator()
            sel = tk.BooleanVar(value=bool(t.get("reload_on_select")))
            ar.add_checkbutton(label="À chaque sélection de l'onglet", variable=sel,
                               command=lambda: self.toggle_reload_on_select(t))
            m.add_cascade(label="Actualisation automatique", menu=ar)
            m.add_separator()
            m.add_command(label="Renommer l'onglet…", command=lambda: self.rename_tab(t))
            m.add_command(label="Nouveau groupe avec cet onglet",
                          command=lambda: (t.update(gid=self.new_group()), self.normalize(), self.redraw()))
            if t["gid"]:
                m.add_command(label="Retirer du groupe",
                              command=lambda: (t.update(gid=None), self.prune_groups(), self.relayout(), self.redraw()))
                m.add_cascade(label="Affichage du groupe", menu=self.split_menu(m, t["gid"]))
                m.add_cascade(label="Couleur du groupe", menu=self.color_menu(m, t["gid"]))
                m.add_command(label="Renommer le groupe…", command=lambda: self.rename_group(t["gid"]))
            if self.cfg["features"]["rotation"] and t.get("launch"):
                m.add_command(label="Nouvelle IP (rotation)", command=lambda: self.rotate_ip(False, [t]))
            m.add_separator()
            m.add_command(label="Détacher (rendre la fenêtre)", command=lambda: self.release(t))
            m.add_command(label="Fermer la fenêtre", command=lambda: self.close_window(t))
        elif kind == "group":
            gid = obj
            m.add_cascade(label="Affichage : côte à côte…", menu=self.split_menu(m, gid))
            m.add_command(label="Renommer le groupe…", command=lambda: self.rename_group(gid))
            m.add_cascade(label="Couleur", menu=self.color_menu(m, gid))
            m.add_command(label="Replier / Déplier", command=lambda: (
                self.groups[gid].update(collapsed=not self.groups[gid]["collapsed"]), self.redraw()))
            m.add_command(label="Dissoudre le groupe", command=lambda: (
                [t.update(gid=None) for t in self.tabs if t["gid"] == gid], self.prune_groups(),
                self.relayout(), self.redraw()))
            m.add_command(label="Détacher tout le groupe",
                          command=lambda: [self.release(t) for t in [x for x in self.tabs if x["gid"] == gid]])
        else:
            return
        m.tk_popup(e.x_root, e.y_root)

    # ----------------------------------------------------------- capture / lancement
    def dlg_capture(self):
        win = tk.Toplevel(self.root)
        win.title("Capturer des fenêtres")
        win.geometry("640x420")
        win.transient(self.root)
        tk.Label(win, text="Sélectionnez une ou plusieurs fenêtres ouvertes (Ctrl+clic), puis « Ajouter ».",
                 anchor="w").pack(fill="x", padx=8, pady=(8, 0))
        lb = tk.Listbox(win, selectmode="extended", font=("Segoe UI", 9))
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        items = []

        def refresh():
            items.clear()
            lb.delete(0, "end")
            own = {t["hwnd"] for t in self.tabs}
            for h, t, exe, pid in w.list_windows():
                if h not in own:
                    items.append(h)
                    lb.insert("end", f"[{exe}]  {t}")

        def add():
            sel = list(lb.curselection())
            win.destroy()
            for i in sel:
                self.embed(items[i])
        row = tk.Frame(win)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row, text="Actualiser", command=refresh).pack(side="left")
        ttk.Button(row, text="Ajouter la sélection", command=add).pack(side="right")
        lb.bind("<Double-Button-1>", lambda e: add())
        refresh()

    def dlg_launch(self):
        browsers = core_browsers()
        labels = self.route_labels()
        win = tk.Toplevel(self.root)
        win.title("Nouveau navigateur isolé")
        win.transient(self.root)
        win.resizable(False, False)
        f = ttk.Frame(win, padding=12)
        f.pack()
        names = list(browsers)
        bname = tk.StringVar(value=self.cfg.get("browser") or (names[0] if names else ""))
        prof = tk.StringVar(value=self.cfg.get("profile", "profil1"))
        page = tk.StringVar(value="Page vide")
        proxy = tk.StringVar(value="")
        ttk.Label(f, text="Navigateur").grid(row=0, column=0, sticky="w", pady=3)
        cb = ttk.Combobox(f, textvariable=bname, values=names, width=40)
        cb.grid(row=0, column=1, pady=3)

        def browse():
            p = filedialog.askopenfilename(filetypes=[("Exécutable", "*.exe")])
            if p:
                n = os.path.splitext(os.path.basename(p))[0]
                browsers[n] = p
                cb["values"] = list(browsers)
                bname.set(n)
        ttk.Button(f, text="…", width=3, command=browse).grid(row=0, column=2, padx=4)
        ttk.Label(f, text="Profil (cookies isolés)").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=prof, width=43).grid(row=1, column=1, pady=3)
        ttk.Label(f, text="Page de départ").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(f, textvariable=page, values=list(TEST_PAGES), width=40).grid(row=2, column=1, pady=3)
        ttk.Label(f, text="Route / proxy").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Combobox(f, textvariable=proxy, values=list(labels) + self.cfg.get("proxies", []),
                     width=40).grid(row=3, column=1, pady=3)
        ttk.Button(f, text="⚙", width=3, command=lambda: (win.destroy(), self.dlg_connections())).grid(
            row=3, column=2, padx=4)
        ttk.Label(f, foreground="#666", justify="left", wraplength=440,
                  text=("Profil : un nom par compte (cookies séparés).\n"
                        + ("Route : déroulez la liste et choisissez « Route · … » : l'adresse se remplit toute seule "
                           "(elle ressemble à socks5://127.0.0.1:10810 — 127.0.0.1 = votre PC, le numéro = la route). "
                           if labels else
                           "Route : aucune route créée pour l'instant. Cliquez ⚙ (à droite) pour détecter vos connexions "
                           "(box, 4G du téléphone…) et créer vos routes. ")
                        + "Vide = connexion normale. Opera avec VPN : laissez vide et activez le VPN d'Opera dans ce profil.")
                  ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        def go():
            path = browsers.get(bname.get())
            if not path or not os.path.isfile(path):
                messagebox.showerror("SoNiC_0TAB0", "Choisissez un navigateur valide.", parent=win)
                return
            raw = proxy.get().strip()
            px = core.normalize_proxy(labels.get(raw, raw))
            url = TEST_PAGES.get(page.get(), page.get().strip() or "about:blank")
            self.cfg.update(browser=bname.get(), profile=prof.get())
            if raw and raw not in labels:
                self.cfg["proxies"] = ([raw] + [p for p in self.cfg["proxies"] if p != raw])[:10]
            core.save_config(self.cfg)
            win.destroy()
            self.launch(path, prof.get() or "profil1", url, px)
        ttk.Button(f, text="Lancer et intégrer", command=go).grid(row=5, column=0, columnspan=3, pady=(12, 0))

    def launch(self, path, profile, url, proxy, restore=False, on_done=None):
        try:
            cmd = core.build_command(path, profile, url, proxy, restore, self.cfg["block_webrtc"])
        except Exception as ex:
            log(traceback.format_exc())
            messagebox.showerror("SoNiC_0TAB0", f"Impossible de préparer le profil :\n{ex}")
            if on_done:
                on_done(None)
            return
        exe = os.path.basename(path).lower()
        names = {exe} | ({"opera.exe", "launcher.exe"} if "opera" in exe else set())
        info = {"path": path, "profile": profile, "url": url, "proxy": proxy}
        label = profile + (f" · {proxy.split('//')[-1]}" if proxy else "")
        self.spawn(cmd, names, info, label, proxy, on_done)

    def spawn(self, cmd, names, info, label, proxy, on_done=None):
        before = {h for h, *_ in w.list_windows()}          # AVANT le lancement (évite une course)
        self.embed_error = ""
        try:
            proc = subprocess.Popen(cmd)
        except Exception as ex:
            log(traceback.format_exc())
            messagebox.showerror("SoNiC_0TAB0", f"Échec du lancement :\n{ex}")
            if on_done:
                on_done(None)
            return
        deadline = time.time() + 30
        self.status.set(f"Lancement de {label}…")

        def look():
            for h, t, e, pid in w.list_windows():
                if h in before or h in self.failed:
                    continue
                if pid == proc.pid or e in names:
                    tab = self.embed(h, proxy=proxy, label=label, launch=info, quiet=True)
                    if tab:
                        self.status.set(f"Intégré : {t}")
                        if on_done:
                            on_done(tab)
                        return
            if time.time() < deadline:
                self.root.after(400, look)
                return
            if self.embed_error:
                messagebox.showerror("SoNiC_0TAB0 — intégration impossible", self.embed_error)
            else:
                self.status.set("Fenêtre introuvable (délai dépassé) — utilisez ＋ → Capturer une fenêtre.")
            if on_done:
                on_done(None)
        self.root.after(700, look)

    # -------------------------------------------------------------------- sessions
    def session_data(self):
        return {"version": 3, "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
                "groups": {g: dict(v) for g, v in self.groups.items()},
                "tabs": [{"title": t["title"], "label": t["label"], "gid": t["gid"], "exe": t["exe"],
                          "exe_path": t["exe_path"], "proxy": t["proxy"], "launch": t["launch"],
                          "auto_s": t.get("auto_s", 0), "reload_on_select": bool(t.get("reload_on_select")),
                          "current": t is self.current} for t in self.tabs]}

    def save_now(self, name=None):
        n = core.save_session_file(name or time.strftime("Session %Y-%m-%d %Hh%M"), self.session_data())
        self.status.set(f"Session « {n} » sauvegardée ({len(self.tabs)} onglets).")
        return n

    def session_save_dialog(self):
        if not self.tabs:
            messagebox.showinfo("Session", "Aucun onglet ouvert : rien à sauvegarder.")
            return
        name = simpledialog.askstring("Session", "Nom de la session :",
                                      initialvalue=time.strftime("Session %Y-%m-%d %Hh%M"))
        if name:
            self.save_now(name)

    def session_restore_dialog(self):
        names = core.list_sessions()
        if not names:
            messagebox.showinfo("Sessions", "Aucune session sauvegardée.")
            return
        win = tk.Toplevel(self.root)
        win.title("Restaurer une session")
        win.transient(self.root)
        lb = tk.Listbox(win, width=46, height=12)
        lb.pack(padx=8, pady=8)
        for n in names:
            lb.insert("end", "(dernière session automatique)" if n == "_derniere" else n)

        def go():
            if lb.curselection():
                n = names[lb.curselection()[0]]
                win.destroy()
                try:
                    self.restore_session(core.load_session_file(n))
                except Exception as e:
                    log(traceback.format_exc())
                    messagebox.showerror("Session", f"Restauration impossible :\n{e}")

        def delete():
            if lb.curselection():
                i = lb.curselection()[0]
                try:
                    os.remove(os.path.join(core.SESSIONS, names[i] + ".json"))
                except OSError:
                    pass
                names.pop(i)
                lb.delete(i)
        row = tk.Frame(win)
        row.pack(pady=(0, 8))
        ttk.Button(row, text="Restaurer", command=go).pack(side="left", padx=4)
        ttk.Button(row, text="Supprimer", command=delete).pack(side="left", padx=4)
        lb.bind("<Double-Button-1>", lambda e: go())

    def restore_last(self, quiet=False):
        try:
            data = core.load_session_file("_derniere")
        except FileNotFoundError:
            if not quiet:
                messagebox.showinfo("Session", "Aucune session automatique pour l'instant.\n\nElle est enregistrée à la "
                                    "fermeture de SoNiC_0TAB0 et toutes les 2 minutes, dès qu'un onglet est ouvert.")
            return
        except Exception as e:
            log(traceback.format_exc())
            messagebox.showerror("Session", f"Fichier de session illisible :\n{e}")
            return
        if not data.get("tabs"):
            if not quiet:
                messagebox.showinfo("Session", "La dernière session ne contient aucun onglet.")
            return
        try:
            self.restore_session(data)
        except Exception as e:
            log(traceback.format_exc())
            messagebox.showerror("Session", f"Restauration impossible :\n{e}")

    def apply_meta(self, tab, meta, idx=None):
        tab["label"] = meta.get("label", "") or tab["label"]
        tab["auto_s"] = int(meta.get("auto_s", 0) or 0)
        tab["reload_on_select"] = bool(meta.get("reload_on_select"))
        tab["next_reload"] = time.time() + tab["auto_s"]
        tab["order"] = meta.get("order")
        gid = meta.get("gid")
        if gid:
            if gid not in self.groups and meta.get("group"):
                self.groups[gid] = dict(meta["group"])
            tab["gid"] = gid if gid in self.groups else None
        if idx is not None and tab in self.tabs:
            self.tabs.remove(tab)
            self.tabs.insert(min(idx, len(self.tabs)), tab)
        self.normalize()
        if meta.get("current") and tab in self.tabs:
            self.select(tab)
        else:
            self.relayout()
        self.redraw()

    def restore_session(self, data):
        saved = data.get("tabs", [])
        gmap = {}
        for old, g in data.get("groups", {}).items():
            n = self.new_group()
            self.groups[n].update({k: g[k] for k in ("name", "color", "collapsed", "split") if k in g})
            gmap[old] = n
        open_profiles = {t["launch"]["profile"] for t in self.tabs if t.get("launch")}
        plans = core.plan_restore(saved, w.list_windows(), {t["hwnd"] for t in self.tabs}, open_profiles)
        report = {"missing": [], "already": []}

        def name_of(ts):
            return ts.get("label") or ts.get("title") or ts.get("exe") or "?"

        def job_for(plan, meta):
            ts = plan[1]

            def job(done):
                def ok(tab):
                    if tab:
                        self.apply_meta(tab, meta)
                    else:
                        report["missing"].append(name_of(ts))
                    done()
                if plan[0] == "launch":
                    L = ts["launch"]
                    if not os.path.isfile(L["path"]):
                        report["missing"].append(name_of(ts) + " (navigateur introuvable)")
                        return done()
                    self.launch(L["path"], L["profile"], L.get("url", ""), L.get("proxy", ""), True, ok)
                else:
                    exe = ts["exe"]
                    names = {exe} | ({"opera.exe", "launcher.exe"} if exe in ("opera.exe", "launcher.exe") else set())
                    self.spawn(core.reopen_command(ts["exe_path"]), names, None, ts.get("label", ""),
                               ts.get("proxy", ""), ok)
            return job

        for idx, plan in enumerate(plans):
            ts = plan[1]
            meta = {"label": ts.get("label", ""), "gid": gmap.get(ts.get("gid")), "order": idx,
                    "current": ts.get("current"),
                    "auto_s": ts.get("auto_s", 0), "reload_on_select": ts.get("reload_on_select", False)}
            if plan[0] == "embed":
                t = self.embed(plan[2], proxy=ts.get("proxy", ""), quiet=True)
                if t:
                    self.apply_meta(t, meta)
                else:
                    report["missing"].append(name_of(ts))
            elif plan[0] in ("launch", "reopen"):
                self.enqueue(job_for(plan, meta))
            elif plan[0] == "already":
                report["already"].append(name_of(ts))
            else:
                report["missing"].append(name_of(ts))

        def finish(done):
            self.tabs.sort(key=lambda t: t["order"] if t.get("order") is not None else 10 ** 6)
            self.normalize()
            self.prune_groups()
            self.relayout()
            self.redraw()
            msg = f"Session restaurée : {len(self.tabs)} onglet(s)."
            if report["already"]:
                msg += f" Déjà ouverts : {len(report['already'])}."
            self.status.set(msg)
            if report["missing"]:
                messagebox.showinfo("Session", "Non restaurés :\n- " + "\n- ".join(report["missing"]) +
                                    "\n\n(Fenêtres capturées à la main d'applications autres que des navigateurs : "
                                    "rouvrez-les puis capturez-les de nouveau.)")
            done()
        self.enqueue(finish)

    # ------------------------------------------------------------ rotation / fuites
    def rotate_ip(self, all_tabs, tabs=None):
        rot = self.cfg["rotation"]
        if rot["mode"] == "tor":
            threading.Thread(target=self._tor_worker, daemon=True).start()
            return
        pool = [core.normalize_proxy(p) for p in rot["pool"] if p.strip()]
        if len(pool) < 2:
            messagebox.showinfo("Rotation d'IP", "Mode « pool » : ajoutez au moins 2 proxys/routes dans "
                                "Options → Paramètres → Réseau.")
            return
        targets = tabs or ([t for t in self.tabs if t["proxy"]] if all_tabs else
                           ([self.current] if self.current else []))
        targets = [t for t in targets if t.get("launch")]
        if not targets:
            messagebox.showinfo("Rotation d'IP", "Seuls les navigateurs lancés par SoNiC_0TAB0 peuvent changer "
                                "d'IP (le navigateur est relancé avec le proxy suivant, même profil).")
            return
        for t in targets:
            self.enqueue(self.rotate_job(t, pool))

    def rotate_job(self, tab, pool):
        def job(done):
            if tab not in self.tabs:
                return done()
            cur = tab["proxy"]
            nxt = pool[(pool.index(cur) + 1) % len(pool)] if cur in pool else pool[0]
            L, idx, hwnd = dict(tab["launch"]), self.tabs.index(tab), tab["hwnd"]
            meta = {"label": tab["label"], "gid": tab["gid"], "order": tab.get("order"),
                    "group": dict(self.groups.get(tab["gid"], {})) or None, "current": tab is self.current}
            self.close_window(tab)
            deadline = time.time() + 12

            def wait():
                if w.is_window(hwnd):
                    if time.time() < deadline:
                        self.root.after(300, wait)
                        return
                    self.status.set("Rotation annulée : le navigateur n'a pas fermé (fenêtre de confirmation ?).")
                    return done()
                if tab in self.tabs:
                    self.forget(tab)
                self.launch(L["path"], L["profile"], "", nxt, True,
                            lambda t: (t and self.apply_meta(t, meta, idx), self.status.set(
                                f"Nouvelle sortie : {nxt}"), done()))
            self.root.after(300, wait)
        return job

    def _tor_worker(self):
        r = self.cfg["rotation"]
        try:
            core.tor_newnym(r["tor_host"], r["tor_port"], r["tor_password"], r["tor_cookie"])
            self.q.put(("msg", "Tor : nouveaux circuits demandés (la nouvelle IP s'applique aux nouvelles connexions)."))
        except Exception as e:
            self.q.put(("msg", f"Tor : échec ({e})"))

    def leak_check(self, silent):
        proxies = sorted({t["proxy"] for t in self.tabs if t["proxy"]})
        if not proxies:
            if not silent:
                messagebox.showinfo("Fuites d'IP", "Aucun onglet n'utilise de proxy / route.")
            return
        self.status.set("Test de fuite en cours…")
        threading.Thread(target=lambda: self.q.put(("leak", core.check_proxies(proxies), silent)),
                         daemon=True).start()

    def show_leaks(self, res, silent):
        bad = {r["proxy"] for r in res if r["leak"]}
        for t in self.tabs:
            t["leak"] = t["proxy"] in bad
        self.redraw()
        if silent and not bad:
            self.status.set("Contrôle de fuite : aucune fuite détectée.")
            return
        self.status.set("⚠ Fuite détectée !" if bad else "Contrôle de fuite : OK")
        win = tk.Toplevel(self.root)
        win.title("Test de fuite d'IP")
        tv = ttk.Treeview(win, columns=("p", "ip", "d", "s"), show="headings", height=min(10, len(res) + 1))
        for col, txt, wd in (("p", "Proxy / route", 220), ("ip", "IP vue via le proxy", 130),
                             ("d", "IP directe", 130), ("s", "Verdict", 330)):
            tv.heading(col, text=txt)
            tv.column(col, width=wd)
        for r in res:
            tv.insert("", "end", values=(r["proxy"], r["ip"] or "—", r["direct"] or "—", r["status"]))
        tv.pack(padx=8, pady=8)
        tk.Label(win, justify="left", fg="#555", wraplength=800,
                 text="Ce test vérifie que chaque proxy/route change bien l'IP publique. Les fuites WebRTC et DNS "
                      "ne peuvent pas être vues d'ici : SoNiC_0TAB0 bloque WebRTC dans les profils à proxy (Options).").pack(
            padx=8, pady=(0, 8))

    # ------------------------------------------------------- connexions (assistant)
    def dlg_connections(self):
        win = tk.Toplevel(self.root)
        win.title("Mes connexions Internet")
        win.transient(self.root)
        win.geometry("860x560")
        tk.Label(win, justify="left", wraplength=830, anchor="w", padx=10, pady=8,
                 text="Une « route » est une porte de sortie vers Internet, attribuée à un navigateur (ou à un conteneur "
                      "Firefox). Chaque route sort par UNE carte réseau : votre box (Ethernet/Wi-Fi), le partage de "
                      "connexion 4G de votre téléphone (USB, Bluetooth ou 2e carte Wi-Fi), un VPN…\n"
                      "①  Cliquez « Détecter » : SoNiC_0TAB0 teste chaque carte et affiche l'IP publique obtenue.\n"
                      "②  Deux cartes avec la MÊME IP publique = même accès Internet : elles ne donneront jamais des IP "
                      "différentes (par exemple Wi-Fi et Ethernet de la même box).\n"
                      "③  « Créer les routes » : une route par IP différente. Utilisez-la dans « Nouveau navigateur » "
                      "ou dans l'extension Firefox.\n"
                      "Astuce : une carte Wi-Fi ne rejoint qu'UN réseau. Pour une 2e connexion : câble USB de DONNÉES + Modem USB, "
                      "partage Bluetooth, ou box en Ethernet + Wi-Fi sur le hotspot. « ↪ Route de secours » : si une "
                      "route tombe, une autre prend le relais (notification) et la principale revient seule.").pack(fill="x")
        tv = ttk.Treeview(win, columns=("n", "i", "p", "r"), show="headings", height=9)
        for col, txt, wd in (("n", "Carte réseau", 230), ("i", "IP locale", 120), ("p", "IP publique (vue d'Internet)", 230),
                             ("r", "Route", 240)):
            tv.heading(col, text=txt)
            tv.column(col, width=wd)
        tv.pack(padx=10, fill="x")
        summary = tk.StringVar(value="Cliquez « Détecter ».")
        tk.Label(win, textvariable=summary, wraplength=830, justify="left", anchor="w", padx=10, pady=6,
                 font=("Segoe UI", 9, "bold")).pack(fill="x")
        rows = []

        def route_of(index):
            return next((r for r in self.cfg["routes"] if r["iface_index"] == index), None)

        def fill():
            tv.delete(*tv.get_children())
            for r in rows:
                rt = route_of(r["index"])
                pub = r["pub"] or ("—  " + r["err"] if r["err"] else "…")
                tv.insert("", "end", iid=str(r["index"]), values=(
                    r["name"], r["ip"], pub,
                    (f"{rt['name']}  →  socks5://127.0.0.1:{rt['port']}" +
                     (f"   ↪ secours : {self.backup_of(rt)['name']}" if self.backup_of(rt) else "")) if rt else "(aucune)"))

        def scan():
            summary.set("Détection en cours (quelques secondes)…")

            def probe(i):
                r = dict(i, pub=None, err="")
                if not i.get("gw", True):
                    r["err"] = "pas d'accès Internet (aucune passerelle)"
                else:
                    try:
                        r["pub"] = core.get_public_ip_bound(w.make_bind_hook(i["index"], i["ip"]), timeout=6)
                    except Exception:
                        r["err"] = "test impossible"
                return r

            def work():
                try:
                    ifs = w.list_interfaces()
                    with ThreadPoolExecutor(max_workers=6) as ex:
                        res = list(ex.map(probe, ifs))
                except Exception as e:
                    log(traceback.format_exc())
                    self.q.put(("call", lambda: summary.set(f"Détection impossible : {e}")))
                    return
                self.q.put(("call", lambda: done(res)))
            threading.Thread(target=work, daemon=True).start()

        def done(res):
            if not win.winfo_exists():
                return
            rows[:] = res
            fill()
            pubs = {}
            for r in res:
                if r["pub"]:
                    pubs.setdefault(r["pub"], []).append(r["name"])
            if not res:
                summary.set("Aucune carte réseau détectée.")
            elif len(pubs) <= 1:
                summary.set("⚠ Un seul accès Internet distinct détecté. Une carte Wi-Fi ne peut être connectée qu'à UN "
                            "réseau à la fois (box OU téléphone). Pour une 2e IP : branchez le téléphone en USB avec le "
                            "partage de connexion (bouton « 📱 2e connexion »), puis « Détecter ».")
            else:
                summary.set(f"✔ {len(pubs)} accès Internet différents détectés : " + "  |  ".join(
                    f"{ip} ({', '.join(n)})" for ip, n in pubs.items()))

        def new_route(r):
            port = max([x["port"] for x in self.cfg["routes"]] + [10809]) + 1
            rt = {"name": f"{r['name']}" + (f" ({r['pub']})" if r.get("pub") else ""), "port": port,
                  "iface_index": r["index"], "iface_name": r["name"], "ip": r["ip"]}
            self.cfg["routes"].append(rt)
            self.start_route(rt)

        def create_all():
            seen, n = set(), 0
            for r in rows:
                if r["pub"] and r["pub"] not in seen:
                    seen.add(r["pub"])
                    if not route_of(r["index"]):
                        new_route(r)
                        n += 1
            core.save_config(self.cfg)
            fill()
            self.status.set(f"{n} route(s) créée(s).")

        def create_sel():
            if tv.selection():
                r = next((x for x in rows if str(x["index"]) == tv.selection()[0]), None)
                if r and not route_of(r["index"]):
                    new_route(r)
                    core.save_config(self.cfg)
                    fill()

        def remove():
            if tv.selection():
                rt = route_of(int(tv.selection()[0]))
                if rt:
                    self.cfg["routes"].remove(rt)
                    self.stop_route(rt["port"])
                    for x in self.cfg["routes"]:
                        if x.get("backup_port") == rt["port"]:
                            x.pop("backup_port", None)
                            self.stop_route(x["port"])
                            self.start_route(x)
                    core.save_config(self.cfg)
                    fill()

        def test():
            if not tv.selection():
                return
            rt = route_of(int(tv.selection()[0]))
            if not rt:
                summary.set("Créez d'abord une route pour cette carte.")
                return
            px = f"socks5://127.0.0.1:{rt['port']}"
            summary.set("Test de la route…")

            def work():
                try:
                    ip = core.get_public_ip(px)
                    self.q.put(("call", lambda: summary.set(f"Route « {rt['name']} » : IP publique {ip}")))
                except Exception as e:
                    self.q.put(("call", lambda: summary.set(f"Route « {rt['name']} » : échec ({e})")))
            threading.Thread(target=work, daemon=True).start()
        def set_backup():
            if not tv.selection():
                summary.set("Sélectionnez d'abord la carte dont vous voulez définir le secours.")
                return
            rt = route_of(int(tv.selection()[0]))
            if not rt:
                summary.set("Créez d'abord une route pour cette carte.")
                return
            others = [x for x in self.cfg["routes"] if x["port"] != rt["port"]]
            if not others:
                summary.set("Il faut au moins DEUX routes (deux cartes réseau) pour définir un secours.")
                return
            d = tk.Toplevel(win)
            d.title("Route de secours")
            d.transient(win)
            tk.Label(d, justify="left", wraplength=420, padx=12, pady=10,
                     text=f"Si « {rt['name']} » ne répond plus, les connexions passeront par la route choisie "
                          "ci-dessous (une notification s'affiche), puis reviendront automatiquement sur la "
                          "principale dès qu'elle fonctionne de nouveau.\n\n"
                          "⚠ L'adresse IP vue par le site change pendant la bascule. Ne l'utilisez que là où ce n'est "
                          "pas un problème (et jamais pour faire apparaître deux comptes sous la même IP).\n"
                          "Il n'y a jamais de repli sur la connexion normale du PC.").pack()
            labels = ["(aucun secours)"] + [f"{x['name']}  —  port {x['port']}" for x in others]
            cur = self.backup_of(rt)
            var = tk.StringVar(value=labels[1 + others.index(cur)] if cur else labels[0])
            cb = ttk.Combobox(d, values=labels, textvariable=var, state="readonly", width=52)
            cb.pack(padx=12, pady=4)

            def ok():
                i = labels.index(var.get())
                if i == 0:
                    rt.pop("backup_port", None)
                else:
                    rt["backup_port"] = others[i - 1]["port"]
                core.save_config(self.cfg)
                self.stop_route(rt["port"])
                self.start_route(rt)
                d.destroy()
                fill()
            ttk.Button(d, text="Enregistrer", command=ok).pack(pady=10)

        def usb_help():
            messagebox.showinfo(
                "Brancher le téléphone en 4G (2e connexion)",
                "Le Wi-Fi du PC reste connecté à votre box. Le téléphone ajoute UNE 2e carte réseau par câble :\n\n"
                "1. Branchez le téléphone au PC avec un câble USB (câble de données).\n"
                "2. Sur le téléphone (Samsung Galaxy) : Paramètres → Connexions → Point d'accès mobile et modem "
                "→ activez « Modem USB ».\n   (Désactivez le Wi-Fi du téléphone pour qu'il utilise bien la 4G/5G.)\n"
                "3. Windows crée automatiquement une carte « Ethernet … » (Remote NDIS) : patientez 10 secondes.\n"
                "4. Ici : « ① Détecter » → vous devez voir 2 IP publiques différentes → « ③ Créer les routes ».\n\n"
                "Pourquoi pas le point d'accès Wi-Fi du téléphone ? Votre PC n'a qu'une carte Wi-Fi : elle ne peut être "
                "connectée qu'à SFR_D894 OU au téléphone, pas aux deux. (Alternatives : une clé Wi-Fi USB à ~10 €, "
                "ou le partage par Bluetooth, plus lent.)")
        row = tk.Frame(win)
        row.pack(pady=8)
        for txt, cmd in (("① Détecter", scan), ("③ Créer les routes", create_all), ("Route pour la sélection", create_sel),
                         ("Tester la route", test), ("↪ Route de secours", set_backup), ("Supprimer la route", remove),
                         ("📱 2e connexion", usb_help)):
            ttk.Button(row, text=txt, command=cmd).pack(side="left", padx=4)
        rows[:] = [dict(index=r["iface_index"], name=r["iface_name"], ip=r.get("ip", ""), pub=None, err="", gw=True)
                   for r in self.cfg["routes"]]
        fill()
        scan()

    # ------------------------------------------------------------------ paramètres
    def dlg_settings(self):
        c = self.cfg
        win = tk.Toplevel(self.root)
        win.title("Paramètres")
        win.transient(self.root)
        nb = ttk.Notebook(win)
        nb.pack(padx=8, pady=8, fill="both")
        g, k, n = (ttk.Frame(nb, padding=10) for _ in range(3))
        nb.add(g, text="Général")
        nb.add(k, text="Raccourcis")
        nb.add(n, text="Réseau")
        V = {}

        def chk(parent, key, text, val, row):
            V[key] = tk.BooleanVar(value=val)
            ttk.Checkbutton(parent, text=text, variable=V[key]).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        V["auto"] = tk.StringVar(value=w.get_autostart())
        ttk.Label(g, text="Démarrage avec Windows :").grid(row=0, column=0, sticky="w")
        for i, (txt, val) in enumerate((("Non", "none"), ("Oui", "user"),
                                        ("Oui, en administrateur (sans invite UAC)", "admin"))):
            ttk.Radiobutton(g, text=txt, value=val, variable=V["auto"]).grid(row=1 + i, column=0, sticky="w", padx=14)
        chk(g, "start_foreground", "Au démarrage : ouvrir SoNiC_0TAB0 au premier plan (comme Firefox)", c["start_foreground"], 4)
        chk(g, "start_maximized", "… et en plein écran", c["start_maximized"], 5)
        chk(g, "autorestore", "Restaurer automatiquement la dernière session au démarrage", c["autorestore"], 6)
        chk(g, "autosave_session", "Sauvegarder la session à la fermeture", c["autosave_session"], 7)
        chk(g, "run_as_admin", "Toujours exécuter en administrateur (invite UAC en lancement manuel)", c["run_as_admin"], 8)
        HK = {}
        for i, a in enumerate(core.ACTION_LABELS):
            ttk.Label(k, text=core.ACTION_LABELS[a]).grid(row=i, column=0, sticky="w", pady=2)
            HK[a] = tk.StringVar(value=c["hotkeys"].get(a, ""))
            ttk.Entry(k, textvariable=HK[a], width=22).grid(row=i, column=1, padx=8)
        gs = tk.StringVar(value=c["goto_scoped"])
        gg = tk.StringVar(value=c["goto_global"])
        ttk.Label(k, text="Onglets 1 à 9 — préfixe, fenêtre active").grid(row=len(HK), column=0, sticky="w", pady=2)
        ttk.Entry(k, textvariable=gs, width=22).grid(row=len(HK), column=1, padx=8)
        ttk.Label(k, text="Onglets 1 à 9 — préfixe, partout").grid(row=len(HK) + 1, column=0, sticky="w", pady=2)
        ttk.Entry(k, textvariable=gg, width=22).grid(row=len(HK) + 1, column=1, padx=8)
        chk(k, "scoped_tabs", "Ctrl+Tab / Ctrl+Maj+Tab (fenêtre active)", c["scoped_tabs"], len(HK) + 2)
        ttk.Label(k, foreground="#666", justify="left",
                  text="Préfixe seul : « ctrl » donne Ctrl+1…9. « Fenêtre active » = ne gêne pas les autres applications.\n"
                       "Format : ctrl+alt+g · ctrl+shift+f5 · ctrl+alt+right").grid(
            row=len(HK) + 3, column=0, columnspan=2, sticky="w", pady=6)
        f, r = c["features"], c["rotation"]
        chk(n, "f_routes", "Activer les routes réseau (sortie par carte)", f["routes"], 0)
        chk(n, "f_rotation", "Activer la rotation d'IP", f["rotation"], 1)
        V["mode"] = tk.StringVar(value=r["mode"])
        ttk.Radiobutton(n, text="Pool : relancer le navigateur avec le proxy/route suivant", value="pool",
                        variable=V["mode"]).grid(row=2, column=0, columnspan=3, sticky="w", padx=14)
        ttk.Radiobutton(n, text="Tor : nouveaux circuits (NEWNYM) sans relancer", value="tor",
                        variable=V["mode"]).grid(row=3, column=0, columnspan=3, sticky="w", padx=14)
        ttk.Label(n, text="Pool (un proxy par ligne) :").grid(row=4, column=0, sticky="nw", padx=14)
        pool = tk.Text(n, width=38, height=4)
        pool.grid(row=4, column=1, columnspan=2, pady=2)
        pool.insert("1.0", "\n".join(r["pool"]))
        T = {}
        for i, (key, txt) in enumerate((("tor_host", "Tor : hôte"), ("tor_port", "Tor : port contrôle"),
                                        ("tor_password", "Tor : mot de passe"), ("tor_cookie", "Tor : fichier cookie"))):
            ttk.Label(n, text=txt).grid(row=5 + i, column=0, sticky="w", padx=14)
            T[key] = tk.StringVar(value=str(r[key]))
            ttk.Entry(n, textvariable=T[key], width=40, show="*" if key == "tor_password" else "").grid(
                row=5 + i, column=1, columnspan=2, pady=1)
        ttk.Label(n, text="Rotation automatique (min, Tor, 0 = non)").grid(row=9, column=0, sticky="w", padx=14)
        V["auto_min"] = tk.StringVar(value=str(r["auto_min"]))
        ttk.Spinbox(n, from_=0, to=1440, textvariable=V["auto_min"], width=6).grid(row=9, column=1, sticky="w")
        chk(n, "f_leak", "Activer la détection de fuite d'IP", f["leak"], 10)
        ttk.Label(n, text="Contrôle périodique (min, 0 = non)").grid(row=11, column=0, sticky="w", padx=14)
        V["leak_min"] = tk.StringVar(value=str(c["leak_min"]))
        ttk.Spinbox(n, from_=0, to=1440, textvariable=V["leak_min"], width=6).grid(row=11, column=1, sticky="w")
        chk(n, "block_webrtc", "Bloquer WebRTC dans les profils à proxy (anti-fuite d'IP locale)", c["block_webrtc"], 12)

        def save():
            hot = {a: HK[a].get().strip().lower() for a in HK if HK[a].get().strip()}
            gpre = [gs.get().strip().lower(), gg.get().strip().lower()]
            for a, spec in list(hot.items()) + [("onglets 1-9", p + "+1") for p in gpre if p]:
                if not core.parse_hotkey(spec):
                    messagebox.showerror("Raccourcis", f"Raccourci invalide pour « {a} » : {spec}", parent=win)
                    return
            for key in ("start_foreground", "start_maximized", "autorestore", "autosave_session",
                        "run_as_admin", "block_webrtc"):
                c[key] = V[key].get()
            c["hotkeys"], c["goto_scoped"], c["goto_global"] = hot, gpre[0], gpre[1]
            c["scoped_tabs"] = V["scoped_tabs"].get()
            c["features"] = {"routes": V["f_routes"].get(), "rotation": V["f_rotation"].get(), "leak": V["f_leak"].get()}
            try:
                c["rotation"].update(mode=V["mode"].get(), pool=[p.strip() for p in pool.get("1.0", "end").splitlines() if p.strip()],
                                     auto_min=int(V["auto_min"].get() or 0), tor_host=T["tor_host"].get(),
                                     tor_port=int(T["tor_port"].get() or 9051), tor_password=T["tor_password"].get(),
                                     tor_cookie=T["tor_cookie"].get())
                c["leak_min"] = int(V["leak_min"].get() or 0)
            except ValueError:
                messagebox.showerror("Paramètres", "Valeur numérique invalide.", parent=win)
                return
            core.save_config(c)
            mode = V["auto"].get()
            if mode != w.get_autostart():
                if not w.set_autostart(mode, w.launch_parts() + ["--startup"]):
                    messagebox.showwarning("Démarrage", "Le démarrage automatique n'a pas pu être modifié "
                                           "(invite UAC refusée ?).", parent=win)
            self.menu = self.build_menu()
            self.start_hotkeys()
            win.destroy()
            self.status.set("Paramètres enregistrés.")
        ttk.Button(win, text="Enregistrer", command=save).pack(pady=(0, 10))

    # ------------------------------------------------------------ actions / boucle
    def handle_action(self, a):
        if a == "capture":
            h = w.foreground_window()
            if h and w.pid_of(h) != os.getpid():
                if self.embed(h):
                    self.bring_front(False)
        elif a == "next_tab":
            self.cycle(1)
        elif a == "prev_tab":
            self.cycle(-1)
        elif a.startswith("goto_"):
            i = int(a[5:]) - 1
            if i < len(self.tabs):
                self.switch_to(self.tabs[i])
        elif a == "reload":
            self.reload_tab(self.current)
        elif a == "detach" and self.current:
            self.release(self.current)
        elif a == "toggle":
            if self.root.state() in ("withdrawn", "iconic"):
                self.bring_front(False)
            else:
                self.root.withdraw()
        elif a == "new_ip":
            self.rotate_ip(False)
        elif a == "leak_check":
            self.leak_check(False)
        elif a == "save_session":
            self.save_now()
        elif a == "new_browser":
            self.bring_front(False)
            self.dlg_launch()

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "action":
                    self.handle_action(msg[1])
                elif msg[0] == "msg":
                    self.status.set(msg[1])
                elif msg[0] == "leak":
                    self.show_leaks(msg[1], msg[2])
                elif msg[0] == "call":
                    try:
                        msg[1]()
                    except Exception:
                        log(traceback.format_exc())
                elif msg[0] == "hk_fail":
                    self.status.set("Raccourcis non enregistrés (déjà pris ?) : " + ", ".join(msg[1]))
        except queue.Empty:
            pass
        if self.hotkeys and getattr(self.hotkeys, "tid", None):     # Ctrl+1…9 seulement quand SoNiC_0TAB0 est actif
            active = w.is_foreground(self.top_hwnd)
            if active != self.scoped_on:
                self.scoped_on = active
                self.hotkeys.set_scoped(active)
        self.tick += 1
        if self.tick % 4 == 0:
            changed = False
            for t in list(self.tabs):
                if not w.is_window(t["hwnd"]) or w.real_parent(t["hwnd"]) != self.host_hwnd:
                    self.forget(t)
                    continue
                nt = w.title_of(t["hwnd"])
                if nt and nt != t["title"]:
                    t["title"], changed = nt, True
                    if t is self.current:
                        self.root.title(f"SoNiC_0TAB0 — {t['label'] or nt}")
            if changed:
                self.redraw()
            try:
                self.auto_reload_tick()
            except Exception:
                log(traceback.format_exc())
            now = time.time()
            f, r = self.cfg["features"], self.cfg["rotation"]
            if f["leak"] and self.cfg["leak_min"] and now - self.last_leak > self.cfg["leak_min"] * 60:
                self.last_leak = now
                self.leak_check(True)
            if f["rotation"] and r["mode"] == "tor" and r["auto_min"] and now - self.last_rot > r["auto_min"] * 60:
                self.last_rot = now
                threading.Thread(target=self._tor_worker, daemon=True).start()
            if self.tabs and self.cfg["autosave_session"] and now - self.last_save > 120:
                self.last_save = now
                core.save_session_file("_derniere", self.session_data())
        self.root.after(150, self.poll)

    def on_close(self, relaunch=False):
        try:
            if self.cfg["autosave_session"] and self.tabs:
                core.save_session_file("_derniere", self.session_data())
        except Exception:
            log(traceback.format_exc())
        for t in list(self.tabs):          # rendre les fenêtres AVANT de détruire le cadre
            try:
                self.release(t, quiet=True)
            except Exception:
                log(traceback.format_exc())
        try:
            w.liberate_children(self.host_hwnd)   # et celles que SoNiC_0TAB0 ne connaîtrait plus
        except Exception:
            pass
        for fn in (lambda: self.hotkeys and self.hotkeys.stop(), lambda: [self.stop_route(p) for p in list(self.routes)],
                   self.control.stop):
            try:
                fn()
            except Exception:
                pass
        self.root.destroy()
        if relaunch:
            w.relaunch_as_admin(["--restore"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--startup", action="store_true", help="lancé au démarrage de Windows")
    ap.add_argument("--minimized", action="store_true")
    ap.add_argument("--restore", action="store_true", help="restaurer la dernière session")
    ap.add_argument("--admin", action="store_true", help="exiger les droits administrateur")
    args, _ = ap.parse_known_args()
    try:
        cfg = core.load_config()
        if (args.admin or cfg["run_as_admin"]) and not w.is_admin():
            if w.relaunch_as_admin():
                return
        root = tk.Tk()
        SoNiC_0TAB0(root, args)
        root.mainloop()
    except Exception:
        log(traceback.format_exc())
        w.message_box("SoNiC_0TAB0", "Erreur au démarrage :\n\n" + traceback.format_exc()[-900:] +
                      f"\nJournal : {os.path.join(core.DATA, 'sonic_0tab0.log')}", error=True)


if __name__ == "__main__":
    main()
