#!/usr/bin/env python3
"""Generate rank badge resource packs (Java + Bedrock) for ZareyEcoSMP."""
import json, os, shutil, zipfile, hashlib
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.expanduser("~/projects/zarey-ranks/build")
SRC = os.path.expanduser("~/projects/zarey-ranks/src")
FONT_BOLD = os.path.expanduser("~/.local/share/fonts/PlusJakartaSans-ExtraBold.ttf")

# rank -> (label, color_top, color_bottom, border, cp)
RANKS = {
    "warga": {"label": "WARGA", "top": (74, 222, 128), "bot": (22, 163, 74), "border": (6, 46, 28), "cp": 0xE100},
}

S = 8  # supersample factor (draw big, downscale)

def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def draw_pill(text, top, bot, border, height=36, pad=10):
    """Wide rounded pill, drawn at S scale then downscaled."""
    f = ImageFont.truetype(FONT_BOLD, 22 * S)
    track = 1 * S
    widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] for ch in text]
    tw = sum(widths) + track * (len(text) - 1)
    w = int(tw) + pad * 2 * S
    h = height * S
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = h // 2
    # gradient body
    body = Image.new("RGBA", (w, h))
    bd = ImageDraw.Draw(body)
    for y in range(h):
        bd.line([(0, y), (w, y)], fill=lerp(top, bot, y / max(1, h - 1)) + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    img.paste(body, (0, 0), mask)
    # border
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, outline=border + (255,), width=max(2, 2 * S // 2))
    # top gloss
    gloss = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    gd.rounded_rectangle([2 * S, 2 * S, w - 2 * S, h // 2], radius=r // 2, fill=(255, 255, 255, 46))
    img = Image.alpha_composite(img, gloss)
    d = ImageDraw.Draw(img)
    # text
    x = pad * S
    for ch, cw in zip(text, widths):
        bb = f.getbbox(ch)
        d.text((x - bb[0], h // 2 - (bb[1] + bb[3]) // 2 - 1 * S), ch, font=f, fill=(255, 255, 255, 255))
        x += cw + track
    return img.resize((max(1, w // S), max(1, h // S)), Image.LANCZOS)

def draw_bedrock_pill(label, top, bot, border):
    """Pill digambar utuh 16*len x 16 px, lalu dipotong per 16 px supaya sel nyambung."""
    n = len(label)
    W, H = 16 * n * S, 16 * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body = Image.new("RGBA", (W, H))
    bd = ImageDraw.Draw(body)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=lerp(top, bot, y / (H - 1)) + (255,))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, W - 1, H - 1], radius=4 * S, fill=255)
    img.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=4 * S, outline=border + (255,), width=max(1, S))
    f = ImageFont.truetype(FONT_BOLD, 11 * S)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] for c in label]
    track = -1 * S
    total = sum(widths) + track * (n - 1)
    x = (W - total) // 2
    for ch, cw in zip(label, widths):
        bb = f.getbbox(ch)
        d.text((x - bb[0], (H - (bb[3] - bb[1])) // 2 - bb[1]), ch, font=f, fill=(255, 255, 255, 255))
        x += cw + track
    small = img.resize((16 * n, 16), Image.LANCZOS)
    return [small.crop((i * 16, 0, i * 16 + 16, 16)) for i in range(n)]

def main():
    shutil.rmtree(OUT, ignore_errors=True)
    jroot = os.path.join(OUT, "java")
    jfont = os.path.join(jroot, "assets/minecraft/font")
    jtex = os.path.join(jroot, "assets/zareyranks/textures/font")
    os.makedirs(jfont, exist_ok=True)
    os.makedirs(jtex, exist_ok=True)

    broot = os.path.join(OUT, "bedrock")
    bfont = os.path.join(broot, "font")
    os.makedirs(bfont, exist_ok=True)

    providers, preview = [], Image.new("RGBA", (400, 60), (28, 28, 32, 255))
    bx = 8
    glyph_sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    cell_index = 0

    for name, cfg in RANKS.items():
        pill = draw_pill(cfg["label"], cfg["top"], cfg["bot"], cfg["border"])
        pill.save(os.path.join(jtex, f"{name}.png"))
        cp = chr(cfg["cp"])
        providers.append({"type": "bitmap", "file": f"zareyranks:font/{name}.png",
                          "height": 9, "ascent": 7, "chars": [cp]})
        # bedrock: one cell per letter, packed left-to-right
        for tile in draw_bedrock_pill(cfg["label"], cfg["top"], cfg["bot"], cfg["border"]):
            cx, cy = (cell_index % 16) * 16, (cell_index // 16) * 16
            glyph_sheet.alpha_composite(tile, (cx, cy))
            cell_index += 1
        preview.alpha_composite(pill, (bx, 22))
        bx += pill.width + 10
        print(f"{name}: java glyph U+{cfg['cp']:04X} pill {pill.width}x{pill.height}, bedrock cells U+{cfg['cp']:04X}..U+{cfg['cp']+len(cfg['label'])-1:04X}")

    glyph_sheet.save(os.path.join(bfont, "glyph_E1.png"))
    preview.save(os.path.join(OUT, "preview.png"))

    base = {"providers": []}
    vanilla = os.path.join(SRC, "vanilla-default.json")
    if os.path.exists(vanilla):
        base = json.load(open(vanilla))
    with open(os.path.join(jfont, "default.json"), "w") as f:
        json.dump({"providers": base.get("providers", []) + providers}, f, indent=2)

    with open(os.path.join(jroot, "pack.mcmeta"), "w") as f:
        json.dump({"pack": {"pack_format": 46,
                            "supported_formats": {"min_inclusive": 15, "max_inclusive": 99},
                            "description": "ZareyEcoSMP Rank Badges"}}, f, indent=2)

    import uuid
    with open(os.path.join(broot, "manifest.json"), "w") as f:
        json.dump({"format_version": 2,
                   "header": {"name": "ZareyEcoSMP Ranks", "uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, "zareyr-names-uuid")),
                              "version": [1, 0, 1], "min_engine_version": [1, 21, 0]},
                   "modules": [{"type": "resources", "uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, "zareyr-names-mod")),
                                "version": [1, 0, 1]}]}, f, indent=2)

    for src, name in ((jroot, "ZareyRanks-Java.zip"), (broot, "ZareyRanks-Bedrock.mcpack")):
        path = os.path.join(OUT, name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for dp, _, fs in os.walk(src):
                for fn in fs:
                    full = os.path.join(dp, fn)
                    z.write(full, os.path.relpath(full, src))
        h = hashlib.sha1(open(path, "rb").read()).hexdigest()
        print(name, os.path.getsize(path), "bytes sha1", h)

if __name__ == "__main__":
    main()
