# -*- coding: utf-8 -*-
"""SoNiC_0TAB0 - couche Windows : fenêtres, démarrage automatique, droits admin,
raccourcis (.lnk), cartes réseau, raccourcis clavier globaux."""
import ctypes
import getpass
import os
import socket
import subprocess
import sys
import tempfile
import threading
from ctypes import wintypes
from xml.sax.saxutils import escape

import td_core as core

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
s32 = ctypes.WinDLL("shell32", use_last_error=True)
try:
    dwm = ctypes.WinDLL("dwmapi")
except Exception:
    dwm = None

HWND, DWORD, BOOL, UINT = wintypes.HWND, wintypes.DWORD, wintypes.BOOL, wintypes.UINT
CREATE_NO_WINDOW = 0x08000000
GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CHILD, WS_POPUP = 0x40000000, 0x80000000
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
WS_SYSMENU, WS_MINBOX, WS_MAXBOX = 0x00080000, 0x00020000, 0x00010000
WS_EX_TOOLWINDOW = 0x80
SW_HIDE, SW_SHOW, SW_RESTORE = 0, 5, 9
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x1, 0x2, 0x4
SWP_NOACTIVATE, SWP_FRAMECHANGED, SWP_SHOWWINDOW = 0x10, 0x20, 0x40
WM_CLOSE, WM_HOTKEY, WM_QUIT = 0x10, 0x0312, 0x12

_get = getattr(u32, "GetWindowLongPtrW", None) or u32.GetWindowLongW
_set = getattr(u32, "SetWindowLongPtrW", None) or u32.SetWindowLongW
_get.restype, _get.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int]
_set.restype, _set.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int, ctypes.c_ssize_t]
get_style, set_style = _get, _set


def _sig(fn, res, *args):
    fn.restype, fn.argtypes = res, list(args)


_sig(u32.SetParent, HWND, HWND, HWND)
_sig(u32.GetParent, HWND, HWND)
_sig(u32.GetAncestor, HWND, HWND, UINT)
_sig(u32.MoveWindow, BOOL, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, BOOL)
_sig(u32.ShowWindow, BOOL, HWND, ctypes.c_int)
_sig(u32.SetWindowPos, BOOL, HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, UINT)
_sig(u32.IsWindow, BOOL, HWND)
_sig(u32.IsWindowVisible, BOOL, HWND)
_sig(u32.IsIconic, BOOL, HWND)
_sig(u32.BringWindowToTop, BOOL, HWND)
_sig(u32.SetForegroundWindow, BOOL, HWND)
_sig(u32.GetWindowTextW, ctypes.c_int, HWND, wintypes.LPWSTR, ctypes.c_int)
_sig(u32.GetWindowTextLengthW, ctypes.c_int, HWND)
_sig(u32.GetWindowThreadProcessId, DWORD, HWND, ctypes.POINTER(DWORD))
_sig(u32.GetWindow, HWND, HWND, UINT)
_sig(u32.GetWindowRect, BOOL, HWND, ctypes.POINTER(wintypes.RECT))
_sig(u32.PostMessageW, BOOL, HWND, UINT, wintypes.WPARAM, wintypes.LPARAM)
_sig(u32.GetForegroundWindow, HWND)
_sig(u32.AttachThreadInput, BOOL, DWORD, DWORD, BOOL)
_sig(u32.SetFocus, HWND, HWND)
_sig(u32.RegisterHotKey, BOOL, HWND, ctypes.c_int, UINT, UINT)
_sig(u32.UnregisterHotKey, BOOL, HWND, ctypes.c_int)
_sig(u32.GetMessageW, ctypes.c_int, ctypes.POINTER(wintypes.MSG), HWND, UINT, UINT)
_sig(u32.PostThreadMessageW, BOOL, DWORD, UINT, wintypes.WPARAM, wintypes.LPARAM)
_sig(k32.GetCurrentThreadId, DWORD)
_sig(k32.OpenProcess, wintypes.HANDLE, DWORD, BOOL, DWORD)
_sig(k32.CloseHandle, BOOL, wintypes.HANDLE)
_sig(k32.QueryFullProcessImageNameW, BOOL, wintypes.HANDLE, DWORD, wintypes.LPWSTR,
     ctypes.POINTER(DWORD))
_sig(u32.IsZoomed, BOOL, HWND)
WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, wintypes.LPARAM)
_sig(u32.EnumChildWindows, BOOL, HWND, WNDENUMPROC, wintypes.LPARAM)
adv = ctypes.WinDLL("advapi32", use_last_error=True)
_sig(adv.OpenProcessToken, BOOL, wintypes.HANDLE, DWORD, ctypes.POINTER(wintypes.HANDLE))
_sig(adv.GetTokenInformation, BOOL, wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, DWORD, ctypes.POINTER(DWORD))
GA_PARENT, GA_ROOT = 1, 2
SW_SHOWNA = 8
WS_CLIPCHILDREN, WS_CLIPSIBLINGS = 0x02000000, 0x04000000
WS_OVERLAPPEDWINDOW = 0x00CF0000


def set_app_id(app_id="SoNiC_0TAB0.App"):
    try:
        s32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


# ----- fenêtres -------------------------------------------------------------
def title_of(h):
    n = u32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, buf, n + 1)
    return buf.value


def pid_of(h):
    pid = DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value


def exe_path_of(pid):
    hp = k32.OpenProcess(0x1000, False, pid)
    if not hp:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    n = DWORD(1024)
    ok = k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n))
    k32.CloseHandle(hp)
    return buf.value if ok else ""


def exe_of(pid):
    p = exe_path_of(pid)
    return os.path.basename(p).lower() if p else "?"


def is_cloaked(h):
    if not dwm:
        return False
    v = ctypes.c_int(0)
    try:
        dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(v), 4)
    except Exception:
        return False
    return v.value != 0


def list_windows():
    """Fenêtres de premier niveau 'normales' : (hwnd, titre, exe, pid)."""
    out = []

    @WNDENUMPROC
    def cb(h, _):
        try:
            if not u32.IsWindowVisible(h) or u32.GetWindow(h, 4):
                return True
            if _get(h, GWL_EXSTYLE) & WS_EX_TOOLWINDOW or is_cloaked(h):
                return True
            t = title_of(h)
            if not t or t == "Program Manager":
                return True
            pid = pid_of(h)
            if pid == os.getpid():
                return True
            out.append((h, t, exe_of(pid), pid))
        except Exception:
            pass
        return True

    u32.EnumWindows(cb, 0)
    return out


def focus_window(h):
    try:
        me = k32.GetCurrentThreadId()
        other = u32.GetWindowThreadProcessId(h, None)
        u32.AttachThreadInput(me, other, True)
        u32.SetFocus(h)
        u32.AttachThreadInput(me, other, False)
    except Exception:
        pass


def modifiers_down():
    """True si Ctrl, Alt, Maj ou Windows sont physiquement enfoncées (évite un F5 transformé en Ctrl+F5, etc.)."""
    try:
        return any(u32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x10, 0x5B, 0x5C))
    except Exception:
        return False


def press_key(vk, ctrl=False):
    """Envoie une touche (avec Ctrl en option) à la fenêtre qui a le focus clavier."""
    KEYUP = 0x0002
    try:
        if ctrl:
            u32.keybd_event(0x11, 0, 0, 0)
        u32.keybd_event(vk, 0, 0, 0)
        u32.keybd_event(vk, 0, KEYUP, 0)
        if ctrl:
            u32.keybd_event(0x11, 0, KEYUP, 0)
        return True
    except Exception:
        return False


def force_foreground(h):
    """Amène une fenêtre au premier plan (contourne le blocage du focus de Windows)."""
    try:
        top = u32.GetAncestor(h, 2) or h
        fg = u32.GetForegroundWindow()
        me = k32.GetCurrentThreadId()
        ft = u32.GetWindowThreadProcessId(fg, None) if fg else 0
        if ft:
            u32.AttachThreadInput(me, ft, True)
        u32.ShowWindow(top, SW_RESTORE if u32.IsIconic(top) else SW_SHOW)
        u32.BringWindowToTop(top)
        u32.SetForegroundWindow(top)
        if ft:
            u32.AttachThreadInput(me, ft, False)
    except Exception:
        pass



# ----- intégration de fenêtres (cœur de SoNiC_0TAB0) ---------------------------------
# IMPORTANT : GetParent() renvoie 0 pour une fenêtre sans style WS_CHILD ni WS_POPUP, même
# quand SetParent() a réussi. On vérifie donc avec GetAncestor(GA_PARENT), fiable.
def is_window(h):
    return bool(u32.IsWindow(h))


def real_parent(h):
    return u32.GetAncestor(h, GA_PARENT) or 0


def show(h, cmd):
    u32.ShowWindow(h, cmd)


def move(h, x, y, wd, ht):
    u32.MoveWindow(h, x, y, max(1, wd), max(1, ht), True)


def screen_rect(h):
    rc = wintypes.RECT()
    u32.GetWindowRect(h, ctypes.byref(rc))
    return (rc.left, rc.top, rc.right, rc.bottom)


def post_close(h):
    u32.PostMessageW(h, WM_CLOSE, 0, 0)


def foreground_window():
    return u32.GetForegroundWindow() or 0


def top_hwnd(h):
    return u32.GetAncestor(h, GA_ROOT) or h


def is_foreground(top):
    """Vrai si `top` (fenêtre principale) est la fenêtre active — y compris quand le
    clavier est dans un navigateur intégré (ses fenêtres sont des enfants de `top`)."""
    fg = u32.GetForegroundWindow()
    return bool(fg) and (fg == top or u32.GetAncestor(fg, GA_ROOT) == top)


def message_box(title, text, error=False):
    try:
        u32.MessageBoxW(0, text, title, 0x10 if error else 0x40)
    except Exception:
        print(title, text)


def add_clip_styles(hwnd):
    """Évite que Tk repeigne par-dessus les fenêtres intégrées (scintillement)."""
    try:
        h = hwnd
        for _ in range(6):
            if not h:
                break
            _set(h, GWL_STYLE, _get(h, GWL_STYLE) | WS_CLIPCHILDREN | WS_CLIPSIBLINGS)
            if h == u32.GetAncestor(h, GA_ROOT):
                break
            h = real_parent(h)
    except Exception:
        pass


def process_elevated(pid):
    """True / False selon que le processus est élevé (administrateur) ; None si inconnu."""
    hp = k32.OpenProcess(0x1000, False, pid)
    if not hp:
        return None
    tok = wintypes.HANDLE()
    try:
        if not adv.OpenProcessToken(hp, 0x8, ctypes.byref(tok)):
            return None
        elev, ret = DWORD(0), DWORD(0)
        if adv.GetTokenInformation(tok, 20, ctypes.byref(elev), 4, ctypes.byref(ret)):
            return bool(elev.value)
        return None
    finally:
        if tok:
            k32.CloseHandle(tok)
        k32.CloseHandle(hp)


def embed_window(hwnd, host):
    """Place la fenêtre `hwnd` dans `host`. Retourne {'ok', 'err', 'style', 'rect'}.
    Ordre conseillé par Microsoft : style enfant AVANT SetParent."""
    if u32.IsIconic(hwnd) or u32.IsZoomed(hwnd):
        u32.ShowWindow(hwnd, SW_RESTORE)
    rect = screen_rect(hwnd)
    style = _get(hwnd, GWL_STYLE)
    child = ((style & ~(WS_CAPTION | WS_THICKFRAME | WS_POPUP | WS_SYSMENU | WS_MINBOX | WS_MAXBOX))
             | WS_CHILD | WS_CLIPSIBLINGS | WS_CLIPCHILDREN)
    _set(hwnd, GWL_STYLE, child)
    ctypes.set_last_error(0)
    u32.SetParent(hwnd, host)
    err = ctypes.get_last_error()
    if real_parent(hwnd) != host:
        _set(hwnd, GWL_STYLE, style)  # on annule
        return {"ok": False, "err": err, "style": style, "rect": rect}
    u32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
                     | SWP_NOACTIVATE)
    return {"ok": True, "err": 0, "style": style, "rect": rect}


def release_window(hwnd, style, rect):
    """Rend la fenêtre au bureau avec son style et sa position d'origine."""
    if not u32.IsWindow(hwnd):
        return
    u32.SetParent(hwnd, 0)
    _set(hwnd, GWL_STYLE, style)
    l, t, r, b = rect
    if l < -10000 or r - l < 200 or b - t < 150:
        l, t, r, b = 100, 100, 1100, 760
    u32.SetWindowPos(hwnd, 0, l, t, r - l, b - t, SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
    u32.ShowWindow(hwnd, SW_SHOW)


def direct_children(host):
    """Fenêtres étrangères (autres processus) directement enfants de `host`."""
    out = []

    @WNDENUMPROC
    def cb(h, _):
        try:
            if real_parent(h) == host and pid_of(h) != os.getpid():
                out.append(h)
        except Exception:
            pass
        return True
    u32.EnumChildWindows(host, cb, 0)
    return out


def liberate_children(host):
    """Secours : rend au bureau toute fenêtre étrangère encore coincée dans `host`,
    même si SoNiC_0TAB0 ne la connaît plus. Retourne le nombre de fenêtres libérées."""
    n = 0
    for h in direct_children(host):
        try:
            u32.SetParent(h, 0)
            style = (_get(h, GWL_STYLE) & ~(WS_CHILD | WS_CLIPSIBLINGS)) | WS_OVERLAPPEDWINDOW | 0x10000000
            _set(h, GWL_STYLE, style)
            u32.SetWindowPos(h, 0, 100, 100, 1000, 700, SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
            u32.ShowWindow(h, SW_SHOW)
            n += 1
        except Exception:
            pass
    return n


def explain_embed_failure(pid, err):
    exe = exe_of(pid)
    elev = process_elevated(pid)
    if elev and not is_admin():
        return (f"« {exe} » est lancé en administrateur, pas SoNiC_0TAB0.\n\n"
                "→ Menu ☰ → Options → « Relancer en administrateur ».")
    return (f"Windows a refusé d'intégrer « {exe} » (code {err}).\n\n"
            "Certaines applications protégées ne peuvent pas être placées dans une autre fenêtre. "
            "Les navigateurs courants (Firefox, Chrome, Edge, Opera, Brave) fonctionnent normalement.")


# ----- droits administrateur --------------------------------------------------
def is_admin():
    try:
        return bool(s32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(extra_args=None):
    """Relance le programme avec élévation (invite UAC). True si la demande est partie."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, []
    else:
        exe, args = pythonw(), [os.path.abspath(sys.argv[0])]
    args += [a for a in sys.argv[1:] if a != "--admin"] + (extra_args or [])
    s32.ShellExecuteW.restype = ctypes.c_void_p
    r = s32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), None, 1)
    return (r or 0) > 32


def pythonw():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.isfile(w) else exe


def launch_parts(script=None):
    """Commande pour démarrer SoNiC_0TAB0 : exe compilé, ou pythonw + script."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [pythonw(), script or os.path.abspath(sys.argv[0])]


# ----- démarrage automatique ---------------------------------------------------
TASK = "SoNiC_0TAB0"
LEGACY_TASK = "TabDock"
RUNKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, **kw)


def get_autostart():
    if _run(["schtasks", "/Query", "/TN", TASK]).returncode == 0:
        return "admin"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUNKEY) as k:
            winreg.QueryValueEx(k, TASK)
            return "user"
    except OSError:
        return "none"


def _remove_legacy_autostart():
    """Supprime l'ancien démarrage automatique « SoNiC_0TAB0 » (avant le renommage)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUNKEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, LEGACY_TASK)
    except OSError:
        pass
    if _run(["schtasks", "/Query", "/TN", LEGACY_TASK]).returncode == 0:
        _schtasks(["/Delete", "/TN", LEGACY_TASK, "/F"])


def _task_xml(cmd):
    user = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".lstrip("\\")
    exe, args = cmd[0], subprocess.list2cmdline(cmd[1:])
    target = cmd[1] if len(cmd) > 1 and not cmd[1].startswith('--') else cmd[0]
    workdir = os.path.dirname(target)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>SoNiC_0TAB0 - ouverture au démarrage (administrateur)</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{escape(user)}</UserId><Delay>PT5S</Delay></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>{escape(user)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>{escape(exe)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(workdir)}</WorkingDirectory></Exec></Actions>
</Task>"""


def _schtasks(args):
    """Exécute schtasks ; avec une invite UAC si on n'est pas administrateur."""
    if is_admin():
        return _run(["schtasks"] + args).returncode == 0
    arglist = ",".join("'" + a.replace("'", "''") + "'" for a in args)
    _run(["powershell", "-NoProfile", "-Command",
          f"Start-Process schtasks -ArgumentList {arglist} -Verb RunAs -Wait -WindowStyle Hidden"])
    return True


def set_autostart(mode, cmd):
    """mode : 'none' | 'user' (clé Run) | 'admin' (tâche planifiée, sans invite UAC au démarrage)."""
    import winreg
    _remove_legacy_autostart()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUNKEY, 0, winreg.KEY_SET_VALUE) as k:
            try:
                winreg.DeleteValue(k, TASK)
            except OSError:
                pass
            if mode == "user":
                winreg.SetValueEx(k, TASK, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
    except OSError:
        pass
    if mode == "admin":
        xml = os.path.join(tempfile.gettempdir(), "sonic_0tab0_task.xml")
        with open(xml, "w", encoding="utf-16") as f:
            f.write(_task_xml(cmd))
        _schtasks(["/Create", "/TN", TASK, "/XML", xml, "/F"])
        try:
            os.remove(xml)
        except OSError:
            pass
    elif get_autostart() == "admin":
        _schtasks(["/Delete", "/TN", TASK, "/F"])
    return get_autostart() == mode


# ----- raccourcis .lnk ---------------------------------------------------------
def make_shortcut(lnk, target, args="", workdir="", icon="", runas=False, desc="SoNiC_0TAB0"):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)

    def q(s):
        return "'" + str(s).replace("'", "''") + "'"
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(lnk)});"
          f"$s.TargetPath={q(target)};$s.Arguments={q(args)};$s.WorkingDirectory={q(workdir)};"
          f"$s.Description={q(desc)};" + (f"$s.IconLocation={q(icon)};" if icon else "") + "$s.Save()")
    _run(["powershell", "-NoProfile", "-Command", ps])
    if runas and os.path.isfile(lnk):
        with open(lnk, "rb") as f:
            b = bytearray(f.read())
        b[0x15] |= 0x20  # drapeau « exécuter en tant qu'administrateur »
        with open(lnk, "wb") as f:
            f.write(b)
    return os.path.isfile(lnk)


# ----- cartes réseau / routes ----------------------------------------------------
def list_interfaces():
    """Cartes réseau IPv4 actives : [{'index', 'name', 'ip', 'gw'}] (gw = a une passerelle Internet)."""
    ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
          "$gw=@{}; Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
          "ForEach-Object { $gw[[int]$_.InterfaceIndex]=1 };"
          "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and "
          "$_.IPAddress -notlike '169.254.*'} | ForEach-Object { '{0}|{1}|{2}|{3}' -f "
          "$_.InterfaceIndex,$_.InterfaceAlias,$_.IPAddress,[int]$gw.ContainsKey([int]$_.InterfaceIndex) }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                       creationflags=CREATE_NO_WINDOW)
    out = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 3 and parts[0].isdigit():
            out.append({"index": int(parts[0]), "name": parts[1], "ip": parts[2],
                        "gw": len(parts) < 4 or parts[3] == "1"})
    return out


def make_bind_hook(ifindex, ip=None):
    """Force la carte de sortie d'une socket (IP_UNICAST_IF) ; lève une erreur si impossible."""
    def hook(sock):
        sock.setsockopt(socket.IPPROTO_IP, 31, socket.htonl(int(ifindex)))  # IP_UNICAST_IF
        if ip:
            sock.bind((ip, 0))
    return hook


# ----- raccourcis clavier globaux --------------------------------------------------
class Hotkeys(threading.Thread):
    """Enregistre des RegisterHotKey dans un thread dédié (boucle de messages) et
    place le nom de l'action dans `queue` ; les échecs sont signalés par ('hk_fail', [...])."""

    SCOPED_BASE = 1000
    WM_SCOPED_ON, WM_SCOPED_OFF = 0x0401, 0x0402          # WM_USER + 1 / + 2

    def __init__(self, mapping, queue, scoped=None):
        super().__init__(daemon=True)
        self.mapping, self.queue = mapping, queue
        self.scoped = scoped or {}
        self.scoped_ids = {}
        self.tid = None
        self.ready = threading.Event()

    def _scoped_on(self):
        if self.scoped_ids:
            return
        for i, (action, spec) in enumerate(self.scoped.items(), self.SCOPED_BASE):
            p = core.parse_hotkey(spec)
            if p and u32.RegisterHotKey(None, i, p[0] | 0x4000, p[1]):
                self.scoped_ids[i] = action

    def _scoped_off(self):
        for i in self.scoped_ids:
            u32.UnregisterHotKey(None, i)
        self.scoped_ids = {}

    def set_scoped(self, on):
        """Active / coupe les raccourcis « fenêtre active seulement » (appelable depuis tout thread)."""
        if self.scoped and self.tid:
            u32.PostThreadMessageW(self.tid, self.WM_SCOPED_ON if on else self.WM_SCOPED_OFF, 0, 0)

    def run(self):
        self.tid = k32.GetCurrentThreadId()
        ids, failed = {}, []
        for i, (action, spec) in enumerate(self.mapping.items(), 1):
            p = core.parse_hotkey(spec)
            if p and u32.RegisterHotKey(None, i, p[0] | 0x4000, p[1]):
                ids[i] = action
            else:
                failed.append(f"{action} ({spec})")
        self.ready.set()
        if failed:
            self.queue.put(("hk_fail", failed))
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                act = ids.get(msg.wParam) or self.scoped_ids.get(msg.wParam)
                if act:
                    self.queue.put(("action", act))
            elif msg.message == self.WM_SCOPED_ON:
                self._scoped_on()
            elif msg.message == self.WM_SCOPED_OFF:
                self._scoped_off()
        self._scoped_off()
        for i in ids:
            u32.UnregisterHotKey(None, i)

    def stop(self):
        self.ready.wait(2)
        if self.tid:
            u32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
