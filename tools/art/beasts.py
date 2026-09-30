"""七種妖獸（面朝右），依五行／變異屬性換色。每種 4 幀走路動畫。"""
import math

from .canvas import Canvas, darken, hexc, lighten

FW, FH = 56, 44

ELEMENT_PALETTES = {   # main, dark, light, accent(眼睛／紋路)
    "金": ("#b9b3a0", "#6e6a5c", "#ece6c9", "#ffd84a"),
    "木": ("#5fa05a", "#2f5f36", "#a8dc8a", "#e6ff6a"),
    "水": ("#4a86c8", "#24467a", "#9ad0f4", "#7af0ff"),
    "火": ("#d8552f", "#7a2415", "#ffb066", "#fff07a"),
    "土": ("#a67c4a", "#5b3f22", "#d9b878", "#ffcf5a"),
    "雷": ("#8a6ad0", "#3f2a7a", "#d2c4ff", "#fff35a"),
    "冰": ("#8fd6e8", "#3f7f9a", "#e8fbff", "#ffffff"),
    "風": ("#9ed8b8", "#4a8a70", "#e4fff2", "#c8ff9a"),
}
ELEMENTS = list(ELEMENT_PALETTES)


def _pal(el):
    m, d, l, a = (hexc(x) for x in ELEMENT_PALETTES[el])
    return m, d, l, a


def wolf(el, t):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    bob = [0, 1, 0, 1][t]
    lift = [(0, 2), (1, 0), (2, 0), (0, 1)][t]        # 四腿抬起量
    tail = [0, 2, 3, 2][t]
    c.line(12, 26 + bob, 4, 18 - tail + bob, m, "b", 3)
    c.line(4, 18 - tail + bob, 2, 15 - tail + bob, l, "l", 2)
    for i, x in enumerate((17, 22, 31, 36)):
        up = 3 if (i % 2 == 0) == (lift[0] > 0 or lift[1] > 0) and t in (0, 2) else 0
        c.rect(x - 1, 32 - up + bob, x + 2, 41 - up, d if i in (0, 2) else m, "leg")
        c.rect(x - 1, 39 - up, x + 3, 41 - up, l, "claw")
    c.ellipse(26, 27 + bob, 14, 8, m, "b")
    c.ellipse(26, 31 + bob, 11, 4, l, "l")
    c.ellipse(41, 20 + bob, 7, 6, m, "b")
    c.poly([(44, 20 + bob), (54, 24 + bob), (44, 26 + bob)], m, "b")
    c.rect(52, 23 + bob, 54, 24 + bob, d, "nose")
    c.poly([(37, 15 + bob), (36, 6 + bob), (41, 13 + bob)], d, "ear")
    c.poly([(42, 14 + bob), (44, 6 + bob), (47, 15 + bob)], d, "ear")
    c.rect(43, 24 + bob, 48, 25 + bob, l, "fang")
    c.rect(43, 18 + bob, 45, 19 + bob, a, "eye")
    return c


def spider(el, t):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    bob = [0, 1, 0, 1][t]
    for i in range(4):
        ph = (t + i) % 4
        dy = -2 if ph == 0 else 0
        for side, x0 in ((1, 30), (-1, 24)):
            pass
        x0 = 25 + i * 3
        c.line(x0, 26 + bob, x0 + 8 + i * 2, 20 + dy + bob, d, "leg")
        c.line(x0 + 8 + i * 2, 20 + dy + bob, x0 + 11 + i * 3, 40, d, "leg")
        x1 = 22 - i * 2
        c.line(x1, 28 + bob, x1 - 7 - i, 20 - dy + bob, d, "leg")
        c.line(x1 - 7 - i, 20 - dy + bob, x1 - 11 - i * 2, 40, d, "leg")
    c.ellipse(20, 26 + bob, 11, 9, m, "b")
    c.ellipse(19, 24 + bob, 6, 4, l, "l")
    for x in (14, 20, 26):
        c.line(x, 21 + bob, x + 1, 33 + bob, a, "mark")
    c.ellipse(34, 28 + bob, 7, 6, d, "b")
    for x, y in ((36, 26), (39, 27), (37, 29), (40, 30)):
        c.rect(x, y + bob, x + 1, y + 1 + bob, a, "eye")
    c.rect(38, 33 + bob, 40, 35 + bob, l, "fang")
    return c


def bear(el, t):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    bob = [0, 1, 0, 1][t]
    for i, x in enumerate((15, 24, 33, 41)):
        up = 2 if (i + t) % 2 == 0 else 0
        c.rect(x - 2, 30 - up, x + 3, 42 - up, d if i % 2 == 0 else m, "leg")
        c.rect(x - 2, 40 - up, x + 3, 42 - up, l, "claw")
    c.ellipse(26, 26 + bob, 17, 12, m, "b")
    c.ellipse(26, 31 + bob, 12, 6, l, "l")
    c.ellipse(43, 20 + bob, 8, 8, m, "b")
    c.ellipse(40, 12 + bob, 3, 3, d, "ear")
    c.ellipse(47, 12 + bob, 3, 3, d, "ear")
    c.ellipse(49, 23 + bob, 4, 3, l, "l")
    c.rect(50, 21 + bob, 52, 22 + bob, d, "nose")
    c.rect(43, 18 + bob, 45, 19 + bob, a, "eye")
    c.line(23, 16 + bob, 29, 16 + bob, a, "mark")
    return c


def snake(el, t, big=False):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    r = 4 if big else 3
    n = 12 if big else 10
    ph = t * math.pi / 2
    pts = []
    for i in range(n):
        x = 4 + i * (3.6 if big else 3.4)
        y = 32 + 5 * math.sin(i * .9 - ph) - (i * .3 if big else 0)
        pts.append((x, y))
    for i, (x, y) in enumerate(pts):
        c.ellipse(x, y, r, r, m if i % 2 == 0 else d, "b")
        if big and i % 3 == 1:
            c.rect(x - 1, y - r, x + 1, y - r + 1, l, "l")
    for x, y in pts[2:-1]:
        c.put(x, y + r - 1, l, "l")
    hx, hy = pts[-1]
    c.ellipse(hx + 3, hy - 3, r + 3, r + 1, m, "b")
    c.rect(hx + 5, hy - 5, hx + 7, hy - 4, a, "eye")
    c.rect(hx + 8 + (t % 2), hy - 2, hx + 11 + (t % 2), hy - 2, hexc("#e83a4a"), "tongue")
    if big:
        c.poly([(hx, hy - 6), (hx - 2, hy - 13), (hx + 3, hy - 7)], l, "horn")
        c.poly([(hx + 4, hy - 7), (hx + 6, hy - 14), (hx + 8, hy - 6)], l, "horn")
    return c


def ape(el, t):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    bob = [0, 1, 0, 1][t]
    sw = [3, 0, -3, 0][t]
    c.line(14, 30, 6, 22 + (t % 2) * 2, d, "tail", 2)
    c.rect(19, 32 + bob, 23, 42 - (1 if t == 1 else 0), d, "leg")
    c.rect(27, 32 + bob, 31, 42 - (1 if t == 3 else 0), m, "leg")
    c.ellipse(25, 27 + bob, 9, 10, m, "b")
    c.ellipse(26, 29 + bob, 5, 6, l, "l")
    c.line(19, 22 + bob, 15 + sw, 36, d, "arm", 3)
    c.line(31, 22 + bob, 36 - sw, 36, m, "arm", 3)
    c.rect(13 + sw, 36, 17 + sw, 39, l, "claw")
    c.rect(34 - sw, 36, 38 - sw, 39, l, "claw")
    c.ellipse(26, 13 + bob, 8, 7, m, "b")
    c.ellipse(29, 15 + bob, 5, 4, l, "l")
    c.rect(28, 17 + bob, 33, 18 + bob, a, "mark")
    c.rect(24, 11 + bob, 26, 12 + bob, a, "eye")
    c.rect(29, 11 + bob, 31, 12 + bob, a, "eye")
    c.ellipse(20, 8 + bob, 2, 2, d, "ear")
    c.ellipse(32, 8 + bob, 2, 2, d, "ear")
    return c


def bat(el, t):
    m, d, l, a = _pal(el)
    c = Canvas(FW, FH)
    flap = [-9, -3, 6, -3][t]
    bob = [0, 1, 2, 1][t]
    for side in (-1, 1):
        x0 = 28 + side * 4
        tipx = 28 + side * 22
        tipy = 20 + flap + bob
        c.poly([(x0, 20 + bob), (tipx, tipy), (28 + side * 16, 26 + flap // 2 + bob), (28 + side * 10, 28 + bob), (x0, 26 + bob)], d, "wing")
        c.line(x0, 20 + bob, tipx, tipy, m, "bone")
        c.line(x0, 20 + bob, 28 + side * 16, 26 + flap // 2 + bob, m, "bone")
    c.ellipse(28, 24 + bob, 5, 7, m, "b")
    c.ellipse(28, 26 + bob, 3, 4, l, "l")
    c.ellipse(28, 15 + bob, 5, 5, m, "b")
    c.poly([(24, 12 + bob), (23, 5 + bob), (27, 11 + bob)], d, "ear")
    c.poly([(29, 11 + bob), (33, 5 + bob), (32, 12 + bob)], d, "ear")
    c.rect(26, 14 + bob, 27, 15 + bob, a, "eye")
    c.rect(30, 14 + bob, 31, 15 + bob, a, "eye")
    c.rect(27, 18 + bob, 27, 19 + bob, (255, 255, 255), "fang")
    c.rect(30, 18 + bob, 30, 19 + bob, (255, 255, 255), "fang")
    return c


BEASTS = {
    "wolf": (wolf, "青狼"), "spider": (spider, "毒蛛"), "bear": (bear, "鐵背熊"),
    "snake": (snake, "赤焰蛇"), "python": (lambda e, t: snake(e, t, True), "碧水蟒"),
    "ape": (ape, "山魈"), "bat": (bat, "血翼蝠"),
}
