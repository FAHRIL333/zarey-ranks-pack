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

def draw_bedrock_native(text, top, bot, border, w):
    """Badge Bedrock digambar LANGSUNG di ukuran akhir (tanpa downscale) supaya tidak blur.

    Ukuran render klien ikut jumlah piksel art, jadi ukuran tetap = w kecil,
    ketajaman didapat dari teks yang di-threshold jadi biner 1 bit (tajam, tanpa halo abu-abu).
    """
    h = max(7, round(w * 12 / 36))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    body = Image.new("RGBA", (w, h))
    bd = ImageDraw.Draw(body)
    for y in range(h):
        bd.line([(0, y), (w, y)], fill=lerp(top, bot, y / max(1, h - 1)) + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=max(2, h // 2), fill=255)
    img.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=max(2, h // 2), outline=border + (255,), width=1)
    # teks: render 4x lalu threshold -> biner, tepi tajam
    target_cap = max(4, h - 6)
    size = target_cap * 4
    f = ImageFont.truetype(FONT_BOLD, size)
    bb = f.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    while tw > (w - 6) * 4 and size > 4:
        size -= 1
        f = ImageFont.truetype(FONT_BOLD, size)
        bb = f.getbbox(text)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    layer = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(layer).text((-bb[0], -bb[1]), text, font=f, fill=255)
    layer = layer.resize((max(1, round(tw / 4)), max(1, round(th / 4))), Image.LANCZOS)
    ox = (w - layer.width) // 2
    oy = (h - layer.height) // 2
    img.paste((255, 255, 255, 255), (ox, oy), layer)
    return img


def bedrock_cell(badge, cell=128):
    """Tempel badge apa adanya di tengah sel; sisanya transparan (bbox = ukuran render)."""
    canvas = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    canvas.alpha_composite(badge, ((cell - badge.width) // 2, (cell - badge.height) // 2))
    return canvas

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
    CELL = 128  # sel kecil: rasio badge tetap, resolusi 2x lipat biar label "WARGA" nggak blur
    glyph_sheet = Image.new("RGBA", (CELL * 16, CELL * 16), (0, 0, 0, 0))
    cell_index = 0

    for name, cfg in RANKS.items():
        pill = draw_pill(cfg["label"], cfg["top"], cfg["bot"], cfg["border"])
        pill.save(os.path.join(jtex, f"{name}.png"))
        cp = chr(cfg["cp"])
        providers.append({"type": "bitmap", "file": f"zareyranks:font/{name}.png",
                          "height": 9, "ascent": 7, "chars": [cp]})
        # bedrock: satu sel 128x128 per rank, badge di tengah (padding transparan)
        # sel 0..4 = badge sama pada ukuran berbeda, biar tuning cukup ganti prefiks (tanpa repack/reload)
        for target_w in (111, 64, 48, 36, 28):
            cell = bedrock_cell(draw_bedrock_native(cfg["label"], cfg["top"], cfg["bot"], cfg["border"], target_w))
            cx, cy = (cell_index % 16) * CELL, (cell_index // 16) * CELL
            glyph_sheet.alpha_composite(cell, (cx, cy))
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
                              "version": [1, 0, 7], "min_engine_version": [1, 21, 0]},
                   "modules": [{"type": "resources", "uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, "zareyr-names-mod")),
                                "version": [1, 0, 7]}]}, f, indent=2)

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
