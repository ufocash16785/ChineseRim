"""地圖探索：區域間旅行、地點事件、遭遇戰。純邏輯，不含任何 UI。"""
import math
import random

from .elements import element_multiplier

SAFE = {"村鎮", "城市", "都城", "府城", "坊市", "巨城", "國都", "港口", "集市"}
SECT = {"門派", "門派/山", "魔宗"}
DEEP = {"秘境", "聖地", "洞窟", "遺跡", "礦坑"}
GARDEN = {"藥園"}
DWELLING = {"洞府"}
ELEMENTS = ["金", "木", "水", "火", "土", "雷", "冰", "風"]
BEASTS = ["青狼", "毒蛛", "鐵背熊", "赤焰蛇", "碧水蟒", "山魈", "血翼蝠"]
LINGJIE_MIN_REALM = 5
DEEP_GATE = {"xuese": 1}      # 秘境進入所需境界（預設 2＝築基）；血色禁地練氣期即可進入


def min_realm(loc_id, loc=None):
    """進入所需境界：地點資料的 minRealm 優先，其次 DEEP_GATE，秘境類預設築基。"""
    if loc is not None and "minRealm" in loc:
        return loc["minRealm"]
    return DEEP_GATE.get(loc_id, 2)


class WorldMap:
    def __init__(self, data):
        self.regions = {}
        self.sect_index = data.sects
        for w in data.regions:
            for g in w["regions"]:
                g = dict(g, world=w["id"], world_name=w["name"], locked_realm=LINGJIE_MIN_REALM if w["id"] == "lingjie" else 0)
                self.regions[g["id"]] = g

    def travel_days(self, ch, a, b):
        if a == b:
            return 0
        (x1, y1), (x2, y2) = self.regions[a]["coords"], self.regions[b]["coords"]
        d = math.hypot(x1 - x2, y1 - y2)
        days = max(1, round(d / 4))
        return max(1, days // 3) if ch.realm >= 2 else days     # 築基後可御器飛行

    def can_enter(self, ch, region_id):
        return ch.realm >= self.regions[region_id]["locked_realm"]

    def travel(self, ch, a, b):
        """回傳 (成功, 天數, 訊息)。"""
        if not self.can_enter(ch, b):
            return False, 0, f"{self.regions[b]['name']}需化神期飛升後才能前往"
        return True, self.travel_days(ch, a, b), f"抵達{self.regions[b]['name']}"

    def location_layout(self, region_id):
        """地點在區域內圖上的位置（環狀，決定性）。回傳 [(loc, x, y)]，座標 0~100。"""
        locs = self.regions[region_id]["locations"]
        n = len(locs)
        out = []
        for i, l in enumerate(locs):
            ring = 0 if i < 6 else 1
            k, m = (i, min(n, 6)) if ring == 0 else (i - 6, max(n - 6, 1))
            ang = 2 * math.pi * k / m + ring * 0.5
            rad = 22 if ring == 0 else 40
            out.append((l, round(50 + rad * math.cos(ang), 1), round(50 + rad * math.sin(ang), 1)))
        return out


def find_location(world, region_id, loc_id):
    for l in world.regions[region_id]["locations"]:
        if l["id"] == loc_id:
            return l
    raise KeyError(loc_id)


def is_wild(loc_type):
    return not (loc_type in SAFE or loc_type in SECT or loc_type in DEEP or loc_type in GARDEN or loc_type in DWELLING)


def scale_for(ch, deep=False):
    return 1 + ch.realm * (1.6 if deep else 1.0)


def kill_reward(realms, ch, rng, loc_id, deep=False, mult=1.0):
    """即時戰鬥擊殺一隻妖獸的結算（卷軸前端使用）。回傳訊息列表。"""
    scale = scale_for(ch, deep)
    gold = int(rng.uniform(20, 60) * scale * (3 if deep else 1) * mult)
    ch.add("lingshi", gold)
    for k in (f"kill:{loc_id}", "kill:total"):
        ch.counters[k] = ch.counters.get(k, 0) + 1
    realms.gain_level(ch, 8 if deep else 3)
    msg = [f"擊殺妖獸，獲得靈石 {gold}" if gold else "擊殺妖獸，卻一無所獲……"]
    if deep and rng.random() < min(0.95, 0.6 * mult):
        ch.add("lingye")
        msg.append("秘境深處拾得一滴靈液")
    return msg


def fight(ch, rng, deep=False):
    """自動回合制。回傳 (勝?, 紀錄行, 戰利靈石)。"""
    beast_elem = rng.choice(ELEMENTS)
    name = rng.choice(BEASTS)
    scale = 1 + ch.realm * (1.6 if deep else 1.0)
    bhp = 60 * scale * (2 if deep else 1)
    batk = 12 * scale * (1.5 if deep else 1)
    mult = max(element_multiplier(e, beast_elem) for e in ch.elements) if ch.elements else 1.0
    incoming = element_multiplier(beast_elem, ch.primary_element)
    atk = 18 * (1 + ch.realm * 1.5) * mult
    log = [f"遭遇 {beast_elem}屬性{name}（HP {bhp:.0f}）；我方屬性倍率 ×{mult}，對方 ×{incoming}"]
    hp = ch.hp
    for rnd in range(1, 21):
        bhp -= atk * rng.uniform(0.8, 1.2)
        if bhp <= 0:
            ch.hp = max(1, hp)
            gold = int(rng.uniform(20, 60) * scale * (3 if deep else 1))
            log.append(f"第 {rnd} 回合擊敗{name}，獲得靈石 {gold}")
            return True, log, gold
        hp -= batk * incoming * rng.uniform(0.8, 1.2)
        if hp <= 0:
            break
    ch.hp = 1
    log.append(f"不敵{name}，重傷逃回")
    return False, log, 0


def visit(world, realms, ch, region_id, loc_id, rng=None, day=0, fight_wild=True):
    """造訪地點，回傳 (訊息列表, 花費天數)。"""
    rng = rng or random.Random()
    loc = find_location(world, region_id, loc_id)
    t = loc["type"]
    if t in DEEP and ch.realm < min_realm(loc_id, loc):
        return [f"{loc['name']}靈壓駭人，境界不足，不得深入"], 0
    ch.counters[f"visit:{loc_id}"] = ch.counters.get(f"visit:{loc_id}", 0) + 1
    if t in SAFE or t in GARDEN or t in DWELLING:
        ch.hp = ch.max_hp
        msg = [f"在{loc['name']}休整，HP 回滿。"]
        if ch.count("lingshi") >= 100 and rng.random() < 0.5:
            ch.remove("lingshi", 100)
            ch.add("pill")
            msg.append("坊市裡花 100 靈石購得一顆突破丹")
        return msg, 1
    if t in SECT:
        sid = next((s for s, v in world.sect_index.items() if v["name"] in loc["name"]), None)
        msg = [f"拜訪{loc['name']}，靜心參悟。"]
        realms.gain_level(ch, 2)
        if sid:
            ch.sects[sid] = min(4, ch.sects.get(sid, 0) + 1)
            msg.append(f"與{world.sect_index[sid]['name']}聲望 {ch.sects[sid]}/4")
        return msg, 2
    if not fight_wild:      # 卷軸前端：野外/秘境由玩家即時戰鬥，這裡只記錄到訪
        return [f"來到{loc['name']}"], 0
    ok, log, gold = fight(ch, rng, deep=t in DEEP)
    if ok:
        for k in (f"kill:{loc_id}", "kill:total"):
            ch.counters[k] = ch.counters.get(k, 0) + 1
        ch.add("lingshi", gold)
        realms.gain_level(ch, 3 if t not in DEEP else 8)
        if t in DEEP and rng.random() < 0.6:
            ch.add("lingye")
            log.append("秘境深處拾得一滴靈液")
    else:
        ch.remove("lingshi", min(50, ch.count("lingshi")))
    return log, 2
