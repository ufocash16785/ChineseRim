"""Q 版小人偶（約 3 頭身，仙劍一代比例）。面朝右，左向由前端水平翻轉。"""
from .canvas import Canvas, darken, hexc, lighten, mix

FW, FH = 40, 52
BASE = 49          # 腳底 y

SKIN = hexc("#f6d3b0")
HAIR_DARK = hexc("#2b2233")


class Pal:
    def __init__(self, robe, trim, sash, hair, skin=SKIN, boots="#3a2c3c", beard=None, hairstyle="topknot",
                 accessory=None, sword=True, robe2=None, hat=None):
        self.robe, self.trim, self.sash = hexc(robe), hexc(trim), hexc(sash)
        self.robe2 = hexc(robe2) if robe2 else darken(hexc(robe), .18)
        self.hair, self.skin, self.boots = hexc(hair), skin, hexc(boots)
        self.beard = hexc(beard) if beard else None
        self.hairstyle, self.accessory, self.sword, self.hat = hairstyle, accessory, sword, hat


def _sword(c, x0, y0, x1, y1):
    c.line(x0, y0, x1, y1, hexc("#dff4ff"), "blade", 2)
    dx, dy = (x1 - x0), (y1 - y0)
    n = max(abs(dx), abs(dy)) or 1
    c.put(x0 - dx / n * 1, y0 - dy / n * 1, hexc("#8a5a2b"), "hilt")
    c.put(x0 - dx / n * 2, y0 - dy / n * 2, hexc("#8a5a2b"), "hilt")


def draw_human(p: Pal, pose: dict):
    c = Canvas(FW, FH)
    bob = pose.get("bob", 0)
    lean = pose.get("lean", 0)               # 上身水平位移（受擊後仰為負）
    fly = pose.get("fly", False)
    flutter = pose.get("flutter", 0)         # 衣髮飄動 0/1/2
    cx = 20 + lean
    base = BASE - (3 if fly else 0)

    # ---- 飛劍（腳下）----
    if fly:
        c.line(6, base + 3 + bob, 34, base + 1 + bob, hexc("#cfeeff"), "blade", 2)
        c.rect(32, base + bob, 35, base + 2 + bob, hexc("#8a5a2b"), "hilt")

    # ---- 後髮 / 髮尾 ----
    hy = 16 + bob
    hs = p.hairstyle
    if hs == "ponytail":
        sway = [0, 2, 1][flutter]
        c.ellipse(cx - 9, hy + 2, 3, 3, p.hair, "hair")
        c.line(cx - 10, hy + 3, cx - 15 - sway, hy + 12 + (flutter == 1), p.hair, "hair", 3)
        c.line(cx - 15 - sway, hy + 12, cx - 14 - sway, hy + 16, p.hair, "hair", 2)
    elif hs == "long":
        sway = [0, 1, 2][flutter]
        c.rect(cx - 11, hy, cx - 6, hy + 20, p.hair, "hair")
        c.rect(cx - 12 - sway, hy + 8, cx - 8, hy + 24, p.hair, "hair")
        c.rect(cx + 8, hy + 2, cx + 10, hy + 12, p.hair, "hair")     # 前側髮束
    elif hs == "short":
        c.ellipse(cx - 8, hy + 1, 2, 4, p.hair, "hair")

    # ---- 身體（長袍）----
    top, bot = 24 + bob, 40 + bob
    sway = [0, 1, 2][flutter]
    for y in range(top, bot):
        t = (y - top) / (bot - top)
        w = 5 + int(t * 3.4)
        x0, x1 = cx - w - (sway if t > .6 else 0), cx + w
        c.rect(x0, y, x1, y, p.robe if t < .85 else p.robe2, "robe")
    c.rect(cx - 8 - sway, bot - 2, cx + 8, bot - 1, p.trim, "trim")     # 下擺滾邊
    c.rect(cx - 5, top, cx + 4, top + 1, p.trim, "trim")                # 領口
    c.line(cx - 2, top + 1, cx + 1, top + 5, p.trim, "trim")            # 交領
    c.line(cx + 4, top + 1, cx + 1, top + 5, p.trim, "trim")
    c.rect(cx - 6, top + 8, cx + 7, top + 9, p.sash, "sash")            # 腰帶
    c.rect(cx + 4, top + 9, cx + 6, top + 13 + (flutter == 2), p.sash, "sash")   # 垂帶

    # ---- 腿 / 靴 ----
    if not fly:
        for (lx, ly, front) in ((pose.get("legB", (0, 0)) + (False,)), (pose.get("legF", (0, 0)) + (True,))):
            x = cx - 1 + (3 if front else -4) + lx
            y = bot - 1 + bob + ly
            c.rect(x, y, x + 3, base - 2 + min(0, ly) + 0, p.robe2, "robe")
            c.rect(x - 1, base - 3 + min(0, ly), x + 4, base + min(0, ly), p.boots, "boots")
    else:
        c.rect(cx - 5, base - 3, cx - 2, base, p.boots, "boots")
        c.rect(cx + 2, base - 3, cx + 5, base, p.boots, "boots")

    # ---- 手臂 ----
    def arm(front, ang):
        sx = cx + (6 if front else -7)
        sy = top + 4
        # ang: 0 垂下 1 前伸 2 上舉 3 後擺 4 前下揮
        tips = {0: (sx + (1 if front else -1), sy + 9), 1: (sx + 9, sy + 3), 2: (sx + 5, sy - 8),
                3: (sx - 6, sy + 6), 4: (sx + 8, sy + 8), 5: (sx - 3, sy - 8)}
        tx, ty = tips[ang]
        c.line(sx, sy, tx, ty, p.robe, "robe", 3)
        c.line(sx + 1, sy, tx + 1, ty, p.robe, "robe", 3)
        c.rect(tx - 1, ty - 1, tx + 1, ty + 1, p.trim, "trim")          # 袖口
        c.put(tx + (1 if front else 0), ty + 2, p.skin, "skin")
        return tx, ty

    if not pose.get("armBack") is None:
        arm(False, pose["armBack"])
    # ---- 頭 ----
    hy = 16 + bob
    c.ellipse(cx, hy, 10, 9, p.skin, "skin")
    # 頭髮：頂蓋 + 短瀏海 + 鬢角（保留大片臉）
    c.ellipse(cx, hy - 5, 10, 5, p.hair, "hair")
    c.rect(cx - 10, hy - 5, cx - 8, hy + 3, p.hair, "hair")
    if hs != "long":
        c.rect(cx + 9, hy - 5, cx + 10, hy, p.hair, "hair")
    for i, bx in enumerate(range(cx - 7, cx + 9, 3)):
        c.rect(bx, hy - 3, bx + 1, hy - (0 if i % 2 == 0 else 1), p.hair, "hair")
    # 髮髻 / 髮飾
    if hs == "topknot":
        c.ellipse(cx - 1, hy - 12, 3, 3, p.hair, "hair")
        c.rect(cx - 2, hy - 10, cx, hy - 9, p.trim, "trim")
    elif hs == "long" and p.accessory == "pin":
        c.rect(cx + 4, hy - 11, cx + 5, hy - 6, hexc("#ffd35a"), "trim")
        c.put(cx + 4, hy - 12, hexc("#ff7a9a"), "trim")
        c.rect(cx - 3, hy - 9, cx + 1, hy - 8, hexc("#ff7a9a"), "trim")
    elif hs == "elder":
        c.ellipse(cx - 1, hy - 13, 3, 3, p.hair, "hair")
        c.rect(cx - 10, hy - 3, cx - 8, hy + 6, p.hair, "hair")
    elif hs == "ponytail":
        c.rect(cx - 4, hy - 10, cx - 1, hy - 9, p.trim, "trim")
    if p.hat:
        c.ellipse(cx, hy - 8, 12, 3, hexc(p.hat), "trim")
        c.rect(cx - 6, hy - 13, cx + 5, hy - 8, hexc(p.hat), "trim")
    # 五官
    ey = hy + 1
    if pose.get("hurt"):
        for ex in (cx - 3, cx + 4):
            c.line(ex, ey - 1, ex + 2, ey + 1, HAIR_DARK, "eye")
            c.line(ex, ey + 1, ex + 2, ey - 1, HAIR_DARK, "eye")
    elif pose.get("blink"):
        for ex in (cx - 3, cx + 4):
            c.rect(ex, ey + 2, ex + 2, ey + 2, HAIR_DARK, "eye")
    else:
        for ex in (cx - 3, cx + 4):
            c.rect(ex, ey - 1, ex + 2, ey + 3, HAIR_DARK, "eye")
            c.rect(ex, ey - 1, ex + 1, ey, (255, 255, 255), "eye")
    c.put(cx - 5, ey + 4, hexc("#f2a0a0"), "skin")
    c.put(cx + 7, ey + 4, hexc("#f2a0a0"), "skin")
    c.rect(cx + 1, ey + 6, cx + 3, ey + 6, hexc("#b0605a"), "eye")
    if p.beard:
        c.poly([(cx - 5, ey + 5), (cx + 8, ey + 5), (cx + 6, ey + 14), (cx, ey + 17), (cx - 4, ey + 12)], p.beard, "beard")
        c.rect(cx + 1, ey + 6, cx + 3, ey + 6, hexc("#b0605a"), "eye")

    # ---- 前臂 + 劍 ----
    fa = pose.get("armFront", 0)
    tip = arm(True, fa)
    sw = pose.get("sword")
    if p.sword and sw:
        x, y = tip
        if sw == "up":
            _sword(c, x, y, x - 5, y - 17)
        elif sw == "fwd":
            _sword(c, x, y, x + 17, y - 1)
        elif sw == "down":
            _sword(c, x, y, x + 13, y + 12)
        elif sw == "hold":
            _sword(c, x, y, x + 2, y - 15)
    elif p.sword and not fly:
        # 背劍
        c.line(cx - 6, top + 1, cx - 11, top - 4 + bob * 0, hexc("#dff4ff"), "blade", 1)
        c.rect(cx - 8, top + 3, cx - 6, top + 4, hexc("#8a5a2b"), "hilt")
    return c


# ---- 動畫定義 ----
def frames(p: Pal, fly=True):
    idle = [dict(bob=0, armFront=0, armBack=0, flutter=0),
            dict(bob=1, armFront=0, armBack=0, flutter=1),
            dict(bob=0, armFront=0, armBack=0, flutter=0, blink=True),
            dict(bob=1, armFront=0, armBack=0, flutter=2)]
    walk = [dict(bob=0, legF=(3, 0), legB=(-3, 0), armFront=3, armBack=1, flutter=1),
            dict(bob=1, legF=(0, -1), legB=(0, 0), armFront=0, armBack=0, flutter=2),
            dict(bob=0, legF=(-3, 0), legB=(3, 0), armFront=1, armBack=3, flutter=1),
            dict(bob=1, legF=(0, 0), legB=(0, -1), armFront=0, armBack=0, flutter=0)]
    jump = [dict(bob=-2, legF=(2, -3), legB=(-2, -2), armFront=2, armBack=2, flutter=2)]
    atk = [dict(bob=0, armFront=5, armBack=1, sword="up", lean=-1, flutter=1),
           dict(bob=0, armFront=1, armBack=3, sword="fwd", lean=1, flutter=2),
           dict(bob=0, armFront=4, armBack=3, sword="down", lean=2, flutter=1)]
    hurt = [dict(bob=0, armFront=3, armBack=3, lean=-3, hurt=True, flutter=2)]
    out = [("idle", idle), ("walk", walk), ("jump", jump), ("attack", atk), ("hurt", hurt)]
    if fly:
        out.append(("fly", [dict(bob=0, fly=True, armFront=1, armBack=3, flutter=1, lean=1),
                            dict(bob=1, fly=True, armFront=1, armBack=3, flutter=2, lean=1)]))
    return out


# ======================= 正面 / 背面（俯視地圖用）=======================
def draw_human_dir(p: Pal, pose: dict):
    """正面（往下走）或背面（往上走）。pose: view='front'|'back', bob, step(-1,0,1), flutter。"""
    c = Canvas(FW, FH)
    view = pose.get("view", "front")
    bob = pose.get("bob", 0)
    step = pose.get("step", 0)            # 1：右腳在前；-1：左腳在前；0：併腳
    cx = 20
    hy = 16 + bob
    hs = p.hairstyle
    top, bot = 24 + bob, 40 + bob
    back = view == "back"

    # 長髮（背面時蓋在身體上，所以先畫身體）
    # ---- 長袍 ----
    for y in range(top, bot):
        t = (y - top) / (bot - top)
        w = 6 + int(t * 3.2)
        c.rect(cx - w, y, cx + w - 1, y, p.robe if t < .85 else p.robe2, "robe")
    c.rect(cx - 9, bot - 2, cx + 8, bot - 1, p.trim, "trim")
    if not back:
        c.rect(cx - 5, top, cx + 4, top + 1, p.trim, "trim")
        c.line(cx - 3, top + 1, cx, top + 6, p.trim, "trim")
        c.line(cx + 2, top + 1, cx - 1, top + 6, p.trim, "trim")
    else:
        c.rect(cx - 5, top, cx + 4, top + 1, p.trim, "trim")
    c.rect(cx - 7, top + 8, cx + 6, top + 9, p.sash, "sash")
    if back:
        c.rect(cx - 2, top + 9, cx + 1, top + 14, p.sash, "sash")        # 背後蝴蝶結垂帶
    else:
        c.rect(cx + 1, top + 9, cx + 3, top + 13, p.sash, "sash")

    # ---- 腿 / 靴 ----
    for side in (-1, 1):
        lift = -2 if step == side else 0            # 抬腳
        fwd = 1 if step == -side else 0
        x = cx + (side * 3) - 2
        y0 = bot - 1
        c.rect(x, y0, x + 3, BASE - 2 + lift * 0, p.robe2, "robe")
        c.rect(x - 1, BASE - 3 + lift + fwd, x + 4, BASE + lift + fwd, p.boots, "boots")

    # ---- 手臂（垂在兩側，走路時前後擺）----
    for side in (-1, 1):
        sw = step * side * 2
        sx = cx + side * 8
        c.line(sx, top + 4, sx + side, top + 12 + sw, p.robe, "robe", 3)
        c.line(sx + 1, top + 4, sx + side + 1, top + 12 + sw, p.robe, "robe", 3)
        c.rect(sx + side - 1, top + 12 + sw, sx + side + 1, top + 14 + sw, p.trim, "trim")
        c.rect(sx + side - 1, top + 15 + sw, sx + side + 1, top + 16 + sw, p.skin, "skin")

    # ---- 背劍 ----
    if p.sword:
        if back:
            c.line(cx - 8, top + 12, cx + 8, top - 2, hexc("#dff4ff"), "blade", 1)
            c.rect(cx + 7, top - 4, cx + 9, top - 1, hexc("#8a5a2b"), "hilt")
        else:
            c.rect(cx + 6, top - 3, cx + 8, top, hexc("#8a5a2b"), "hilt")

    # ---- 頭 ----
    if back:
        c.ellipse(cx, hy, 10, 9, p.hair, "hair")
        c.rect(cx - 10, hy - 2, cx + 9, hy + 6, p.hair, "hair")
        c.rect(cx - 5, hy + 6, cx + 4, hy + 8, p.skin, "skin")            # 後頸
    else:
        c.ellipse(cx, hy, 10, 9, p.skin, "skin")
        c.ellipse(cx, hy - 5, 10, 5, p.hair, "hair")
        c.rect(cx - 10, hy - 5, cx - 8, hy + 2, p.hair, "hair")
        c.rect(cx + 8, hy - 5, cx + 9, hy + 2, p.hair, "hair")
        for i, bx in enumerate(range(cx - 8, cx + 9, 3)):
            c.rect(bx, hy - 3, bx + 1, hy - (0 if i % 2 == 0 else 1), p.hair, "hair")
    # 髮型細節
    if hs == "topknot":
        c.ellipse(cx, hy - 12, 3, 3, p.hair, "hair")
        c.rect(cx - 1, hy - 10, cx + 1, hy - 9, p.trim, "trim")
    elif hs == "ponytail":
        if back:
            c.line(cx, hy + 3, cx + 1, hy + 18, p.hair, "hair", 4)
            c.rect(cx - 2, hy + 1, cx + 3, hy + 2, p.trim, "trim")
        else:
            c.rect(cx - 3, hy - 10, cx + 2, hy - 9, p.trim, "trim")
    elif hs == "long":
        if back:
            c.rect(cx - 9, hy + 2, cx + 8, hy + 24, p.hair, "hair")
        else:
            c.rect(cx - 11, hy - 2, cx - 8, hy + 20, p.hair, "hair")
            c.rect(cx + 8, hy - 2, cx + 11, hy + 20, p.hair, "hair")
        if p.accessory == "pin":
            c.rect(cx + 4, hy - 11, cx + 5, hy - 6, hexc("#ffd35a"), "trim")
            c.put(cx + 4, hy - 12, hexc("#ff7a9a"), "trim")
            c.rect(cx - 3, hy - 9, cx + 1, hy - 8, hexc("#ff7a9a"), "trim")
    elif hs == "elder":
        c.ellipse(cx, hy - 13, 3, 3, p.hair, "hair")
        if back:
            c.rect(cx - 9, hy + 2, cx + 8, hy + 8, p.hair, "hair")
    elif hs == "short" and back:
        pass
    if p.hat:
        c.ellipse(cx, hy - 8, 12, 3, hexc(p.hat), "trim")
        c.rect(cx - 6, hy - 13, cx + 5, hy - 8, hexc(p.hat), "trim")
    # 臉
    if not back:
        ey = hy + 1
        if pose.get("blink"):
            for ex in (cx - 5, cx + 3):
                c.rect(ex, ey + 2, ex + 2, ey + 2, HAIR_DARK, "eye")
        else:
            for ex in (cx - 5, cx + 3):
                c.rect(ex, ey - 1, ex + 2, ey + 3, HAIR_DARK, "eye")
                c.rect(ex, ey - 1, ex + 1, ey, (255, 255, 255), "eye")
        c.put(cx - 7, ey + 4, hexc("#f2a0a0"), "skin")
        c.put(cx + 7, ey + 4, hexc("#f2a0a0"), "skin")
        c.rect(cx - 1, ey + 6, cx + 1, ey + 6, hexc("#b0605a"), "eye")
        if p.beard:
            c.poly([(cx - 7, ey + 5), (cx + 7, ey + 5), (cx + 5, ey + 14), (cx, ey + 17), (cx - 5, ey + 14)], p.beard, "beard")
            c.rect(cx - 1, ey + 6, cx + 1, ey + 6, hexc("#b0605a"), "eye")
    return c


def frames_dir(p: Pal):
    """回傳 [(anim, [pose...])]：idle_d/walk_d/idle_u/walk_u 各方向。"""
    out = []
    for view, tag in (("front", "d"), ("back", "u")):
        out.append((f"idle_{tag}", [dict(view=view, bob=0), dict(view=view, bob=1), dict(view=view, bob=0, blink=True), dict(view=view, bob=1)]))
        out.append((f"walk_{tag}", [dict(view=view, bob=0, step=1), dict(view=view, bob=1, step=0),
                                    dict(view=view, bob=0, step=-1), dict(view=view, bob=1, step=0)]))
    return out
