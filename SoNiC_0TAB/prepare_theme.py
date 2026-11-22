# -*- coding: utf-8 -*-
"""Prépare VOS images (ChatGPT, etc.) pour SoNiC_0TAB0 : recadre/redimensionne aux bonnes tailles
et les place dans %APPDATA%\\SoNiC_0TAB0\\theme (SoNiC_0TAB0 les charge au prochain lancement, sans recompiler).

Nécessite Pillow :  pip install pillow
Exemples :
  python prepare_theme.py --background fond.png --banner banniere.png
  python prepare_theme.py --icon icone.png --marker anim.gif
"""
import argparse
import os
import sys

from PIL import Image, ImageSequence

APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
OUT = os.path.join(APPDATA, "SoNiC_0TAB0", "theme")


def cover(im, size):
    w, h = size
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--background", help="fond de l'écran d'accueil -> 1920x1080")
    ap.add_argument("--banner", help="bannière 'À propos' -> 640x200")
    ap.add_argument("--icon", help="icône carrée -> tabdock.ico")
    ap.add_argument("--marker", help="petit marqueur animé (GIF) en haut à droite -> 50x44")
    ap.add_argument("--splash", help="grande animation d'accueil (GIF) -> 300x266 (banner.gif)")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    done = []
    if a.background:
        cover(Image.open(a.background).convert("RGB"), (1920, 1080)).save(os.path.join(OUT, "background.png"))
        done.append("background.png")
    if a.banner:
        cover(Image.open(a.banner).convert("RGB"), (640, 200)).save(os.path.join(OUT, "banner.png"))
        done.append("banner.png")
    if a.icon:
        im = cover(Image.open(a.icon).convert("RGBA"), (256, 256))
        im.save(os.path.join(OUT, "tabdock.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
        done.append("tabdock.ico")
    for src, name, size in ((a.marker, "marker.gif", (50, 44)), (a.splash, "banner.gif", (300, 266))):
        if src:
            frames = [cover(f.convert("RGB"), size) for f in ImageSequence.Iterator(Image.open(src))]
            frames[0].save(os.path.join(OUT, name), save_all=True, append_images=frames[1:],
                           duration=180, loop=0, disposal=1)
            done.append(name)
    print("Écrit dans", OUT, ":", ", ".join(done) or "rien (aucun argument)")
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
