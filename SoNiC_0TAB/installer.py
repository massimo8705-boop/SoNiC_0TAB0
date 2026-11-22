# -*- coding: utf-8 -*-
"""
Installateur / désinstallateur SoNiC_0TAB0 (sans dépendance externe).

  python installer.py              -> assistant graphique
  python installer.py --silent [--autostart none|user|admin] [--no-desktop] [--no-startmenu]
  python installer.py --uninstall  -> désinstallation

Options proposées : raccourcis Bureau / menu Démarrer, démarrage avec Windows
(utilisateur, ou administrateur via tâche planifiée sans invite UAC au démarrage),
raccourcis « exécuter en tant qu'administrateur », lancement à la fin.
Compilé avec PyInstaller (voir build_exe.bat), le programme installé est un .exe autonome.
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

LOG = os.path.join(tempfile.gettempdir(), "sonic_0tab0_install.log")


def fatal(msg):
    """Affiche l'erreur dans une boîte Windows (même sans Tk) et l'écrit dans le journal."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(0, msg + f"\n\nJournal : {LOG}", "SoNiC_0TAB0 — Installation", 0x10)
    except Exception:
        print(msg)
    sys.exit(1)


if sys.platform != "win32":
    sys.exit("Installateur Windows uniquement.")
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_missing = [f for f in ("td_core.py", "td_win.py", "SoNiC_0TAB0.py") if not os.path.isfile(os.path.join(HERE, f))
            and not os.path.isdir(os.path.join(HERE, "payload"))]
if _missing:
    fatal("Fichiers manquants : " + ", ".join(_missing) + ".\n\nFaites un clic droit sur SoNiC_0TAB0.zip → "
          "« Extraire tout… », puis lancez INSTALLER.cmd depuis le dossier extrait (pas depuis le zip).")
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception as e:  # Tk absent : Python installé sans tcl/tk
    fatal(f"Tkinter est introuvable ({e}).\nRéinstallez Python en cochant « tcl/tk and IDLE », "
          "ou relancez INSTALLER.cmd qui s'en charge.")
try:
    import td_win as w
except Exception:
    fatal("Chargement impossible :\n" + traceback.format_exc())

APP = "SoNiC_0TAB0"
UNINST_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SoNiC_0TAB0"
VERSION = "1.6"
SRC_FILES = ["SoNiC_0TAB0.py", "td_core.py", "td_win.py", "installer.py"]


def default_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP)


def menu_dir():
    return os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")


def desktop_dir():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                       capture_output=True, text=True, creationflags=w.CREATE_NO_WINDOW)
    return r.stdout.strip() or os.path.join(os.path.expanduser("~"), "Desktop")


def has_exe_payload():
    return os.path.isfile(os.path.join(HERE, "payload", "SoNiC_0TAB0.exe"))


def installed_cmd(d):
    if has_exe_payload() or os.path.isfile(os.path.join(d, "SoNiC_0TAB0.exe")):
        return [os.path.join(d, "SoNiC_0TAB0.exe")]
    return [w.pythonw(), os.path.join(d, "SoNiC_0TAB0.py")]


def uninstall_cmd(d):
    if has_exe_payload():
        return [os.path.join(d, "Uninstall.exe"), "--uninstall"]
    return [w.pythonw(), os.path.join(d, "installer.py"), "--uninstall"]


def do_install(o, log=print):
    import winreg
    d = o["dir"]
    os.makedirs(d, exist_ok=True)
    log("Nettoyage de l'ancienne version (TabDock)…")
    remove_legacy(log)
    log("Copie des fichiers…")
    if has_exe_payload():
        shutil.copy2(os.path.join(HERE, "payload", "SoNiC_0TAB0.exe"), os.path.join(d, "SoNiC_0TAB0.exe"))
        shutil.copy2(sys.executable, os.path.join(d, "Uninstall.exe"))
    else:
        for f in SRC_FILES:
            shutil.copy2(os.path.join(HERE, f), os.path.join(d, f))
        shutil.copytree(os.path.join(HERE, "assets"), os.path.join(d, "assets"), dirs_exist_ok=True)
    if os.path.isdir(os.path.join(HERE, "firefox_extension")):
        shutil.copytree(os.path.join(HERE, "firefox_extension"), os.path.join(d, "firefox_extension"),
                        dirs_exist_ok=True)
    cmd = installed_cmd(d)
    exe, args = cmd[0], subprocess.list2cmdline(cmd[1:])
    icon = os.path.join(d, "assets", "tabdock.ico") if not has_exe_payload() else exe
    runas = o["shortcut_admin"]
    if o["startmenu"]:
        log("Raccourci du menu Démarrer…")
        w.make_shortcut(os.path.join(menu_dir(), APP + ".lnk"), exe, args, d, icon, runas)
    if o["desktop"]:
        log("Raccourci du Bureau…")
        w.make_shortcut(os.path.join(desktop_dir(), APP + ".lnk"), exe, args, d, icon, runas)
    log("Démarrage automatique…")
    w.set_autostart(o["autostart"], cmd + ["--startup"])
    log("Enregistrement de la désinstallation…")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINST_KEY) as k:
        for name, val in (("DisplayName", APP), ("DisplayVersion", VERSION), ("InstallLocation", d),
                          ("DisplayIcon", icon), ("Publisher", "SoNiC_0TAB0"),
                          ("UninstallString", subprocess.list2cmdline(uninstall_cmd(d)))):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
    return cmd


def remove_legacy(log=print):
    """Retire l'ancienne installation « TabDock » (raccourcis, entrée de désinstallation, dossier programme).
    Vos données (profils, sessions) sont conservées : SoNiC_0TAB0 les reprend automatiquement."""
    import winreg
    for lnk in (os.path.join(menu_dir(), "TabDock.lnk"), os.path.join(desktop_dir(), "TabDock.lnk")):
        try:
            os.remove(lnk)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TabDock")
    except OSError:
        pass
    old = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "TabDock")
    if os.path.isdir(old) and (os.path.isfile(os.path.join(old, "tabdock.py")) or
                               os.path.isfile(os.path.join(old, "TabDock.exe"))):
        shutil.rmtree(old, ignore_errors=True)


def do_uninstall(remove_data=False, log=print):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINST_KEY) as k:
            d = winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        d = default_dir()
    log("Arrêt du démarrage automatique…")
    w.set_autostart("none", [os.path.join(d, "SoNiC_0TAB0.exe")])
    for lnk in (os.path.join(menu_dir(), APP + ".lnk"), os.path.join(desktop_dir(), APP + ".lnk")):
        try:
            os.remove(lnk)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINST_KEY)
    except OSError:
        pass
    if remove_data:
        shutil.rmtree(os.path.join(os.environ.get("APPDATA", ""), APP), ignore_errors=True)
    # le dossier contient peut-être le programme en cours : suppression différée
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q "{d}"', shell=True,
                     creationflags=w.CREATE_NO_WINDOW)


class Wizard(tk.Tk):
    def __init__(self, uninstall=False):
        super().__init__()
        self.title("Désinstaller SoNiC_0TAB0" if uninstall else "Installer SoNiC_0TAB0")
        self.configure(bg="#0a0e1f")
        self.resizable(False, False)
        for n in ("assets/tabdock.ico",):
            p = os.path.join(HERE, n)
            if os.path.isfile(p):
                try:
                    self.iconbitmap(p)
                except Exception:
                    pass
        left = tk.Label(self, bg="#0a0e1f")
        left.grid(row=0, column=0, padx=10, pady=10)
        gif = os.path.join(HERE, "assets", "banner.gif")
        self.frames, self.fi = [], 0
        k = 0
        while os.path.isfile(gif):
            try:
                self.frames.append(tk.PhotoImage(file=gif, format=f"gif -index {k}"))
            except tk.TclError:
                break
            k += 1
        if self.frames:
            left.configure(image=self.frames[0])
            self._anim(left)
        right = ttk.Frame(self, padding=14)
        right.grid(row=0, column=1, sticky="n")
        self.uninstall = uninstall
        self.v_dir = tk.StringVar(value=default_dir())
        self.v_desktop, self.v_menu = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        self.v_auto = tk.StringVar(value="user")
        self.v_admin_sc = tk.BooleanVar(value=False)
        self.v_run = tk.BooleanVar(value=True)
        self.v_data = tk.BooleanVar(value=False)
        if uninstall:
            ttk.Label(right, text="Désinstaller SoNiC_0TAB0 ?", font=("Segoe UI", 12, "bold")).pack(anchor="w")
            ttk.Checkbutton(right, text="Supprimer aussi mes données (profils, sessions, réglages)",
                            variable=self.v_data).pack(anchor="w", pady=10)
            ttk.Button(right, text="Désinstaller", command=self.go).pack(anchor="e", pady=6)
        else:
            ttk.Label(right, text="Installation de SoNiC_0TAB0", font=("Segoe UI", 12, "bold")).pack(anchor="w")
            ttk.Label(right, text="Dossier d'installation :").pack(anchor="w", pady=(10, 0))
            ttk.Entry(right, textvariable=self.v_dir, width=52).pack(anchor="w")
            ttk.Checkbutton(right, text="Raccourci sur le Bureau", variable=self.v_desktop).pack(anchor="w", pady=(10, 0))
            ttk.Checkbutton(right, text="Raccourci dans le menu Démarrer", variable=self.v_menu).pack(anchor="w")
            ttk.Checkbutton(right, text="Raccourcis toujours en mode administrateur",
                            variable=self.v_admin_sc).pack(anchor="w")
            ttk.Label(right, text="Au démarrage de Windows :").pack(anchor="w", pady=(10, 0))
            for txt, val in (("Ne pas lancer", "none"),
                             ("Ouvrir SoNiC_0TAB0 au premier plan (restaure la dernière session)", "user"),
                             ("… en mode administrateur (sans invite UAC, via tâche planifiée)", "admin")):
                ttk.Radiobutton(right, text=txt, value=val, variable=self.v_auto).pack(anchor="w", padx=14)
            ttk.Label(right, foreground="#777", wraplength=430, justify="left",
                      text="Le mode administrateur permet d'intégrer aussi des fenêtres lancées en administrateur. "
                           "Une invite UAC unique apparaît pendant l'installation.").pack(anchor="w", pady=(6, 0))
            ttk.Checkbutton(right, text="Lancer SoNiC_0TAB0 à la fin", variable=self.v_run).pack(anchor="w", pady=(10, 0))
            ttk.Button(right, text="Installer", command=self.go).pack(anchor="e", pady=8)
        self.log = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.log, foreground="#777").pack(anchor="w")

    def _anim(self, label):
        self.fi = (self.fi + 1) % len(self.frames)
        label.configure(image=self.frames[self.fi])
        self.after(180, self._anim, label)

    def say(self, t):
        self.log.set(t)
        self.update()

    def go(self):
        try:
            if self.uninstall:
                do_uninstall(self.v_data.get(), self.say)
                messagebox.showinfo("SoNiC_0TAB0", "SoNiC_0TAB0 a été désinstallé.")
            else:
                cmd = do_install({"dir": self.v_dir.get(), "desktop": self.v_desktop.get(),
                                  "startmenu": self.v_menu.get(), "autostart": self.v_auto.get(),
                                  "shortcut_admin": self.v_admin_sc.get()}, self.say)
                if self.v_run.get():
                    subprocess.Popen(cmd, cwd=os.path.dirname(cmd[-1]))
                messagebox.showinfo("SoNiC_0TAB0", "Installation terminée.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("SoNiC_0TAB0", f"Erreur : {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--autostart", default="user", choices=["none", "user", "admin"])
    ap.add_argument("--no-desktop", action="store_true")
    ap.add_argument("--no-startmenu", action="store_true")
    ap.add_argument("--dir", default=default_dir())
    a = ap.parse_args()
    try:
        run(a)
    except SystemExit:
        raise
    except Exception:
        fatal("Erreur pendant l'installation :\n" + traceback.format_exc())


def run(a):
    if a.silent:
        if a.uninstall:
            do_uninstall()
        else:
            do_install({"dir": a.dir, "desktop": not a.no_desktop, "startmenu": not a.no_startmenu,
                        "autostart": a.autostart, "shortcut_admin": a.autostart == "admin"})
        return
    Wizard(a.uninstall).mainloop()


if __name__ == "__main__":
    main()
