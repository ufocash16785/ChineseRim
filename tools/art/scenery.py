"""場景素材：建築、植物、傳送陣、地面／平台貼圖、特效。以生態區（biome）換色。"""
import math

from PIL import Image

from .canvas import Canvas, darken, hexc, lighten, mix

BIOMES = {
    # 地面草色/泥土、葉色、屋瓦、天空(上,下)
    "tiannan": dict(grass="#6fbf5a", dirt="#7a5a3a", leaf="#3f9a4a", leaf2="#2f7a3a", roof="#8a3a2a", sky=("#274b6e", "#8fc1d8")),
    "mulan": dict(grass="#c9b24a", dirt="#8a6a3a", leaf="#a8a03a", leaf2="#7a7a2a", roof="#a0522d", sky=("#3a6a9a", "#e6d9a0")),
    "luanxinghai": dict(grass="#e6d29a", dirt="#b89a6a", leaf="#3fae9a", leaf2="#2a7f78", roof="#2f6f8f", sky=("#1e4d7a", "#8fdcd8")),
    "dajin": dict(grass="#a88a4a", dirt="#5f4a3a", leaf="#d0702a", leaf2="#a04a1a", roof="#4a4a5a", sky=("#3a3a5a", "#c8a890")),
    "taixu": dict(grass="#6a7aa8", dirt="#2e3454", leaf="#6ac0d0", leaf2="#3a7a9a", roof="#243a6a", sky=("#080c28", "#5a6aa8")),
    "tianyuan": dict(grass="#9a7ad0", dirt="#4a3a6a", leaf="#7ad0d8", leaf2="#4a9ab8", roof="#5a3a8a", sky=("#231a4a", "#a88ad8")),
}
REGION_BIOME = {"tiannan": "tiannan", "mulan": "mulan", "luanxinghai": "luanxinghai", "dajin": "dajin", "tianyuan": "tianyuan", "taixu": "taixu"}


def _c(h):
    return hexc(h)


def house(b, variant=0):
    P = BIOMES[b]
    c = Canvas(56, 52)
    wall, beam = _c("#e8dcc0"), _c("#7a4a2a")
    c.rect(6, 22, 49, 47, wall, "wall")
    for x in (6, 27, 48):
        c.rect(x, 22, x + 1, 47, beam, "beam")
    c.rect(6, 34, 49, 35, beam, "beam")
    c.rect(22, 34, 33, 47, _c("#4a2a1a"), "door")
    c.rect(24, 36, 31, 47, _c("#6a3a22"), "door")
    c.put(30, 41, _c("#ffd35a"), "door")
    c.rect(10, 26, 18, 32, _c("#8fc9e8") if variant == 0 else _c("#ffe6a0"), "win")
    c.line(14, 26, 14, 32, beam, "beam")
    c.rect(38, 26, 46, 32, _c("#8fc9e8") if variant == 0 else _c("#ffe6a0"), "win")
    c.line(42, 26, 42, 32, beam, "beam")
    roof = _c(P["roof"])
    c.poly([(0, 24), (28, 4), (55, 24), (50, 24), (28, 9), (5, 24)], roof, "roof")
    c.poly([(3, 26), (28, 8), (52, 26), (52, 22), (28, 2), (3, 22)], roof, "roof")
    for i in range(5):
        c.line(6 + i * 2, 24 - i * 3, 28, 6 - i // 2 + 1, darken(roof, .25), "roofline")
    c.rect(2, 22, 53, 24, darken(roof, .3), "roof")
    c.rect(40, 4, 44, 12, _c("#8a8a8a"), "chimney")
    if variant == 1:   # 商鋪：招牌旗
        c.rect(50, 14, 51, 42, beam, "beam")
        c.rect(44, 16, 50, 30, _c("#c0392b"), "flag")
        c.rect(46, 19, 48, 27, _c("#ffd35a"), "flag")
    return c


def pagoda(b):
    P = BIOMES[b]
    c = Canvas(64, 92)
    roof, pillar, gold = _c(P["roof"]), _c("#a83a2a"), _c("#ffd35a")
    c.rect(6, 84, 57, 90, _c("#9a9a9a"), "stone")
    c.rect(10, 80, 53, 84, _c("#b0b0b0"), "stone")
    y = 78
    for i, w in enumerate((22, 18, 14)):
        top = y - 22
        c.rect(32 - w + 3, top + 6, 32 + w - 4, y, _c("#e8dcc0"), "wall")
        for x in (32 - w + 4, 32, 32 + w - 5):
            c.rect(x, top + 6, x + 2, y, pillar, "pillar")
        c.rect(32 - w + 8, y - 12, 32 + w - 9, y, _c("#5a2a1a"), "door") if i == 0 else c.rect(28, top + 10, 36, top + 17, _c("#8fc9e8"), "win")
        c.poly([(32 - w - 6, top + 8), (32, top - 6), (32 + w + 6, top + 8), (32 + w, top + 10), (32, top - 1), (32 - w, top + 10)], roof, "roof")
        c.rect(32 - w - 7, top + 8, 32 + w + 7, top + 10, gold, "gold")
        y = top + 2
    c.rect(31, 2, 32, 22, gold, "gold")
    c.ellipse(31.5, 3, 2, 2, _c("#ff7a4a"), "gold")
    return c


def sect_gate(b):
    P = BIOMES[b]
    c = Canvas(72, 64)
    pillar, roof, gold = _c("#a83a2a"), _c(P["roof"]), _c("#ffd35a")
    for x in (10, 58):
        c.rect(x, 18, x + 4, 62, pillar, "pillar")
        c.rect(x - 2, 58, x + 6, 62, _c("#8a8a8a"), "stone")
    c.rect(6, 16, 65, 22, pillar, "beam")
    c.rect(8, 24, 63, 27, pillar, "beam")
    c.poly([(0, 18), (36, 2), (71, 18), (68, 18), (36, 6), (3, 18)], roof, "roof")
    c.rect(0, 16, 71, 18, gold, "gold")
    c.rect(24, 28, 47, 40, _c("#2a1a1a"), "plaque")
    c.rect(26, 30, 45, 38, gold, "plaque")
    c.rect(28, 32, 43, 36, _c("#2a1a1a"), "plaque")
    return c


def cave(b):
    c = Canvas(64, 52)
    rock, dark = _c("#6a6470"), _c("#2a2430")
    c.poly([(0, 51), (4, 24), (14, 8), (32, 2), (50, 8), (60, 24), (63, 51)], rock, "rock")
    c.poly([(12, 51), (14, 28), (24, 16), (32, 14), (42, 16), (50, 28), (52, 51)], dark, "hole")
    for i in range(6):
        c.ellipse(32, 44 - i * 4, 10 - i, 3 + i * .3, mix(_c("#3a2a5a"), _c("#a46af0"), i / 6), "glow")
    for x, y in ((18, 22), (46, 22), (32, 12)):
        c.rect(x, y, x + 1, y + 3, _c("#c8a0ff"), "rune")
    return c


def tree_round(b):
    P = BIOMES[b]
    c = Canvas(44, 60)
    c.rect(19, 30, 24, 58, _c("#6a4a2a"), "trunk")
    c.rect(22, 34, 24, 58, _c("#4a3220"), "trunk")
    for cx, cy, r, col in ((22, 16, 14, P["leaf"]), (11, 24, 9, P["leaf2"]), (33, 24, 9, P["leaf2"]), (22, 26, 11, P["leaf"])):
        c.ellipse(cx, cy, r, r * .85, _c(col), "leaf")
    for x, y in ((16, 10), (26, 8), (30, 20), (12, 22)):
        c.rect(x, y, x + 2, y + 1, lighten(_c(P["leaf"]), .3), "leaf")
    return c


def pine(b):
    P = BIOMES[b]
    c = Canvas(36, 66)
    c.rect(16, 46, 19, 64, _c("#5a3a22"), "trunk")
    for i, (w, y) in enumerate(((16, 42), (13, 30), (10, 19), (7, 9))):
        c.poly([(18 - w, y + 8), (18, y - 10), (18 + w, y + 8)], _c(P["leaf2"] if i % 2 else P["leaf"]), "leaf")
    return c


def bamboo(b):
    c = Canvas(30, 66)
    for i, x in enumerate((5, 12, 20, 25)):
        h = 62 - (i % 2) * 8
        col = _c("#5fa64a") if i % 2 == 0 else _c("#4a8f3a")
        c.rect(x, 64 - h, x + 2, 64, col, "b")
        for y in range(64 - h + 8, 64, 12):
            c.rect(x - 1, y, x + 3, y, darken(col, .3), "node")
        c.poly([(x + 2, 64 - h + 12), (x + 10, 64 - h + 8), (x + 4, 64 - h + 15)], _c("#7fd05a"), "leaf")
        c.poly([(x, 64 - h + 22), (x - 8, 64 - h + 20), (x - 2, 64 - h + 26)], _c("#7fd05a"), "leaf")
    return c


def rock(b):
    c = Canvas(30, 18)
    c.poly([(1, 17), (4, 8), (12, 2), (22, 4), (28, 12), (29, 17)], _c("#8a8a90"), "rock")
    c.poly([(8, 8), (12, 4), (18, 5), (14, 9)], _c("#b0b0b8"), "rock")
    return c


def lantern(b):
    c = Canvas(14, 36)
    c.rect(6, 12, 7, 35, _c("#5a3a22"), "pole")
    c.ellipse(6.5, 8, 5, 6, _c("#e8503a"), "lamp")
    c.rect(3, 2, 10, 3, _c("#ffd35a"), "gold")
    c.rect(3, 13, 10, 14, _c("#ffd35a"), "gold")
    c.ellipse(6.5, 8, 2, 3, _c("#ffe9a0"), "glow")
    return c


def portal_frame(t):
    c = Canvas(64, 32)
    for r, col in ((28, "#3a5aa0"), (24, "#5a8ad8"), (20, "#8ac8ff"), (14, "#d8f0ff")):
        c.ellipse(32, 16, r, r * .42, _c(col), "ring")
    c.ellipse(32, 16, 10, 4, _c("#ffffff"), "ring")
    for i in range(8):
        a = i * math.pi / 4 + t * .4
        x, y = 32 + math.cos(a) * 22, 16 + math.sin(a) * 9
        c.rect(x - 1, y - 1, x + 1, y + 1, _c("#ffffff"), "rune")
    return c


def ground_tile(b, variant=0):
    P = BIOMES[b]
    c = Canvas(32, 32)
    c.rect(0, 6, 31, 31, _c(P["dirt"]), "dirt")
    for x, y in ((4, 14), (18, 20), (10, 26), (26, 12), (22, 28)):
        c.rect(x, y, x + 3, y + 1, darken(_c(P["dirt"]), .3), "dirt")
        c.rect(x + 1, y - 1, x + 2, y - 1, lighten(_c(P["dirt"]), .2), "dirt")
    c.rect(0, 0, 31, 7, _c(P["grass"]), "grass")
    for x in range(0, 32, 4):
        h = 2 + ((x * 7 + variant * 3) % 4)
        c.rect(x, 7, x + 2, 7 + h, _c(P["grass"]), "grass")
        c.put(x + 1, 0, lighten(_c(P["grass"]), .3), "grass")
    return c


def platform(b):
    P = BIOMES[b]
    c = Canvas(48, 16)
    c.rect(0, 4, 47, 13, _c("#8a7a6a"), "stone")
    c.rect(2, 12, 45, 15, _c("#6a5a4a"), "stone")
    c.rect(0, 0, 47, 5, _c(P["grass"]), "grass")
    for x in range(1, 47, 5):
        c.rect(x, 5, x + 1, 7, _c(P["grass"]), "grass")
    for x in (10, 26, 38):
        c.rect(x, 8, x + 2, 9, _c("#a89a8a"), "stone")
    return c


# ---- 特效 ----
def slash_frame(t):
    """新月形劍氣：外弧白、中段青、內側藍；三幀逐漸變大變薄。"""
    c = Canvas(72, 72)
    R = [24, 29, 33][t]
    inner = [9, 10, 8][t]             # 月牙最厚處（像素）
    for y in range(72):
        for x in range(72):
            dx, dy = x - 26, y - 36
            d_out = math.hypot(dx, dy)
            d_in = math.hypot(dx + inner, dy)
            if d_out <= R and d_in > R:
                edge = d_in - R
                col = (255, 255, 255) if edge < 2.5 else (170, 232, 255) if edge < 5.5 else (90, 170, 240)
                c.put(x, y, col, "fx")
    return c


def orb_frame(t, color, accent):
    c = Canvas(20, 20)
    r = 5 + t
    c.ellipse(10, 10, r + 2, r + 2, mix(color, (0, 0, 0), .35), "g")
    c.ellipse(10, 10, r, r, color, "g")
    c.ellipse(10, 10, r - 2, r - 2, accent, "g")
    c.put(9, 8, (255, 255, 255), "g")
    for k in range(3):
        c.put(2 - k * 2 + t, 10 + (k % 2) * 2 - 1, mix(color, (255, 255, 255), .2), "g")
    return c


def spark_frame(t):
    c = Canvas(24, 24)
    r = 3 + t * 3
    for a in range(0, 360, 45):
        x = 12 + math.cos(math.radians(a)) * r
        y = 12 + math.sin(math.radians(a)) * r
        c.rect(x, y, x + 1, y + 1, (255, 250, 200), "fx")
    return c
