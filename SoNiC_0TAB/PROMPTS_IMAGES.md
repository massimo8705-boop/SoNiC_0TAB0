# Prompts pour générer vos visuels (ChatGPT / autre)

Style commun à garder dans tous les prompts (cohérence avec votre mascotte) :
*« cosmic hooded cat mage, sapphire-blue eyes, black robe with gold trim, golden "MD" monogram emblem,
neon blue galaxy, glowing gold orbital rings, stylized anime-cartoon illustration, high contrast, clean lines »*

## 1. Fond d'accueil — `background.png` (16:9, rendu final 1920x1080)
> Wide 16:9 dark cosmic wallpaper for a desktop app empty screen. Deep navy-to-black starfield, a distant
> spiral galaxy in the top-right corner, thin glowing gold orbital rings crossing softly, subtle blue nebula
> dust. VERY low contrast and dark in the center (that area must stay calm and empty for text and an
> animation). Tiny faint golden "MD" monogram watermark in the bottom-left. No characters, no text,
> no borders. Anime-cartoon illustration style, neon blue and gold palette.

## 2. Bannière « À propos » — `banner.png` (3,2:1, rendu final 640x200)
> Ultra-wide panoramic banner, 3:1. A cosmic hooded cat mage with sapphire-blue eyes and a black-and-gold
> robe with a golden "MD" emblem, smiling confidently, seen from the chest up, placed on the LEFT third.
> Behind him a glowing galaxy swirl and orbital gold rings flowing to the right; empty dark starry space
> on the right two thirds for a title. Keep all important details in the central horizontal band (the
> top and bottom will be cropped). Anime-cartoon style, neon blue + gold, no text.

## 3. Icône — `--icon icone.png` (carré)
> App icon, square 1:1, centered close-up of the hooded cosmic cat's face (sapphire-blue eyes, black hood
> with gold trim, small golden "MD" emblem on the forehead of the hood), dark blue galaxy background that
> fills the whole square, strong silhouette readable at 16 px, thick clean outlines, no text.

## 4. Variantes d'ambiance (optionnel)
* **Mode jour** : « same style but dawn colors: deep violet to warm orange nebula, gold rings ».
* **Écran de fin / déconnexion** : « the cosmic cat sleeping on a floating rock among stars, calm, dark ».

Conseil : générez en 1536x1024 puis laissez `prepare_theme.py` recadrer aux bonnes tailles.
