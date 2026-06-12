"""
Regenerates the two title-screen sprites that still carry text inherited from the
upstream Chinese fork:

  - title_logo.png      : replaces the top line (Chinese "Summer Time Render" kanji)
                           with the English title "Summer Time Rendering", keeping the
                           existing "-Another Horizon" subtitle untouched.
  - title_copyright.png : rebuilt from the ORIGINAL JAPANESE copyright sprite (dumped
                           from mgr/title.unity3d - the font has no JP glyphs so the JP
                           text can't be re-rendered), scaled down to make room for an
                           appended "Unofficial Translation".

No backups are written - originals are always re-dumpable from original_files/.

  python scripts/make_title.py
"""
import UnityPy
from PIL import Image, ImageDraw, ImageFilter

from make_sprites import get_font, centered_pos, draw_neon, ACTIVE_FILL, ACTIVE_GLOW

SPRITES_DIR = "files/sprites"
TITLE_BUNDLE = "original_files/Switch/Data/StreamingAssets/Switch/AssetBundles/mgr/title.unity3d"


def make_logo():
    path = f"{SPRITES_DIR}/title_logo.png"
    src = Image.open(path).convert("RGBA")
    W, H = src.size  # 1154 x 428

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Keep the "-Another Horizon" subtitle (and its glow) untouched; the kanji title
    # band ends ~y262, the subtitle starts ~y268 - copy from the gap downward.
    subtitle = src.crop((0, 263, W, H))
    canvas.paste(subtitle, (0, 263), subtitle)

    # Render the English title in the freed top band (kanji occupied y86-259,
    # centered ~x577 to match the subtitle's center).
    text = "Summer Time Rendering"
    box_w, box_h = int(W * 0.95), 200
    cx, cy = 577, 178

    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for size in range(140, 20, -2):
        font = get_font(size)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        if (bb[2] - bb[0]) <= box_w and (bb[3] - bb[1]) <= box_h:
            break

    x, y = centered_pos(box_w, box_h, text, font)
    layer = draw_neon((box_w, box_h), text, font, ACTIVE_FILL, ACTIVE_GLOW, radii=(3, 8, 15))
    canvas.alpha_composite(layer, (cx - box_w // 2, cy - box_h // 2))

    canvas.save(path)
    print(f"  {path}  {W}x{H}  \"{text}\"")


def make_copyright():
    path = f"{SPRITES_DIR}/title_copyright.png"

    env = UnityPy.load(TITLE_BUNDLE)
    jp = None
    for o in env.objects:
        if o.type.name == "Sprite":
            d = o.read()
            if d.m_Name == "title_copyright":
                jp = d.image.convert("RGBA")
                break
    if jp is None:
        raise RuntimeError("title_copyright sprite not found in title.unity3d")

    W, H = jp.size  # 903 x 45

    # Scale the JP block down so it occupies the left ~590px, freeing the right side
    # for the appended English. JP content spans x3-899, y4-41 (~896x37).
    scale = 0.66
    new_w, new_h = int(W * scale), int(H * scale)
    jp_small = jp.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(jp_small, (0, (H - new_h) // 2))

    # Append "Unofficial Translation" in the freed right-hand region, matching the
    # light-cyan tone used by the upstream fork's appended translation credit.
    text = "Unofficial Translation"
    region_x0, region_x1 = new_w + 6, W - 4
    box_w, box_h = region_x1 - region_x0, H

    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for size in range(36, 8, -1):
        font = get_font(size)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        if (bb[2] - bb[0]) <= box_w - 4 and (bb[3] - bb[1]) <= box_h - 4:
            break

    fill = (108, 207, 243, 255)
    glow = (0, 0, 0, 120)
    x, y = centered_pos(box_w, box_h, text, font)
    glow_layer = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    ImageDraw.Draw(glow_layer).text((x, y), text, font=font, fill=glow)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(2))
    sharp_layer = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    ImageDraw.Draw(sharp_layer).text((x, y), text, font=font, fill=fill)
    text_layer = Image.alpha_composite(glow_layer, sharp_layer)

    canvas.alpha_composite(text_layer, (region_x0, 0))
    canvas.save(path)
    print(f"  {path}  {W}x{H}  \"{text}\"")


def main():
    print("Generating title-screen text...")
    make_logo()
    make_copyright()


if __name__ == "__main__":
    main()
