"""仙劍式回合制戰鬥（純邏輯，狀態存於 Session.battle，可存檔）。

指令：attack 劍擊、spell 五行法術、item 服用回春丹、guard 防禦回氣、flee 逃跑。"""
import random

from .elements import element_multiplier
from .explore import kill_reward

KINDS = {"wolf": "青狼", "spider": "毒蛛", "bear": "鐵背熊", "snake": "赤焰蛇", "python": "碧水蟒", "ape": "山魈", "bat": "血翼蝠"}
HEAL_FRAC = 0.4
SPELL_MP_FRAC = 0.10


def hero_atk(ch, bonus):
    return 18 * (1 + 1.5 * ch.realm) * (1 + bonus.get("allDmg", 0)) * (1 + 0.012 * ch.level)


def spell_cost(ch):
    return max(4, round(ch.max_mp * SPELL_MP_FRAC))


def make_enemy(ch, spec, deep, idx):
    scale = 1 + ch.realm * (1.3 if deep else 1.0)
    hp = 60 * scale * (1.6 if deep else 1)
    return {"id": spec.get("id", f"e{idx}"), "kind": spec["kind"], "name": KINDS.get(spec["kind"], "妖獸"), "el": spec["el"],
            "hp": hp, "maxhp": hp, "atk": 9.0 * scale * (1.15 if deep else 1.0), "dead": False}


def start(ch, loc_id, specs, deep=False):
    specs = specs[:2 if deep else 3]
    if not specs:
        raise ValueError("沒有敵人")
    return {"loc": loc_id, "deep": bool(deep), "enemies": [make_enemy(ch, s, deep, i) for i, s in enumerate(specs)],
            "log": [f"遭遇 {'、'.join(KINDS.get(s['kind'], '妖獸') for s in specs)}！"], "guard": False, "over": None, "turn": 1,
            "killed": [], "rewards": []}


def alive(st):
    return [i for i, e in enumerate(st["enemies"]) if not e["dead"]]


def _target(st, arg2):
    al = alive(st)
    if not al:
        return None
    return arg2 if arg2 in al else al[0]


def _hit(st, i, dmg, log_prefix):
    e = st["enemies"][i]
    e["hp"] -= dmg
    st["log"].append(f"{log_prefix}，對{e['name']}造成 {round(dmg)} 傷害")
    if e["hp"] <= 0:
        e["dead"] = True
        e["hp"] = 0
        st["killed"].append(e["id"])
        st["log"].append(f"{e['name']}倒下了")


def command(st, ch, realms, rng, cmd, arg=None, target=None, bonus=None):
    """執行一個玩家指令並跑完敵方回合。回傳 True 表示戰鬥已結束。"""
    bonus = bonus or {}
    if st["over"]:
        return True
    st["log"] = []
    st["guard"] = False
    t = _target(st, target)
    used_turn = True
    if cmd == "attack":
        crit = rng.random() < bonus.get("critChance", 0) + 0.08
        d = hero_atk(ch, bonus) * (1 + bonus.get("slashDmg", 0)) * rng.uniform(.9, 1.1) * (2 if crit else 1)
        _hit(st, t, d, "你揮劍斬出" + ("（會心一擊！）" if crit else ""))
    elif cmd == "spell":
        el_list = ch.elements or ["木"]
        el = el_list[(arg or 0) % len(el_list)]
        cost = spell_cost(ch)
        if ch.mp < cost:
            st["log"].append("靈力不足！")
            used_turn = False
        else:
            ch.mp -= cost
            e = st["enemies"][t]
            m = element_multiplier(el, e["el"])
            d = hero_atk(ch, bonus) * 1.7 * (1 + bonus.get("elemDmg", {}).get(el, 0)) * m * rng.uniform(.9, 1.1)
            tag = "（剋制！）" if m > 1 else "（被剋…）" if m < 1 else ""
            _hit(st, t, d, f"你施展{el}系法術{tag}")
    elif cmd == "item":
        if ch.count("heal") <= 0:
            st["log"].append("沒有回春丹了！")
            used_turn = False
        else:
            ch.remove("heal")
            amt = ch.max_hp * HEAL_FRAC
            ch.hp = min(ch.max_hp, ch.hp + amt)
            st["log"].append(f"服下回春丹，回復 {round(amt)} 點氣血")
    elif cmd == "guard":
        st["guard"] = True
        ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.04)
        st["log"].append("你運功守禦，靈力略有恢復")
    elif cmd == "flee":
        chance = 0.35 if st["deep"] else 0.6
        if rng.random() < chance:
            st["log"].append("你成功逃脫了！")
            st["over"] = "flee"
            return True
        st["log"].append("逃跑失敗！")
    else:
        st["log"].append("未知指令")
        used_turn = False
    if not used_turn:
        return False
    if not alive(st):
        return _win(st, ch, realms, rng)
    # 敵方回合
    prim = ch.elements[0] if ch.elements else ""
    for i in alive(st):
        e = st["enemies"][i]
        if rng.random() < 0.12:
            st["log"].append(f"{e['name']}遲疑了一下")
            continue
        m = element_multiplier(e["el"], prim)
        d = e["atk"] * m * rng.uniform(.85, 1.15) * (0.5 if st["guard"] else 1.0)
        ch.hp -= d
        st["log"].append(f"{e['name']}撲來，你受到 {round(d)} 傷害" + ("（被剋制）" if m > 1 else ""))
        if ch.hp <= 0:
            ch.hp = 0
            st["over"] = "lose"
            st["log"].append("你重傷倒下了……")
            return True
    st["turn"] += 1
    return False


def _win(st, ch, realms, rng):
    st["over"] = "win"
    st["log"].append("戰鬥勝利！")
    for e in st["enemies"]:
        msgs = kill_reward(realms, ch, rng, st["loc"], st["deep"])
        st["rewards"].extend(msgs)
    ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.1)
    if rng.random() < 0.25:
        ch.add("heal")
        st["rewards"].append("拾得回春丹 ×1")
    st["log"].extend(st["rewards"])
    return True


def view(st, ch):
    if not st:
        return None
    return {"loc": st["loc"], "deep": st["deep"], "over": st["over"], "turn": st["turn"], "log": st["log"],
            "enemies": [{k: e[k] for k in ("id", "kind", "name", "el", "hp", "maxhp", "dead")} for e in st["enemies"]],
            "spellCost": spell_cost(ch), "killed": st["killed"], "rewards": st["rewards"]}
