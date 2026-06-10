"""
Generates English overlay sprites for the dialogue speaker-name plates (talker_*)
and the QTE action prompts (adv_action_*), both inside mgr/adv2.unity3d.

For each sprite it dims the original Japanese art and composites the English text
on top (blue fill + white outline, auto-sized and word-wrapped to fit the image),
writing files/sprites/<name>.png — which the build then bakes into the patch.

Text comes from the editable maps files/_talker_map.json and files/_action_map.json.

  python scripts/make_overlays.py            # generate all
  python scripts/make_overlays.py --only talker_000,adv_action_ACT_009_L
"""
import UnityPy, json, sys, os, argparse
from PIL import Image, ImageDraw, ImageFont

BUNDLE = "original_files/Switch/Data/StreamingAssets/Switch/AssetBundles/mgr/adv2.unity3d"
FONT   = "files/_optional_fonts/FOT-NEWRODINPRO-DB.ttf"   # Inter SemiBold
DIM    = 0.30
FILL   = (21, 103, 154, 255)     # blue, matching the original name plates
STROKE = (255, 255, 255, 255)    # white outline
OUTDIR = "files/sprites"


def wrap(draw, text, font, max_w, sw):
    out, cur = [], ""
    for word in text.split(" "):
        cand = word if not cur else cur + " " + word
        w = draw.textbbox((0, 0), cand, font=font, stroke_width=sw)[2]
        if not cur or w <= max_w:
            cur = cand
        else:
            out.append(cur); cur = word
    if cur:
        out.append(cur)
    return out


def fit(draw, text, max_w, max_h):
    """Largest font (with wrapping) that fits text in max_w x max_h."""
    for size in range(72, 13, -2):
        font = ImageFont.truetype(FONT, size)
        sw   = max(2, size // 11)
        lines = wrap(draw, text, font, max_w, sw)
        asc, desc = font.getmetrics()
        lh = asc + desc + sw * 2
        widths = [draw.textbbox((0, 0), l, font=font, stroke_width=sw)[2] for l in lines]
        if max(widths) <= max_w and lh * len(lines) <= max_h:
            return font, lines, sw, lh
    return font, lines, sw, lh


def make(name, text, img):
    W, H = img.size
    dim = img.copy()
    dim.putalpha(dim.getchannel("A").point(lambda p: int(p * DIM)))
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(dim)
    draw = ImageDraw.Draw(canvas)
    font, lines, sw, lh = fit(draw, text, W * 0.92, H * 0.92)
    y = (H - lh * len(lines)) / 2
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font, stroke_width=sw)
        x = (W - (bb[2] - bb[0])) / 2 - bb[0]
        draw.text((x, y - bb[1]), line, font=font, fill=FILL, stroke_width=sw, stroke_fill=STROKE)
        y += lh
    canvas.save(os.path.join(OUTDIR, f"{name}.png"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated sprite names to (re)generate")
    args = ap.parse_args()

    names = {}
    for f in ("files/_talker_map.json", "files/_action_map.json"):
        if os.path.exists(f):
            names.update(json.load(open(f, encoding="utf-8")))
    if args.only:
        want = set(args.only.split(","))
        names = {k: v for k, v in names.items() if k in want}

    os.makedirs(OUTDIR, exist_ok=True)
    env = UnityPy.load(BUNDLE)
    done = 0
    for o in env.objects:
        if o.type.name != "Sprite":
            continue
        try: d = o.read()
        except Exception: continue
        if d.m_Name in names:
            make(d.m_Name, names[d.m_Name], d.image.convert("RGBA"))
            done += 1
    print(f"generated {done}/{len(names)} overlays into {OUTDIR}/")


if __name__ == "__main__":
    main()
