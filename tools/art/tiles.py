"""俯視地圖用的 32×32 地磚、物件與大地圖圖示。"""
import math
import random

from .canvas import Canvas, darken, hexc, lighten, mix
from .scenery import BIOMES

T = 32
WATER = {"tiannan": "#3f86c8", "mulan": "#4a90c0", "luanxinghai": "#2f9fb8", "dajin": "#4a6a9a", "tianyuan": "#6a5ac8", "taixu": "#3a5aa8"}


def _r(*seed):
    return random.Random(hash(seed) & 0xffffff)


def _fill(c, col):
    c.rect(0, 0, T - 1, T - 1, col, "t")


def _speck(c, rng, cols, n, size=1):
    for _ in range(n):
        x, y = rng.randrange(T), rng.randrange(T)
        col = rng.choice(cols)
        c.rect(x, y, x + size - 1, y + size - 1, col, "t")


def grass(b, v):
    P = BIOMES[b]
    g = hexc(P["grass"])
    c = Canvas(T, T)
    rng = _r("grass", b, v)
    _fill(c, g)
    _speck(c, rng, [darken(g, .18), lighten(g, .14), darken(g, .3)], 34)
    for _ in range(3):        # 草簇
        x, y = rng.randrange(2, T - 3), rng.randrange(4, T - 2)
        c.line(x, y, x, y - 3, darken(g, .35), "t")
        c.line(x + 2, y, x + 2, y - 2, darken(g, .25), "t")
    if v == 3:
        for _ in range(3):
            x, y = rng.randrange(3, T - 4), rng.randrange(3, T - 4)
            col = rng.choice([(255, 240, 120), (255, 170, 190), (255, 255, 255)])
            c.rect(x, y, x + 1, y + 1, col, "t")
    return c


def dirt(b, v):
    d = hexc(BIOMES[b]["dirt"])
    d = lighten(d, .12)
    c = Canvas(T, T)
    rng = _r("dirt", b, v)
    _fill(c, d)
    _speck(c, rng, [darken(d, .15), lighten(d, .12)], 40)
    for _ in range(4):
        x, y = rng.randrange(2, T - 4), rng.randrange(2, T - 4)
        c.rect(x, y, x + 2, y + 1, darken(d, .3), "t")
        c.rect(x, y - 1, x + 1, y - 1, lighten(d, .25), "t")
    return c


def path(b, v):
    base = mix(hexc(BIOMES[b]["dirt"]), (170, 160, 150), .55)
    c = Canvas(T, T)
    rng = _r("path", b, v)
    _fill(c, darken(base, .25))
    for gy in range(0, T, 8):
        off = 0 if (gy // 8) % 2 == 0 else 8
        for gx in range(-off, T, 16):
            col = mix(base, lighten(base, .3), rng.random() * .6)
            c.rect(gx + 1, gy + 1, gx + 14, gy + 6, col, "t")
            c.rect(gx + 1, gy + 1, gx + 14, gy + 1, lighten(col, .25), "t")
    return c


def sand(b, v):
    s = hexc(BIOMES[b]["grass"]) if b == "luanxinghai" else (226, 208, 150)
    s = mix(s, (230, 215, 160), .5)
    c = Canvas(T, T)
    rng = _r("sand", b, v)
    _fill(c, s)
    _speck(c, rng, [darken(s, .1), lighten(s, .15)], 30)
    for _ in range(2):
        x, y = rng.randrange(0, T - 8), rng.randrange(3, T - 3)
        c.line(x, y, x + 6, y, darken(s, .18), "t")
    return c


def water(b, frame, deep=False):
    w = hexc(WATER[b])
    w = darken(w, .3) if deep else w
    c = Canvas(T, T)
    _fill(c, w)
    rng = _r("water", b, deep)
    for i in range(5):
        x, y = rng.randrange(0, T), (rng.randrange(0, T) + frame * 2) % T
        col = lighten(w, .3 if not deep else .18)
        c.line(x, y, x + 5, y, col, "t")
        c.line(x + 1, y + 1, x + 4, y + 1, mix(w, col, .5), "t")
    return c


def wood(b, v):
    c = Canvas(T, T)
    base = hexc("#b98a58")
    for i in range(4):
        col = mix(base, darken(base, .25), (i % 2) * .5)
        c.rect(0, i * 8, T - 1, i * 8 + 6, col, "t")
        c.rect(0, i * 8 + 7, T - 1, i * 8 + 7, darken(base, .45), "t")
        c.rect(3 + i * 7 % 20, i * 8 + 3, 4 + i * 7 % 20, i * 8 + 3, darken(base, .5), "t")
    return c


def court(b, v):
    base = (176, 180, 190)
    c = Canvas(T, T)
    rng = _r("court", b, v)
    _fill(c, darken(base, .3))
    for gy in (0, 16):
        for gx in (0, 16):
            col = mix(base, lighten(base, .2), rng.random() * .5)
            c.rect(gx + 1, gy + 1, gx + 14, gy + 14, col, "t")
            c.rect(gx + 1, gy + 1, gx + 14, gy + 1, lighten(col, .3), "t")
    return c


def cave_floor(b, v):
    base = (74, 66, 92)
    c = Canvas(T, T)
    rng = _r("cave", v)
    _fill(c, base)
    _speck(c, rng, [darken(base, .25), lighten(base, .18)], 40)
    return c


def cave_wall(b, v):
    base = (40, 34, 52)
    c = Canvas(T, T)
    rng = _r("cwall", v)
    _fill(c, base)
    for _ in range(9):
        x, y = rng.randrange(0, T - 8), rng.randrange(0, T - 8)
        c.rect(x, y, x + 7, y + 6, mix(base, (90, 80, 110), rng.random() * .6), "t")
        c.rect(x, y, x + 7, y, (110, 100, 130), "t")
    c.rect(0, 0, T - 1, 2, (100, 90, 120), "t")
    return c


def hedge(b, v):
    g = hexc(BIOMES[b]["leaf2"])
    c = Canvas(T, T)
    rng = _r("hedge", b, v)
    _fill(c, darken(g, .25))
    for _ in range(9):
        x, y = rng.randrange(2, T - 6), rng.randrange(2, T - 6)
        c.ellipse(x + 3, y + 3, 5, 4, mix(g, hexc(BIOMES[b]["leaf"]), rng.random()), "t")
        c.put(x + 1, y + 1, lighten(g, .4), "t")
    return c


def mountain(b, v):
    c = Canvas(T, T)
    _fill(c, hexc(BIOMES[b]["grass"]))
    rock = (128, 124, 134)
    peak = [(16, 2 + v * 2), (30, 30), (2, 30)]
    c.poly(peak, rock, "t")
    c.poly([(16, 2 + v * 2), (22, 14), (16, 30), (30, 30)], darken(rock, .25), "t")
    c.poly([(16, 2 + v * 2), (12, 11), (16, 9), (20, 12)], (245, 245, 250), "t")
    c.line(8, 22, 14, 14, lighten(rock, .2), "t")
    return c


def forest(b, v):
    P = BIOMES[b]
    c = Canvas(T, T)
    _fill(c, darken(hexc(P["grass"]), .2))
    rng = _r("forest", b, v)
    for (x, y) in ((8, 10), (22, 9), (15, 21), (5, 25), (27, 24)):
        c.ellipse(x, y, 7, 6, darken(hexc(P["leaf2"]), .1), "t")
        c.ellipse(x - 1, y - 1, 6, 5, hexc(P["leaf"]), "t")
        c.put(x - 3, y - 3, lighten(hexc(P["leaf"]), .4), "t")
    return c


def bridge(b, vertical):
    c = Canvas(T, T)
    _fill(c, hexc(WATER[b]))
    base = hexc("#a87a48")
    if vertical:
        for i in range(4):
            c.rect(4, i * 8, 27, i * 8 + 6, mix(base, darken(base, .3), i % 2 * .5), "t")
            c.rect(4, i * 8 + 7, 27, i * 8 + 7, darken(base, .5), "t")
        c.rect(3, 0, 4, T - 1, darken(base, .4), "t")
        c.rect(27, 0, 28, T - 1, darken(base, .4), "t")
    else:
        for i in range(4):
            c.rect(i * 8, 4, i * 8 + 6, 27, mix(base, darken(base, .3), i % 2 * .5), "t")
            c.rect(i * 8 + 7, 4, i * 8 + 7, 27, darken(base, .5), "t")
        c.rect(0, 3, T - 1, 4, darken(base, .4), "t")
        c.rect(0, 27, T - 1, 28, darken(base, .4), "t")
    return c


def shore(b, mask):
    """陸地磚上的海岸疊圖。mask: N=1 E=2 S=4 W=8（該方向鄰格是水）。"""
    c = Canvas(T, T)
    foam, sand_c = (245, 250, 255), (232, 214, 160)
    w = 5
    def edge(rect_sand, rect_foam):
        c.rect(*rect_sand, sand_c, "t")
        c.rect(*rect_foam, foam, "t")
    if mask & 1: edge((0, 0, T - 1, w - 1), (0, 0, T - 1, 0))
    if mask & 4: edge((0, T - w, T - 1, T - 1), (0, T - 1, T - 1, T - 1))
    if mask & 8: edge((0, 0, w - 1, T - 1), (0, 0, 0, T - 1))
    if mask & 2: edge((T - w, 0, T - 1, T - 1), (T - 1, 0, T - 1, T - 1))
    return c


# ---------------- 物件 ----------------
def well(b):
    c = Canvas(32, 34)
    c.ellipse(16, 24, 12, 8, (150, 150, 158), "s")
    c.ellipse(16, 23, 9, 5, (30, 60, 100), "w")
    c.rect(4, 12, 6, 24, hexc("#7a4a2a"), "wood")
    c.rect(26, 12, 28, 24, hexc("#7a4a2a"), "wood")
    c.poly([(1, 13), (16, 2), (31, 13)], hexc(BIOMES[b]["roof"]), "roof")
    c.line(16, 8, 16, 20, (200, 190, 160), "rope")
    return c


def stall(b):
    c = Canvas(48, 44)
    c.rect(4, 22, 43, 40, hexc("#8a5a2b"), "wood")
    c.rect(4, 22, 43, 26, hexc("#a87a48"), "wood")
    for i in range(6):
        c.rect(4 + i * 7, 6, 10 + i * 7, 20, hexc("#c0392b") if i % 2 == 0 else hexc("#f0e6d0"), "awn")
    c.rect(4, 20, 43, 21, hexc("#6a2a1a"), "awn")
    c.rect(2, 8, 3, 40, hexc("#5a3a22"), "wood")
    c.rect(44, 8, 45, 40, hexc("#5a3a22"), "wood")
    for x, col in ((10, "#e8503a"), (18, "#f0c040"), (26, "#6fbf5a"), (34, "#8fc9e8")):
        c.ellipse(x, 24, 3, 2, hexc(col), "goods")
    return c


def chest(b, open_):
    c = Canvas(28, 24)
    wood, gold = hexc("#8a5a2b"), hexc("#ffd35a")
    c.rect(2, 10, 25, 22, wood, "w")
    c.rect(2, 10, 25, 12, lighten(wood, .2), "w")
    c.rect(2, 16, 25, 17, gold, "g")
    if open_:
        c.rect(2, 2, 25, 9, darken(wood, .2), "w")
        c.rect(4, 10, 23, 13, (255, 236, 150), "g")
    else:
        c.rect(2, 4, 25, 10, wood, "w")
        c.rect(2, 4, 25, 5, lighten(wood, .25), "w")
        c.rect(12, 10, 15, 14, gold, "g")
    return c


def statue(b):
    c = Canvas(30, 50)
    c.rect(4, 40, 25, 48, (140, 140, 150), "s")
    c.rect(8, 22, 21, 40, (165, 165, 175), "s")
    c.ellipse(15, 16, 7, 8, (175, 175, 185), "s")
    c.rect(6, 24, 8, 34, (165, 165, 175), "s")
    c.rect(21, 24, 23, 34, (165, 165, 175), "s")
    return c


def sign(b):
    c = Canvas(26, 34)
    c.rect(11, 14, 14, 32, hexc("#6a4a2a"), "w")
    c.rect(2, 3, 23, 16, hexc("#b98a58"), "w")
    c.rect(2, 3, 23, 4, lighten(hexc("#b98a58"), .25), "w")
    for y in (7, 10, 13):
        c.rect(5, y, 20, y, hexc("#5a3a1a"), "t")
    return c


def banner(b):
    c = Canvas(20, 70)
    c.rect(9, 0, 10, 69, hexc("#5a3a22"), "w")
    c.rect(2, 4, 17, 46, hexc("#c0392b"), "f")
    c.poly([(2, 46), (17, 46), (9, 54)], hexc("#c0392b"), "f")
    c.rect(6, 12, 13, 30, hexc("#ffd35a"), "f")
    return c


def tent(b):
    c = Canvas(64, 52)
    c.poly([(2, 50), (32, 4), (62, 50)], hexc("#c8b48a"), "c")
    c.poly([(32, 4), (62, 50), (40, 50)], hexc("#a89468"), "c")
    c.poly([(24, 50), (32, 26), (40, 50)], hexc("#3a2a1a"), "d")
    c.line(32, 4, 32, -1, hexc("#5a3a22"), "p")
    c.rect(30, 0, 40, 5, hexc("#c0392b"), "f")
    return c


def campfire(b, t):
    c = Canvas(28, 30)
    c.rect(4, 22, 23, 25, hexc("#5a3a22"), "w")
    c.ellipse(14, 22, 10, 3, (90, 80, 80), "s")
    h = 10 + (t % 2) * 3
    c.poly([(14, 22 - h - 4), (21, 22), (7, 22)], hexc("#e8503a"), "f")
    c.poly([(14, 22 - h + 1), (18, 22), (10, 22)], hexc("#ffb040"), "f")
    c.poly([(14, 22 - h + 5), (16, 22), (12, 22)], hexc("#fff0a0"), "f")
    return c


def dock(b):
    c = Canvas(64, 44)
    c.rect(0, 10, 63, 30, hexc("#a87a48"), "w")
    for x in range(0, 64, 8):
        c.rect(x, 10, x, 30, darken(hexc("#a87a48"), .4), "w")
    for x in (2, 30, 58):
        c.rect(x, 30, x + 3, 40, hexc("#5a3a22"), "w")
    c.poly([(8, 36), (56, 36), (48, 44), (16, 44)], hexc("#7a4a2a"), "boat")
    c.rect(30, 18, 32, 36, hexc("#5a3a22"), "mast")
    c.poly([(32, 18), (48, 32), (32, 32)], hexc("#f0e6d0"), "sail")
    return c


def crystal(b):
    c = Canvas(30, 42)
    c.poly([(15, 2), (24, 20), (15, 40), (6, 20)], hexc("#8ad8f0"), "c")
    c.poly([(15, 2), (24, 20), (15, 40)], hexc("#5ab0d8"), "c")
    c.poly([(15, 2), (10, 14), (14, 12)], (255, 255, 255), "c")
    return c


def altar(b):
    c = Canvas(48, 40)
    c.rect(2, 26, 45, 38, (150, 146, 156), "s")
    c.rect(8, 16, 39, 27, (176, 172, 182), "s")
    c.rect(20, 6, 27, 17, (255, 214, 90), "g")
    c.ellipse(23.5, 5, 4, 3, (255, 120, 60), "f")
    return c


def tomb(b):
    c = Canvas(26, 34)
    c.rect(4, 8, 21, 32, (150, 150, 158), "s")
    c.ellipse(12.5, 9, 9, 7, (150, 150, 158), "s")
    c.rect(11, 12, 14, 24, (90, 90, 100), "t")
    c.rect(7, 16, 18, 18, (90, 90, 100), "t")
    return c


def dummy(b):
    c = Canvas(28, 44)
    c.rect(12, 14, 15, 42, hexc("#7a4a2a"), "w")
    c.rect(3, 18, 24, 22, hexc("#8a5a2b"), "w")
    c.ellipse(13.5, 10, 7, 7, hexc("#d8b070"), "h")
    c.rect(5, 26, 22, 27, hexc("#c0392b"), "r")
    return c


def bush(b):
    P = BIOMES[b]
    c = Canvas(30, 22)
    c.ellipse(15, 13, 13, 8, hexc(P["leaf2"]), "l")
    c.ellipse(11, 11, 8, 6, hexc(P["leaf"]), "l")
    c.put(8, 8, lighten(hexc(P["leaf"]), .4), "l")
    return c


def flowers(b):
    c = Canvas(24, 14)
    for x, y, col in ((4, 8, "#ff8aa8"), (11, 5, "#ffe070"), (18, 9, "#ffffff"), (8, 11, "#c88aff")):
        c.rect(x, y, x + 1, y + 1, hexc(col), "f")
        c.put(x, y + 2, hexc("#3a8a3a"), "s")
    return c


def boulder(b):
    c = Canvas(44, 34)
    c.poly([(2, 32), (6, 14), (18, 4), (34, 6), (42, 18), (42, 32)], (128, 126, 136), "r")
    c.poly([(12, 12), (20, 6), (30, 8), (22, 14)], (170, 168, 178), "r")
    return c


# ---------------- 大地圖圖示（約 40×40）----------------
def icon_town(b):
    c = Canvas(44, 40)
    P = BIOMES[b]
    c.rect(2, 30, 41, 36, (150, 150, 158), "w")
    for x, hgt in ((4, 16), (16, 22), (28, 16)):
        c.rect(x, 30 - hgt, x + 10, 30, (232, 220, 192), "w")
        c.poly([(x - 3, 30 - hgt), (x + 5, 30 - hgt - 9), (x + 13, 30 - hgt)], hexc(P["roof"]), "r")
        c.rect(x + 4, 24, x + 6, 30, (90, 60, 40), "d")
    return c


def icon_sect(b):
    c = Canvas(40, 46)
    P = BIOMES[b]
    c.rect(6, 40, 33, 44, (150, 150, 158), "s")
    y = 40
    for w in (13, 10, 7):
        c.rect(20 - w + 3, y - 10, 20 + w - 4, y, (168, 58, 42), "p")
        c.poly([(20 - w - 3, y - 10), (20, y - 19), (20 + w + 3, y - 10)], hexc(P["roof"]), "r")
        c.rect(20 - w - 3, y - 11, 20 + w + 3, y - 10, (255, 211, 90), "g")
        y -= 12
    return c


def icon_cave(b):
    c = Canvas(40, 34)
    c.poly([(2, 32), (6, 14), (20, 3), (34, 14), (38, 32)], (108, 102, 112), "r")
    c.poly([(11, 32), (12, 20), (20, 13), (28, 20), (29, 32)], (28, 22, 38), "h")
    c.ellipse(20, 26, 5, 3, (170, 100, 240), "g")
    return c


def icon_battle(b):
    c = Canvas(40, 42)
    for x, col in ((8, "#c0392b"), (20, "#3a5ac0"), (30, "#c0392b")):
        c.rect(x, 10, x + 1, 38, (90, 60, 40), "p")
        c.poly([(x + 1, 11), (x + 10, 15), (x + 1, 20)], hexc(col), "f")
    c.line(6, 34, 34, 22, (220, 230, 240), "s", 2)
    c.line(34, 34, 6, 22, (220, 230, 240), "s", 2)
    return c


def icon_camp(b):
    c = Canvas(44, 38)
    for x in (2, 22):
        c.poly([(x, 34), (x + 10, 12), (x + 20, 34)], (200, 180, 140), "t")
        c.poly([(x + 6, 34), (x + 10, 22), (x + 14, 34)], (60, 40, 30), "d")
    c.rect(20, 4, 21, 14, (90, 60, 40), "p")
    c.rect(21, 4, 28, 8, (192, 57, 43), "f")
    return c


def icon_port(b):
    c = Canvas(44, 38)
    c.rect(0, 18, 43, 24, (168, 122, 72), "w")
    for x in (4, 20, 38):
        c.rect(x, 24, x + 2, 34, (90, 60, 40), "w")
    c.poly([(8, 28), (36, 28), (30, 36), (14, 36)], (122, 74, 42), "b")
    c.rect(21, 6, 22, 28, (90, 60, 40), "m")
    c.poly([(22, 6), (34, 24), (22, 24)], (240, 230, 208), "s")
    return c


def icon_ruin(b):
    c = Canvas(40, 40)
    for x, h in ((4, 22), (16, 30), (28, 16)):
        c.rect(x, 36 - h, x + 6, 36, (150, 148, 158), "s")
        c.rect(x - 1, 36 - h - 2, x + 7, 36 - h, (180, 178, 188), "s")
    c.ellipse(20, 8, 4, 4, (170, 120, 240), "g")
    return c


def icon_portal(b):
    c = Canvas(40, 40)
    for r, col in ((16, "#3a5aa0"), (13, "#5a8ad8"), (9, "#8ac8ff"), (5, "#ffffff")):
        c.ellipse(20, 22, r, r * .8, hexc(col), "r")
    return c


# ---------------- 藥園／洞府 ----------------
def furnace(b):
    """煉丹爐：銅色三足鼎，底下有爐火。"""
    c = Canvas(40, 48)
    bronze, dark = hexc("#b9834a"), hexc("#7a4a24")
    c.ellipse(20, 44, 15, 3, (60, 40, 30), "s")
    for x in (8, 19, 30):
        c.rect(x, 34, x + 3, 44, dark, "leg")
    c.ellipse(20, 26, 15, 13, bronze, "body")
    c.ellipse(20, 14, 12, 4, dark, "rim")
    c.ellipse(20, 14, 9, 2, hexc("#2a1a10"), "in")
    c.rect(5, 24, 34, 26, hexc("#d9a860"), "band")
    c.rect(2, 16, 6, 22, dark, "ear")
    c.rect(33, 16, 37, 22, dark, "ear")
    c.poly([(20, 42), (26, 46), (14, 46)], hexc("#ff8a2a"), "fire")
    c.put(20, 8, hexc("#ffffff"), "smoke")
    c.put(22, 5, hexc("#dddddd"), "smoke")
    c.put(19, 2, hexc("#cccccc"), "smoke")
    return c


def plot(b, stage):
    """藥田：0 空地 1 幼苗 2 生長 3 成熟。"""
    P = BIOMES[b]
    c = Canvas(32, 26)
    soil, dk = hexc("#6a4a2a"), hexc("#4a3018")
    c.rect(1, 6, 30, 24, soil, "soil")
    for y in (9, 14, 19):
        c.rect(2, y, 29, y + 1, dk, "row")
    c.rect(1, 5, 30, 5, lighten(soil, .2), "soil")
    leaf = hexc(P["leaf"])
    if stage >= 1:
        for x in (7, 16, 25):
            c.rect(x, 11, x + 1, 14, leaf, "l")
    if stage >= 2:
        for x in (7, 16, 25):
            c.ellipse(x, 9, 4, 3, leaf, "l")
            c.rect(x, 12, x + 1, 17, darken(leaf, .3), "stem")
    if stage >= 3:
        for x, col in ((7, "#ff6a8a"), (16, "#ffd35a"), (25, "#8ad8ff")):
            c.rect(x - 1, 4, x + 1, 6, hexc(col), "fruit")
            c.put(x, 3, (255, 255, 255), "fruit")
    return c


def scarecrow(b):
    c = Canvas(30, 50)
    c.rect(14, 12, 16, 48, hexc("#7a4a2a"), "w")
    c.rect(3, 18, 26, 21, hexc("#8a5a2b"), "w")
    c.rect(8, 21, 21, 32, hexc("#b98a58"), "cloth")
    c.ellipse(15, 9, 6, 6, hexc("#e8d090"), "head")
    c.ellipse(15, 3, 9, 3, hexc("#8a5a2b"), "hat")
    c.rect(12, 8, 13, 9, (40, 30, 20), "e")
    c.rect(17, 8, 18, 9, (40, 30, 20), "e")
    return c


def icon_garden(b):
    P = BIOMES[b]
    c = Canvas(44, 38)
    c.rect(2, 20, 41, 34, hexc("#6a4a2a"), "soil")
    for x in range(3, 41, 6):
        c.rect(x, 12, x + 3, 22, hexc(P["leaf"]), "l")
        c.ellipse(x + 1.5, 12, 3, 3, lighten(hexc(P["leaf"]), .3), "l")
    for x in range(2, 42, 5):
        c.rect(x, 24, x, 34, hexc("#a87a48"), "fence")
    c.rect(2, 26, 41, 27, hexc("#a87a48"), "fence")
    c.rect(2, 31, 41, 32, hexc("#a87a48"), "fence")
    return c


def icon_hut(b):
    P = BIOMES[b]
    c = Canvas(40, 38)
    c.rect(6, 18, 33, 34, hexc("#d8c8a0"), "w")
    c.poly([(2, 20), (20, 4), (37, 20)], hexc(P["roof"]), "r")
    c.rect(16, 24, 23, 34, hexc("#5a3a22"), "d")
    c.rect(26, 22, 31, 27, hexc("#8fc9e8"), "win")
    c.rect(28, 2, 31, 8, (140, 140, 140), "ch")
    return c


def bed(b):
    c = Canvas(48, 34)
    c.rect(2, 12, 45, 30, hexc("#7a4a2a"), "frame")
    c.rect(2, 8, 45, 13, hexc("#5a3018"), "head")
    c.rect(5, 15, 42, 28, hexc("#e8dcc0"), "sheet")
    c.rect(5, 15, 42, 19, hexc("#5a8ac0"), "blanket")
    c.rect(6, 13, 16, 17, hexc("#f4f0e6"), "pillow")
    c.rect(2, 29, 5, 33, hexc("#5a3018"), "leg")
    c.rect(42, 29, 45, 33, hexc("#5a3018"), "leg")
    return c


def board(b):
    """布告欄：木框、屋簷、貼滿告示。"""
    c = Canvas(52, 60)
    wood, dk = hexc("#8a5a2b"), hexc("#5a3a1a")
    c.rect(4, 14, 6, 56, dk, "post")
    c.rect(45, 14, 47, 56, dk, "post")
    c.poly([(0, 14), (26, 2), (51, 14)], hexc(BIOMES[b]["roof"]), "roof")
    c.rect(0, 13, 51, 15, dk, "roof")
    c.rect(6, 16, 45, 42, wood, "board")
    c.rect(6, 16, 45, 17, lighten(wood, .25), "board")
    for x, y, w, h, col in ((9, 19, 10, 13, "#f4ecd0"), (21, 19, 10, 9, "#fff2a8"), (33, 19, 10, 14, "#f4ecd0"), (11, 34, 9, 7, "#ffd0c0"), (24, 30, 10, 10, "#f4ecd0"), (36, 35, 7, 6, "#c8e8ff")):
        c.rect(x, y, x + w - 1, y + h - 1, hexc(col), "note")
        for ly in range(y + 2, y + h - 1, 3):
            c.rect(x + 1, ly, x + w - 2, ly, (150, 130, 110), "txt")
        c.put(x + w // 2, y, hexc("#c0392b"), "pin")
    c.rect(20, 34, 22, 36, hexc("#c0392b"), "seal")
    return c


def pharmacy(b):
    """丹藥鋪：紅簷小店、櫃檯、藥罐、丹字招牌。"""
    P = BIOMES[b]
    c = Canvas(76, 66)
    c.rect(6, 26, 69, 62, hexc("#e8dcc0"), "wall")
    c.rect(6, 26, 8, 62, hexc("#7a4a2a"), "beam"); c.rect(67, 26, 69, 62, hexc("#7a4a2a"), "beam")
    c.poly([(0, 28), (38, 6), (75, 28)], hexc(P["roof"]), "roof")
    c.poly([(8, 28), (38, 12), (67, 28)], lighten(hexc(P["roof"]), .12), "roof")
    c.rect(2, 26, 73, 29, darken(hexc(P["roof"]), .3), "roof")
    for i in range(7):
        c.rect(8 + i * 9, 30, 15 + i * 9, 38, hexc("#c0392b") if i % 2 == 0 else hexc("#f0e6d0"), "awn")
    c.rect(10, 46, 65, 62, hexc("#8a5a2b"), "counter")
    c.rect(10, 46, 65, 49, hexc("#b98a58"), "counter")
    for x, col in ((16, "#e8503a"), (26, "#4aa860"), (36, "#f0c040"), (46, "#5a8ac0"), (56, "#c060d0")):
        c.rect(x, 40, x + 6, 46, hexc(col), "jar"); c.rect(x + 1, 38, x + 5, 40, hexc("#5a3a22"), "jar")
    c.ellipse(60, 20, 7, 7, hexc("#fff4c0"), "sign"); c.ellipse(60, 20, 5, 5, hexc("#c0392b"), "sign")
    c.ellipse(60, 18, 2, 2, hexc("#fff4c0"), "sign"); c.ellipse(60, 22, 2, 2, hexc("#3a2a1a"), "sign")
    c.rect(59, 27, 61, 30, hexc("#5a3a22"), "sign")
    return c


def thunder_pillar(b):
    """雷柱：太虛域的標誌物，石柱頂端纏繞雷光。"""
    c = Canvas(18, 44)
    c.rect(4, 14, 13, 42, (112, 118, 140), "s")
    c.rect(4, 14, 6, 42, (146, 152, 176), "s")
    c.rect(2, 38, 15, 43, (92, 98, 120), "s")
    c.rect(2, 10, 15, 15, (126, 132, 156), "s")
    for y in range(18, 36, 6):
        c.rect(4, y, 13, y, (82, 88, 112), "t")
    bolt = (150, 220, 255)
    c.line(9, 0, 6, 6, bolt, "g", 1)
    c.line(6, 6, 11, 8, bolt, "g", 1)
    c.line(11, 8, 8, 12, (255, 255, 255), "g", 1)
    return c


def ruin_arch(b):
    """殘破石拱：古戰場與遺跡的點綴。"""
    c = Canvas(34, 30)
    c.rect(2, 8, 8, 29, (122, 126, 148), "s")
    c.rect(25, 14, 31, 29, (122, 126, 148), "s")
    c.rect(2, 6, 18, 11, (140, 144, 168), "s")
    c.poly([(18, 6), (26, 10), (24, 14), (18, 11)], (140, 144, 168), "s")
    c.rect(4, 12, 5, 28, (160, 164, 188), "s")
    c.put(21, 18, (100, 104, 126), "t")
    c.put(22, 21, (100, 104, 126), "t")
    return c
