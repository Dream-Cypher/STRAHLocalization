"""
Generates English replacement sprites for STRAH: Another Horizon.

Handles:
  - Neon button pairs (_ac active / _na normal):
      title_menu_*, adv_sysmenu_*, systemwindow_Yes/No
  - Gradient bar notifications:
      adv_Autosavemark, adv_Quicksavemark, adv_LoadFailedmark, adv_notice_autosave

Originals are backed up to files/sprites/_originals/ before overwriting.

Usage (from project root):
  python scripts/make_sprites.py
"""

import os
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SPRITES_DIR = "files/sprites"
BACKUP_DIR  = "files/sprites/_originals"

FONT_PATHS = [
    "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold  (preferred)
    "C:/Windows/Fonts/arialbd.ttf",    # Arial Bold
    "C:/Windows/Fonts/calibrib.ttf",   # Calibri Bold
    "C:/Windows/Fonts/verdanab.ttf",   # Verdana Bold
]


# ── helpers ──────────────────────────────────────────────────────────────────

def get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError("No suitable font found. Expected Segoe UI Bold or Arial Bold.")


def auto_font(text: str, max_w: int, max_h: int, start: int = 48) -> ImageFont.FreeTypeFont:
    """Return largest font where 'text' fits within max_w x max_h (20px h-padding, 10px v-padding)."""
    pad_w, pad_h = 20, 10
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for size in range(start, 8, -1):
        font = get_font(size)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        if (bb[2] - bb[0]) <= max_w - pad_w and (bb[3] - bb[1]) <= max_h - pad_h:
            return font
    return get_font(8)


def centered_pos(canvas_w: int, canvas_h: int, text: str, font) -> tuple[int, int]:
    """Return top-left (x, y) to draw text centered on canvas."""
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = tmp_draw.textbbox((0, 0), text, font=font)
    x = (canvas_w - (bb[2] - bb[0])) // 2 - bb[0]
    y = (canvas_h - (bb[3] - bb[1])) // 2 - bb[1]
    return x, y


# ── neon glow rendering ───────────────────────────────────────────────────────

# Active (_ac): bright yellow text, cyan glow
ACTIVE_FILL = (255, 255,   0, 255)
ACTIVE_GLOW = (  0, 200, 255, 140)

# Normal (_na): light cyan text, softer glow
NORMAL_FILL = (160, 235, 255, 255)
NORMAL_GLOW = (  0, 170, 230, 100)


def draw_neon(size: tuple[int, int], text: str, font,
              fill: tuple, glow: tuple,
              radii: tuple = (3, 8, 15)) -> Image.Image:
    """Transparent RGBA image with neon-glowing centered text.
    Multiple blur passes at increasing radii create a layered glow."""
    w, h = size
    x, y = centered_pos(w, h, text, font)

    result = Image.new("RGBA", size, (0, 0, 0, 0))

    for r in radii:
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x, y), text, font=font, fill=glow)
        result = Image.alpha_composite(result, layer.filter(ImageFilter.GaussianBlur(r)))

    sharp = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(sharp).text((x, y), text, font=font, fill=fill)
    return Image.alpha_composite(result, sharp)


# ── gradient bar rendering ────────────────────────────────────────────────────

def sample_bar_colors(path: str) -> tuple[tuple, tuple]:
    """Sample left and right edge pixel colors from a gradient bar image."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    mid = h // 2
    return img.getpixel((4, mid)), img.getpixel((w - 5, mid))


def make_bar(width: int, height: int,
             left_rgb: tuple, right_rgb: tuple,
             text: str, font) -> Image.Image:
    """Horizontal gradient bar with centered white text."""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    for x in range(width):
        t = x / max(width - 1, 1)
        r = int(left_rgb[0] + (right_rgb[0] - left_rgb[0]) * t)
        g = int(left_rgb[1] + (right_rgb[1] - left_rgb[1]) * t)
        b = int(left_rgb[2] + (right_rgb[2] - left_rgb[2]) * t)
        draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))

    x, y = centered_pos(width, height, text, font)
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img


# ── sprite definitions ────────────────────────────────────────────────────────

NEON_BUTTONS = [
    # Title screen menu
    ("title_menu_1_gamestart", "Start Game"),
    ("title_menu_2_tips",      "TIPS"),
    ("title_menu_3_extra",     "Extra"),
    ("title_menu_4_restart",   "Restart"),
    ("title_menu_5_option",    "Options"),
    ("title_menu_6_manual",    "Manual"),
    # In-game system menu
    ("adv_sysmenu_02flow",     "Flow Chart"),
    ("adv_sysmenu_03back",     "Back"),
    ("adv_sysmenu_03save",     "Save"),
    ("adv_sysmenu_04load",     "Load"),
    ("adv_sysmenu_05resta",    "Restart"),
    ("adv_sysmenu_06option",   "Options"),
    ("adv_sysmenu_07manual",   "Manual"),
    ("adv_sysmenu_08title",    "Title"),
    # Confirmation dialog
    ("systemwindow_Yes",       "Yes"),
    ("systemwindow_No",        "No"),
]

BAR_SPRITES = [
    ("adv_Autosavemark",    "Auto Save Complete"),
    ("adv_Quicksavemark",   "Quick Save Complete"),
    ("adv_LoadFailedmark",  "No Save Data"),
    ("adv_notice_autosave", "Auto Save Complete"),
]


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)

    def backup(filename: str) -> None:
        src = os.path.join(SPRITES_DIR, filename)
        dst = os.path.join(BACKUP_DIR, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

    print("Generating neon buttons…")
    for base, text in NEON_BUTTONS:
        for variant, fill, glow, radii in [
            ("_ac", ACTIVE_FILL, ACTIVE_GLOW, (3, 8,  15)),
            ("_na", NORMAL_FILL, NORMAL_GLOW, (2, 6,  11)),
        ]:
            filename = f"{base}{variant}.png"
            path = os.path.join(SPRITES_DIR, filename)
            if not os.path.exists(path):
                print(f"  SKIP (not found): {filename}")
                continue
            backup(filename)
            orig = Image.open(path)
            font = auto_font(text, orig.width, orig.height, start=44)
            img  = draw_neon(orig.size, text, font, fill, glow, radii)
            img.save(path)
            print(f"  {filename:45s}  {orig.size[0]}x{orig.size[1]}  \"{text}\"")

    print("\nGenerating gradient bars…")
    for base, text in BAR_SPRITES:
        filename = f"{base}.png"
        path = os.path.join(SPRITES_DIR, filename)
        if not os.path.exists(path):
            print(f"  SKIP (not found): {filename}")
            continue
        backup(filename)
        orig = Image.open(path)
        left_rgb, right_rgb = sample_bar_colors(path)
        font = auto_font(text, orig.width, orig.height, start=28)
        img  = make_bar(orig.width, orig.height, left_rgb, right_rgb, text, font)
        img.save(path)
        print(f"  {filename:45s}  {orig.size[0]}x{orig.size[1]}  \"{text}\"")

    print(f"\nDone. Originals backed up to {BACKUP_DIR}/")


if __name__ == "__main__":
    main()
