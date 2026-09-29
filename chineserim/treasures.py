"""法寶祭煉（原 CR_TreasureGrowth）與掌天瓶（原 CR_ZhangTianPing）。"""

MOON_CYCLE_DAYS = 30   # 原 Skyrim 為 24 日；獨立版改為 30 日朔望月


def required_realm(grade: int) -> int:
    return grade + 1


def cost_lingshi(grade: int) -> int:
    return 50 * grade * grade


def refine(realms, ch, treasure_id) -> bool:
    nxt = ch.treasures.get(treasure_id, 0) + 1
    if ch.realm < required_realm(nxt):
        return False
    if not ch.remove("lingshi", cost_lingshi(nxt)):
        return False
    ch.treasures[treasure_id] = nxt
    realms.emit("CR_OnTreasureRefined", item=treasure_id, grade=nxt)
    return True


def treasure_power(base: float, grade: int) -> float:
    return base * (1.0 + 0.25 * grade)


def tick_zhangtianping(realms, ch, day: int, hour: float, outdoors=True, last_day=None):
    """月圓之夜（室外、21~4 時）產一滴靈液。回傳本次觸發的日子（供防重複）。"""
    if day % MOON_CYCLE_DAYS != 0 or last_day == day:
        return last_day
    if outdoors and (hour >= 21 or hour <= 4):
        ch.add("lingye")
    realms.emit("CR_OnMoonFull", day=day)
    return day
