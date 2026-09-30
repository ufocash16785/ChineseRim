"""結局插圖：每個結局一張 320x180 的像素畫（前端放大 3 倍顯示）。python -m tools.art.endings"""
import math
import pathlib
import random

from PIL import Image, ImageDraw

from . import humans, scenery
from .canvas import hexc, lighten, darken, mix

OUT = pathlib.Path(__file__).resolve().parents[2] / "chineserim" / "static" / "art"
W, H = 320, 180
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def col(c):
    return hexc(c) if isinstance(c, str) else c


def grad(im, top, bot, y0=0, y1=H, steps=14):
    top, bot = col(top), col(bot)
    px = im.load()
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        for x in range(W):
            tt = t * steps
            base, frac = int(tt), tt - int(tt)
            tq = (base + (1 if BAYER[y % 4][x % 4] / 16 < frac else 0)) / steps
            px[x, y] = mix(top, bot, min(1, tq))


def glow(im, cx, cy, r, color, strength=.8, bands=7):
    color = col(color)
    px = im.load()
    for y in range(max(0, int(cy - r)), min(H, int(cy + r) + 1)):
        for x in range(max(0, int(cx - r)), min(W, int(cx + r) + 1)):
            d = math.hypot(x - cx, y - cy) / r
            if d < 1:
                a = round((1 - d) ** 1.6 * bands) / bands * strength
                px[x, y] = mix(px[x, y], color, a)


def disc(d, cx, cy, r, c):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col(c))


def stars(im, rng, n, ymax, c="#ffffff"):
    px = im.load()
    for _ in range(n):
        x, y = rng.randrange(W), rng.randrange(ymax)
        px[x, y] = col(c) if rng.random() < .7 else lighten(col(c), 0)
        if rng.random() < .15 and x + 1 < W:
            px[x + 1, y] = col(c)


def cloud(d, x, y, w, c, hi):
    for i in range(5):
        rx = w * (.18 + .05 * ((i * 7) % 3))
        cx = x + (i - 2) * w * .2
        cy = y - (3 if i % 2 else 0) * w / 40
        d.ellipse([cx - rx, cy - rx * .55, cx + rx, cy + rx * .55], fill=col(c))
    d.ellipse([x - w * .3, y - w * .12, x + w * .1, y + w * .05], fill=col(hi))


def mountains(d, base, amp, c, seed, rough=.55, step=6, top=None):
    rng = random.Random(seed)
    pts, h = [], amp * .5
    for x in range(-step, W + step * 2, step):
        h += rng.uniform(-amp, amp) * rough
        h = max(amp * .15, min(amp * 1.2, h))
        pts.append((x, base - h))
    poly = [(-step, H)] + pts + [(W + step * 2, H)]
    d.polygon(poly, fill=col(c))
    if top:
        for a, b in zip(pts, pts[1:]):
            d.line([a, b], fill=col(top), width=1)


def sprite(im, pal_cfg, x, y, scale=2, flip=False, pose=None, clip=None, alpha=1.0):
    """把小人偶貼到 (x=中心, y=腳底)。"""
    p = humans.Pal(**pal_cfg)
    fr = humans.draw_human(p, pose or dict(bob=0, armFront=0, armBack=0, flutter=1)).image()
    if flip:
        fr = fr.transpose(Image.FLIP_LEFT_RIGHT)
    fr = fr.resize((fr.width * scale, fr.height * scale), Image.NEAREST)
    ox, oy = int(x - fr.width / 2), int(y - 49 * scale)
    if clip:
        mask = Image.new("L", fr.size, 0)
        md = ImageDraw.Draw(mask)
        cx0, cx1 = clip
        md.rectangle([cx0 - ox, 0, cx1 - ox, fr.height], fill=255)
        a = fr.split()[3]
        fr.putalpha(Image.composite(a, Image.new("L", fr.size, 0), mask))
    im.paste(fr, (ox, oy), fr)


def shadow(d, x, y, w, c="#00000060"):
    d.ellipse([x - w, y - 2, x + w, y + 2], fill=col("#101018"))


def sword_stuck(d, x, y, lean, c="#dfe8f0", h=16):
    ex, ey = x + lean, y - h
    d.line([(x, y), (ex, ey)], fill=col(c), width=1)
    d.line([(ex - 2, ey + 4), (ex + 2, ey + 4 + lean // 2)], fill=col("#8a5a2b"), width=1)


def petals(im, rng, n, c, x0=0, x1=W, y0=0, y1=H):
    px = im.load()
    for _ in range(n):
        x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
        px[x, y] = col(c)
        if x + 1 < W:
            px[x + 1, y] = lighten(col(c), .3)


HERO = dict(robe="#2a2438", trim="#ffd35a", sash="#c8a030", hair="#e8e8f0", hairstyle="ponytail")


DEFAULT_COMPANION = dict(robe="#fbe7a8", trim="#fff8e0", sash="#f08a4a", hair="#3a2a20", hairstyle="long", accessory="flower", female=True,
                         eye="#a06a2a", shawl="#fff0c0", ornament="#ffb84a")


def blood_lord():
    im, rng = Image.new("RGB", (W, H)), random.Random(11)
    grad(im, "#12030a", "#8a1c22")
    d = ImageDraw.Draw(im)
    glow(im, 215, 62, 60, "#ff3030", .55)
    disc(d, 215, 62, 24, "#b81820")
    disc(d, 212, 58, 18, "#d42a30")
    for _ in range(4):
        cloud(d, rng.randrange(20, 300), rng.randrange(20, 90), rng.randrange(60, 110), "#2a0810", "#3e0c16")
    mountains(d, 122, 40, "#1c0509", 5, .7, 5, "#3a0a12")
    mountains(d, 138, 22, "#0e0205", 8, .8, 4)
    d.rectangle([0, 138, W, H], fill=col("#140306"))
    for y in range(140, H, 3):
        d.line([(0, y), (W, y)], fill=mix(col("#140306"), col("#5a0e14"), (y - 138) / 45))
    for _ in range(46):
        x, y = rng.randrange(6, W - 6), rng.randrange(142, H - 3)
        sword_stuck(d, x, y, rng.choice([-3, -2, -1, 1, 2, 3]), h=rng.randrange(10, 20))
    d.polygon([(106, 154), (138, 116), (182, 116), (214, 154)], fill=col("#3a0a12"))
    d.polygon([(110, 152), (140, 118), (180, 118), (212, 152)], fill=col("#0c0204"))
    d.polygon([(124, 152), (146, 124), (176, 124), (198, 152)], fill=col("#1a0508"))
    sprite(im, dict(robe="#14080c", trim="#d02030", sash="#801018", hair="#d8d8e0", hairstyle="ponytail"), 160, 122, 2,
           pose=dict(bob=0, armFront=5, armBack=1, sword="up", flutter=2))
    glow(im, 160, 95, 34, "#ff2030", .35)
    for _ in range(140):                                    # 血雨
        x, y = rng.randrange(W), rng.randrange(H)
        d.line([(x, y), (x - 2, y + 6)], fill=col("#c02030"))
    petals(im, rng, 60, "#ff8a60")                          # 火星
    return im


def kill_way():
    im, rng = Image.new("RGB", (W, H)), random.Random(21)
    grad(im, "#060c1c", "#3a4f74")
    d = ImageDraw.Draw(im)
    stars(im, rng, 90, 90, "#dfe8ff")
    glow(im, 70, 48, 55, "#b8d0ff", .5)
    disc(d, 70, 48, 19, "#eef4ff")
    disc(d, 64, 44, 4, "#d0dcf0"); disc(d, 76, 54, 3, "#d0dcf0")
    mountains(d, 128, 34, "#16223a", 3, .6, 6, "#4a6088")
    mountains(d, 142, 20, "#101c30", 9, .7, 5)
    d.rectangle([0, 142, W, H], fill=col("#0c1424"))
    for y in range(142, H, 2):
        d.line([(0, y), (W, y)], fill=mix(col("#1a2a44"), col("#080e1c"), (y - 142) / 38))
    for i in range(14):                                     # 殘旗與斷劍
        x, y = 40 + i * 21 + rng.randrange(-6, 6), rng.randrange(150, 172)
        if i % 3 == 0:
            d.line([(x, y), (x + rng.randrange(-2, 3), y - 26)], fill=col("#3a2a2a"))
            d.polygon([(x, y - 26), (x + 11, y - 22), (x + 6, y - 19), (x + 12, y - 15), (x, y - 16)], fill=col("#6a2028"))
        else:
            sword_stuck(d, x, y, rng.choice([-2, 2, 3, -3]), "#9fb0c8", rng.randrange(9, 16))
    px = im.load()
    for k in range(3):                                      # 霧
        y0 = 148 + k * 10
        for x in range(W):
            yy = y0 + int(2.5 * math.sin(x / 17 + k * 2))
            for t in range(4):
                if 0 <= yy + t < H:
                    px[x, yy + t] = mix(px[x, yy + t], col("#9ab0d8"), .22 - t * .04)
    shadow(d, 170, 160, 26)
    sprite(im, dict(robe="#2a3450", trim="#a8bcd8", sash="#1a2038", hair="#2b2233", hairstyle="topknot"), 170, 160, 2,
           pose=dict(bob=0, armFront=3, armBack=1, sword="down", flutter=1))
    return im


def saint():
    im, rng = Image.new("RGB", (W, H)), random.Random(31)
    grad(im, "#f4c88a", "#fff2d4", 0, 120)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 120, W, H], fill=col("#fff2d4"))
    glow(im, 160, 80, 110, "#fff6c8", .9, 9)
    for k in range(18):                                     # 光芒
        a = k / 18 * math.pi * 2
        d.line([(160, 80), (160 + math.cos(a) * 200, 80 + math.sin(a) * 200)], fill=mix(col("#fff0b8"), col("#ffe4a0"), .5))
    glow(im, 160, 80, 60, "#ffffff", .85, 8)
    for i in range(6):
        cloud(d, rng.randrange(0, W), rng.randrange(100, 140), rng.randrange(70, 120), "#ffd9c0", "#fff4ea")
    mountains(d, 150, 20, "#e8b890", 7, .6, 6, "#fff0d8")
    d.rectangle([0, 150, W, H], fill=col("#e6b088"))
    for x in range(0, W, 2):
        d.line([(x, 150 + int(3 * math.sin(x / 9))), (x, H)], fill=mix(col("#f0c8a0"), col("#d09870"), (x % 40) / 40))
    for i in range(16):                                     # 仰望的人群
        x = 20 + i * 19 + rng.randrange(-4, 5)
        cfg = rng.choice([dict(robe="#b98a5a", trim="#e8d8b0", sash="#8a5a3a", hair="#3a2a2a", hairstyle="long", female=True),
                          dict(robe="#8a7a5a", trim="#c8b88a", sash="#5a4a2a", hair="#3a2a2a", hairstyle="short"),
                          dict(robe="#a85a4a", trim="#f0d8b0", sash="#5a2a2a", hair="#2b2233", hairstyle="topknot")])
        cfg["sword"] = False
        sprite(im, cfg, x, 160 + (i % 3) * 6, 1, pose=dict(bob=i % 2, armFront=5, armBack=5, flutter=0))
        d.ellipse([x - 1, 128 + (i % 3) * 6, x + 1, 130 + (i % 3) * 6], fill=col("#ffb84a"))
    d.ellipse([160 - 20, 40, 160 + 20, 50], outline=col("#ffd35a"), width=2)        # 光環
    d.ellipse([160 - 16, 41, 160 + 16, 49], outline=col("#fff4b0"))
    sprite(im, dict(robe="#f6f3ea", trim="#ffd35a", sash="#e8c060", hair="#2b2233", hairstyle="topknot"), 160, 122, 2,
           pose=dict(bob=1, armFront=2, armBack=2, flutter=2, fly=True))
    petals(im, rng, 90, "#ffb0c0")
    return im


def benevolent():
    im, rng = Image.new("RGB", (W, H)), random.Random(41)
    grad(im, "#22184a", "#f2a466")
    d = ImageDraw.Draw(im)
    stars(im, rng, 40, 50, "#ffe8d0")
    glow(im, 260, 108, 46, "#ffd090", .7)
    disc(d, 260, 108, 12, "#ffe0a8")
    mountains(d, 120, 30, "#3a2a5a", 4, .6, 6, "#7a5a8a")
    mountains(d, 136, 16, "#241844", 6, .7, 5)
    d.rectangle([0, 136, W, H], fill=col("#2a1e38"))
    for y in range(136, H):
        d.line([(0, y), (W, y)], fill=mix(col("#4a3a4a"), col("#1a1428"), (y - 136) / 44))
    hs = scenery.house("tiannan", 0).image()
    for i, (x, s) in enumerate([(28, 1), (78, 1), (232, 1), (288, 1)]):
        hsn = hs.resize((hs.width * s, hs.height * s), Image.NEAREST)
        dark = Image.new("RGBA", hsn.size, (30, 20, 50, 110))
        hsn2 = Image.alpha_composite(hsn, dark)
        im.paste(hsn2, (x - hsn.width // 2, 138 - hsn.height), hsn2)
        d.rectangle([x - 4, 138 - hsn.height + 14, x + 1, 138 - hsn.height + 18], fill=col("#ffd070"))
    d.polygon([(120, 180), (190, 180), (176, 138), (138, 138)], fill=col("#5a4a4a"))    # 小路
    for lx in (108, 202):                                    # 燈籠
        d.line([(lx, 150), (lx, 170)], fill=col("#3a2a2a"))
        glow(im, lx, 148, 14, "#ffb040", .8)
        disc(d, lx, 148, 3, "#ff9a30")
    sprite(im, dict(robe="#4a86b8", trim="#f2f0e6", sash="#c0392b", hair="#2b2233", hairstyle="topknot"), 145, 170, 2,
           pose=dict(bob=0, armFront=3, armBack=1, flutter=1))
    sprite(im, dict(robe="#6a8a5a", trim="#e0e0c0", sash="#4a5a3a", hair="#c0c0c0", beard="#d0d0d0", hairstyle="elder", sword=False), 188, 170, 2, flip=True,
           pose=dict(bob=1, armFront=3, armBack=3, flutter=0))
    sprite(im, dict(robe="#b98a5a", trim="#e8d8b0", sash="#8a5a3a", hair="#3a2a2a", hairstyle="long", female=True, sword=False), 222, 172, 1, flip=True,
           pose=dict(bob=0, armFront=0, armBack=0, flutter=0))
    petals(im, rng, 40, "#ffe070", 0, W, 100, 170)          # 螢火
    return im


def two_faces():
    im, rng = Image.new("RGB", (W, H)), random.Random(51)
    left, right = Image.new("RGB", (W, H)), Image.new("RGB", (W, H))
    grad(left, "#9fd0ff", "#f4faff")
    grad(right, "#04040c", "#241638")
    dl, dr = ImageDraw.Draw(left), ImageDraw.Draw(right)
    for i in range(4):
        cloud(dl, rng.randrange(0, 170), rng.randrange(30, 110), rng.randrange(60, 100), "#ffffff", "#ffffff")
    mountains(dl, 140, 34, "#a8c8e8", 2, .6, 6, "#ffffff")
    dl.rectangle([0, 146, W, H], fill=col("#78b860"))
    for x in range(0, 170, 3):
        dl.line([(x, 146), (x + rng.randrange(-1, 2), 142 - rng.randrange(0, 4))], fill=col("#5aa048"))
    stars(right, rng, 110, 110, "#e8e0ff")
    glow(right, 250, 46, 40, "#8a6ad0", .5)
    disc(dr, 250, 46, 13, "#d8ccff")
    mountains(dr, 140, 34, "#120c24", 6, .7, 5, "#3a2a5a")
    dr.rectangle([0, 146, W, H], fill=col("#160e24"))
    for x in range(160, W, 4):
        dr.line([(x, 146), (x + rng.randrange(-2, 3), 140 - rng.randrange(0, 6))], fill=col("#2a1a44"))
    im.paste(left.crop((0, 0, 160, H)), (0, 0))
    im.paste(right.crop((160, 0, W, H)), (160, 0))
    d = ImageDraw.Draw(im)
    for y in range(H):                                       # 中線柔光
        for dx in range(-3, 4):
            px = im.load()
            x = 160 + dx
            px[x, y] = mix(px[x, y], col("#ffffff"), .25 - abs(dx) * .05)
    cx, cy, r = 160, 84, 46                                   # 太極
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col("#1a1a24"))
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 90, 270, fill=col("#f4f4fa"))
    d.ellipse([cx - r // 2, cy - r, cx + r // 2, cy], fill=col("#f4f4fa"))
    d.ellipse([cx - r // 2, cy, cx + r // 2, cy + r], fill=col("#1a1a24"))
    d.ellipse([cx - 5, cy - r // 2 - 5, cx + 5, cy - r // 2 + 5], fill=col("#1a1a24"))
    d.ellipse([cx - 5, cy + r // 2 - 5, cx + 5, cy + r // 2 + 5], fill=col("#f4f4fa"))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col("#c8a030"), width=2)
    glow(im, 160, 84, 70, "#ffe090", .2)
    white = dict(robe="#f6f6fa", trim="#c8c8d8", sash="#8a8aa0", hair="#2b2233", hairstyle="topknot")
    black = dict(robe="#1a1a28", trim="#5a5a78", sash="#3a3a58", hair="#2b2233", hairstyle="topknot")
    shadow(d, 160, 162, 22)
    sprite(im, white, 160, 162, 2, clip=(0, 159))
    sprite(im, black, 160, 162, 2, clip=(160, W))
    return im


def together(comp=None):
    im, rng = Image.new("RGB", (W, H)), random.Random(61)
    grad(im, "#6a4a9a", "#ffd8a0", 0, 130)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 130, W, H], fill=col("#ffe6c0"))
    glow(im, 250, 92, 100, "#fff0c0", .95, 9)
    glow(im, 250, 92, 44, "#ffffff", .9, 8)
    for k in range(14):
        a = -math.pi / 2 + (k - 6.5) * .16
        d.line([(250, 92), (250 + math.cos(a) * 240, 92 + math.sin(a) * 240)], fill=mix(col("#ffe6b0"), col("#ffd890"), .5))
    for i in range(5):
        cloud(d, rng.randrange(0, W), rng.randrange(110, 165), rng.randrange(80, 130), "#ffe0d0" if i % 2 else "#fff4ec", "#ffffff")
    for x0 in (216, 284):                                    # 天門
        d.rectangle([x0 - 6, 50, x0 + 6, 128], fill=col("#e8b848"))
        d.rectangle([x0 - 4, 50, x0 - 2, 128], fill=col("#fff0a0"))
        d.rectangle([x0 - 8, 122, x0 + 8, 130], fill=col("#b88a2a"))
    d.polygon([(200, 50), (300, 50), (312, 42), (188, 42)], fill=col("#c0902a"))
    d.polygon([(206, 42), (294, 42), (250, 24)], fill=col("#e8b848"))
    d.rectangle([222, 58, 278, 66], fill=col("#b88a2a"))
    glow(im, 250, 96, 26, "#ffffff", .9, 6)
    for i in range(7):                                       # 雲階
        y = 176 - i * 8
        for x in range(30 + i * 14, 210 + i * 6, 2):
            d.line([(x, y), (x, y + 5)], fill=col("#ffffff" if (x // 2 + i) % 3 else "#fff0f4"))
    hero = dict(robe="#f0f0f5", trim="#e0b84a", sash="#4a6ab8", hair="#2b2233", hairstyle="topknot")
    comp = dict(comp or DEFAULT_COMPANION, sword=False)
    sprite(im, comp, 132, 150, 2, pose=dict(bob=0, armFront=2, armBack=2, flutter=2))
    sprite(im, hero, 108, 150, 2, pose=dict(bob=0, armFront=2, armBack=2, flutter=1))
    d.line([(124, 122), (122, 122)], fill=col("#f6d3b0"), width=2)
    petals(im, rng, 70, "#ffb0c8")
    return im


def lone_sword():
    im, rng = Image.new("RGB", (W, H)), random.Random(71)
    grad(im, "#3a2a5a", "#f0a060", 0, 118)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 118, W, H], fill=col("#e8905a"))
    glow(im, 226, 112, 70, "#ffd080", .8)
    disc(d, 226, 112, 20, "#ffe8a8")
    for i in range(4):
        cloud(d, rng.randrange(0, W), rng.randrange(26, 80), rng.randrange(50, 90), "#c07a8a", "#f0b0a0")
    mountains(d, 122, 42, "#7a5a8a", 3, .6, 6, "#c898a0")
    mountains(d, 138, 30, "#4a3a66", 8, .65, 6, "#8a6a9a")
    mountains(d, 156, 22, "#2a2044", 12, .7, 5, "#5a4a78")
    d.rectangle([0, 156, W, H], fill=col("#241a38"))
    pts = [(60, 180), (120, 180), (150, 166), (176, 158), (150, 156), (118, 166), (94, 180)]
    d.polygon([(70, 180), (170, 180), (196, 156), (184, 156)], fill=col("#5a4a58"))     # 山路
    hs = scenery.house("tiannan", 0).image()
    for x in (30, 52, 70):                                    # 遠方故鄉
        small = hs.resize((hs.width // 2, hs.height // 2), Image.NEAREST)
        im.paste(small, (x - small.width // 2, 150 - small.height), small)
    for k in range(6):
        y = 132 - k * 7
        x = 52 + int(5 * math.sin(k * .9))
        d.ellipse([x - 2 - k // 2, y - 2, x + 2 + k // 2, y + 2], fill=mix(col("#e0b8b0"), col("#ffe0c0"), k / 6))
    for bx, by in ((120, 60), (134, 70), (110, 74)):         # 飛鳥
        d.line([(bx - 4, by), (bx, by + 2), (bx + 4, by)], fill=col("#2a1a30"))
    shadow(d, 176, 172, 18)
    sprite(im, dict(robe="#8a7a5a", trim="#c8b88a", sash="#5a4a2a", hair="#2b2233", hairstyle="short", hat="#b89a5a"), 176, 172, 2,
           pose=dict(bob=0, legF=(3, 0), legB=(-3, 0), armFront=3, armBack=1, flutter=1))
    return im


ENDINGS = {"blood_lord": blood_lord, "kill_way": kill_way, "saint": saint, "benevolent": benevolent,
           "two_faces": two_faces, "together": together, "lone_sword": lone_sword}


def companion_cfgs():
    """每位道侶候選人一份「攜手同登」用的服飾設定（取自小人偶 NPC 設定）。"""
    import json
    from .build import NPCS
    cands = json.loads((OUT.parents[2] / "data" / "companions.json").read_text(encoding="utf-8"))["candidates"]
    return {cid: NPCS[c["sprite"]] for cid, c in cands.items() if c["sprite"] in NPCS}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in ENDINGS.items():
        fn().save(OUT / f"ending_{name}.png")
    cfgs = companion_cfgs()
    for cid, cfg in cfgs.items():
        together(cfg).save(OUT / f"ending_together_{cid}.png")
    print("結局插圖：", sorted(ENDINGS), "道侶版：", sorted(cfgs))


if __name__ == "__main__":
    main()
