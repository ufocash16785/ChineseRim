"""仙劍式回合制戰鬥（純邏輯，狀態存於 Session.battle，可存檔）。

一般戰鬥（小怪）指令：attack 劍擊、spell 五行法術、item 回春丹、mpill 聚氣丹、guard 防禦、flee 逃跑。
主要對手（boss）戰另可使用：talisman 符錄、formation 陣法、treasure 法寶。

靈力規則：劍擊與各種施法都耗靈力；靈力歸零只能逃跑（或服用丹藥）。
生命規則：氣血歸零——元嬰期以前就是死亡（由 Session 回到上一個儲存點）；元嬰期以上只剩「元嬰出竅」一條路（soul）。"""
from . import items, loot
from .elements import element_multiplier
from .explore import kill_reward

KINDS = {"wolf": "青狼", "spider": "毒蛛", "bear": "鐵背熊", "snake": "赤焰蛇", "python": "碧水蟒", "ape": "山魈", "bat": "血翼蝠"}
HEAL_FRAC = 0.4
SPELL_MP_FRAC = 0.10
ATTACK_MP_FRAC = 0.02
NASCENT_REALM = 4                 # 元嬰期
FORMATION_NAMES = {"ju": "聚靈陣", "kun": "困敵陣", "sha": "殺陣", "hu": "護體陣"}


def hero_atk(ch, bonus):
    return 18 * (1 + 1.5 * ch.realm) * (1 + bonus.get("allDmg", 0)) * (1 + 0.012 * ch.level)


def spell_cost(ch):
    return max(4, round(ch.max_mp * SPELL_MP_FRAC))


def attack_cost(ch):
    return max(1, round(ch.max_mp * ATTACK_MP_FRAC))


def treasure_level(ch, iid):
    return ch.counters.get("fbl:" + iid, 0)


def owned_treasures(ch):
    out = []
    for iid, info in items.registry()["items"].items():
        if info["cat"] == "法寶" and loot.owned(ch, iid):
            out.append(iid)
    return out


def make_enemy(ch, spec, deep, idx, diff=None):
    diff = diff or {}
    scale = 1 + ch.realm * (1.3 if deep else 1.0)
    hp = 60 * scale * (1.6 if deep else 1) * diff.get("enemy_hp", 1.0)
    return {"id": spec.get("id", f"e{idx}"), "kind": spec["kind"], "name": spec.get("name") or KINDS.get(spec["kind"], "妖獸"), "el": spec["el"],
            "hp": hp, "maxhp": hp, "atk": 9.0 * scale * (1.15 if deep else 1.0) * diff.get("enemy_atk", 1.0), "dead": False, "loot": spec.get("loot", 1.0)}


def _base_state(ch, loc_id, enemies, deep, diff, partner, log, allies=None):
    return {"loc": loc_id, "deep": bool(deep), "enemies": enemies, "diff": diff or {}, "log": log, "guard": False, "over": None, "turn": 1,
            "killed": [], "rewards": [], "partner": partner, "pact": None, "boss": False, "down": False,
            "allies": [dict(a) for a in (allies or [])], "shield": 0.0, "invuln": False, "formation": None, "cd": {}, "mirror": 0, "mirror_hit": False, "retry": None}


def start(ch, loc_id, specs, deep=False, diff=None, partner=None, allies=None):
    specs = specs[:2 if deep else 3]
    if not specs:
        raise ValueError("沒有敵人")
    return _base_state(ch, loc_id, [make_enemy(ch, s, deep, i, diff) for i, s in enumerate(specs)], deep, diff, partner,
                       [f"遭遇 {'、'.join(s.get('name') or KINDS.get(s['kind'], '妖獸') for s in specs)}！"], allies)


def start_boss(ch, boss, loc_id, deep=False, diff=None, partner=None, boss_id="boss", retry=None, refine_cfg=None, allies=None):
    """主要對手戰。boss：bosses.json 的定義（已補上 name/el/kind 或 sprite）。"""
    diff = diff or {}
    scale = 1 + ch.realm
    hp = 60 * scale * boss["hp_mult"] * diff.get("enemy_hp", 1.0)
    el = ch.elements[0] if boss["el"] == "@hero" and ch.elements else ("木" if boss["el"] == "@hero" else boss["el"])
    e = {"id": f"boss:{boss_id}", "kind": boss.get("kind", "bear"), "sprite": boss.get("sprite"), "name": boss["name"], "el": el, "hp": hp, "maxhp": hp,
         "atk": 9.0 * scale * boss["atk_mult"] * diff.get("enemy_atk", 1.0), "dead": False, "loot": boss.get("loot", 3.0), "boss": True, "boss_id": boss_id,
         "skills": boss["skills"], "t": 0, "charging": False, "stun": 0, "stun_imm": 0, "rage": False, "drops": boss.get("drops"), "on_win": boss.get("on_win", []), "karma": boss.get("karma", {}), "rep": boss.get("rep"), "gold": boss.get("gold", 0), "win_bonus": boss.get("win_bonus", {})}
    st = _base_state(ch, loc_id, [e], deep, diff, partner, ([boss["intro"]] if boss.get("intro") else []) + [f"強敵「{boss['name']}」攔住了去路！（可使用陣法、符錄、法寶）"], allies)
    st["boss"] = True
    st["retry"] = retry
    st["refine_cfg"] = refine_cfg or {}
    return st


def alive(st):
    return [i for i, e in enumerate(st["enemies"]) if not e["dead"]]


def _target(st, arg2):
    al = alive(st)
    if not al:
        return None
    return arg2 if arg2 in al else al[0]


def _hit(st, i, dmg, log_prefix):
    e = st["enemies"][i]
    if st.get("mirror_hit") and dmg > 0:
        dmg *= 2.2
        st["mirror_hit"] = False
        log_prefix += "（照妖鏡破其防禦！）"
    e["hp"] -= dmg
    st["log"].append(f"{log_prefix}，對{e['name']}造成 {round(dmg)} 傷害")
    if e["hp"] <= 0:
        e["dead"] = True
        e["hp"] = 0
        st["killed"].append(e["id"])
        st["log"].append(f"{e['name']}倒下了")


def _stun(st, i, turns=1):
    e = st["enemies"][i]
    if e.get("boss") and e.get("stun_imm", 0) > 0:
        st["log"].append(f"{e['name']}已有防備，這次定不住它！")
        return
    e["stun"] = turns
    if e.get("boss"):
        e["stun_imm"] = 3
    st["log"].append(f"{e['name']}被定住了！")


REFUSE_NON_BOSS = "這種對手用不著——只有主要對手戰才能使用陣法、符錄與法寶。"


def _exhausted_allowed(cmd):
    return cmd in ("flee", "mpill", "item", "soul")


def command(st, ch, realms, rng, cmd, arg=None, target=None, bonus=None):
    """執行一個玩家指令並跑完敵方回合。回傳 True 表示戰鬥已結束。"""
    bonus = bonus or {}
    if st["over"]:
        return True
    st["log"] = []
    st["guard"] = False
    if st.get("howl", 0) > 0:
        bonus = dict(bonus, allDmg=bonus.get("allDmg", 0) + st.get("howl_val", 0))
    # ---- 氣血耗盡：只剩元嬰出竅 ----
    if st.get("down"):
        if cmd != "soul":
            st["log"].append("你氣血耗盡，動彈不得——只有元嬰出竅才能保住性命！")
            return False
        return _soul(st, ch)
    if cmd == "soul":
        st["log"].append("你還撐得住，用不著元嬰出竅。")
        return False
    # ---- 靈力耗盡：只能逃跑（或服藥）----
    if ch.mp <= 0 and not _exhausted_allowed(cmd):
        st["log"].append("靈力耗盡！你已無力施法出招，只能逃跑，或服用聚氣丹。")
        return False
    t = _target(st, target)
    used_turn = True
    if cmd == "attack":
        ch.mp = max(0.0, ch.mp - attack_cost(ch))
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
    elif cmd == "mpill":
        if ch.count("mpill") <= 0:
            st["log"].append("沒有聚氣丹了！")
            used_turn = False
        else:
            ch.remove("mpill")
            ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.5)
            st["log"].append("服下聚氣丹，靈力恢復了一半")
    elif cmd in ("talisman", "formation", "treasure"):
        used_turn = _use_gear(st, ch, rng, bonus, cmd, arg, t)
    elif cmd == "guard":
        st["guard"] = True
        ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.04)
        st["log"].append("你運功守禦，靈力略有恢復")
    elif cmd == "flee":
        base = 0.35 if st["deep"] else 0.6
        if st.get("boss"):
            base = 0.4
        chance = max(0.05, min(0.95, base + st.get("diff", {}).get("flee", 0) + (0.1 if st.get("partner") else 0) + (0.25 if ch.mp <= 0 else 0)))
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
    _formation_tick(st, ch, rng, bonus)
    if not alive(st):
        return _win(st, ch, realms, rng)
    _partner_act(st, ch, realms, rng)
    if not alive(st):
        return _win(st, ch, realms, rng)
    _allies_act(st, ch, rng)
    if not alive(st):
        return _win(st, ch, realms, rng)
    if _enemy_phase(st, ch, rng):
        return True
    _end_round(st, ch)
    return False


# ---- 陣法 / 符錄 / 法寶 ----
def _use_gear(st, ch, rng, bonus, cmd, arg, t):
    if not st.get("boss"):
        st["log"].append(REFUSE_NON_BOSS)
        return False
    info = items.info(arg) if arg else None
    want = {"talisman": "符錄", "formation": "陣法", "treasure": "法寶"}[cmd]
    if not info or info["cat"] != want or "battle" not in info:
        st["log"].append("沒有這樣東西。")
        return False
    b = info["battle"]
    e = st["enemies"][t]
    lv = bonded = 0
    aw = {}
    if cmd == "treasure":
        if not loot.owned(ch, arg):
            st["log"].append(f"你沒有{info['name']}。")
            return False
        if st["cd"].get(arg, 0) > 0:
            st["log"].append(f"{info['name']}還需要 {st['cd'][arg]} 回合才能再次催動。")
            return False
        cost = max(3, round(ch.max_mp * b.get("mp", 0.1)))
        if ch.mp < cost:
            st["log"].append("靈力不足，催動不了法寶！")
            return False
        ch.mp -= cost
        lv, bonded = treasure_level(ch, arg), ch.flags.get("bonded") == arg
        rc = st.get("refine_cfg") or {}
        st["cd"][arg] = max(1, b.get("cd", 3) - (rc.get("bond_cd_cut", 1) if bonded else 0))
        if lv >= rc.get("awaken_level", 3):
            aw = info.get("awaken", {})
    else:
        if ch.count(arg) <= 0:
            st["log"].append(f"儲物袋裡沒有{info['name']}了。")
            return False
        ch.remove(arg)
    k = b["kind"]
    atk = hero_atk(ch, bonus)
    rc = st.get("refine_cfg") or {}
    lm = (1 + rc.get("mult_per_level", 0.15) * lv) * (rc.get("bond_mult", 1.25) if bonded else 1.0) if cmd == "treasure" else 1.0
    if cmd == "treasure" and (lv or bonded):
        st["log"].append(f"（{info['name']}·{lv}階{'·本命' if bonded else ''}）")
    if k == "damage":
        mult = b.get("mult", 2.0) + b.get("grade_mult", 0) * ch.treasures.get("qingzhu_fengyunjian", 0) + aw.get("mult_add", 0)
        m = element_multiplier(b["el"], e["el"]) if b.get("el") else 1.0
        _hit(st, t, atk * mult * m * lm * rng.uniform(.92, 1.08), f"你祭出{info['name']}" + ("（剋制！）" if m > 1 else ""))
        if aw.get("stun") and not e["dead"]:
            _stun(st, t, aw["stun"])
    elif k == "bell":
        _hit(st, t, atk * b["mult"] * lm * rng.uniform(.92, 1.08), f"你搖動{info['name']}")
        if not e["dead"]:
            _stun(st, t, aw.get("stun", 1))
    elif k == "stun":
        st["log"].append(f"你甩出{info['name']}！")
        _stun(st, t, b.get("turns", 1))
    elif k == "shield":
        st["shield"] += ch.max_hp * b["frac"] * lm
        st["log"].append(f"{info['name']}化作光罩護住全身（可抵擋 {round(st['shield'])} 傷害）")
    elif k == "mp":
        ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * b["frac"])
        st["log"].append(f"{info['name']}的清氣入體，靈力回復了")
    elif k == "invuln":
        st["invuln"] = True
        st["log"].append(f"{info['name']}升起，擋在你的身前！")
        if aw.get("shield"):
            st["shield"] += ch.max_hp * aw["shield"] * lm
            st["log"].append(f"覺醒之力化為護盾（{round(st['shield'])}）")
    elif k == "mirror":
        st["mirror"] = 3 + aw.get("mirror_extra", 0)
        st["mirror_hit"] = True
        if aw.get("heal"):
            ch.hp = min(ch.max_hp, ch.hp + ch.max_hp * aw["heal"])
        st["log"].append(f"{info['name']}照出了敵人的破綻——敵人攻擊力下降，你的下一擊將勢不可擋！")
    elif k == "formation":
        st["formation"] = {"id": b["id"], "turns": b["turns"]}
        st["log"].append(f"你佈下{FORMATION_NAMES[b['id']]}！（持續 {b['turns']} 回合）")
    return True


def _formation_tick(st, ch, rng, bonus):
    _dot_tick(st)
    f = st.get("formation")
    if not f:
        return
    if f["id"] == "ju":
        ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.08)
        st["log"].append("聚靈陣運轉，靈力回流")
    elif f["id"] == "sha":
        for i in alive(st):
            _hit(st, i, hero_atk(ch, bonus) * 0.8 * rng.uniform(.9, 1.1), "殺陣運轉")


def _enemy_phase(st, ch, rng):
    """敵方回合。回傳 True＝戰鬥因你倒下（死亡）而結束。"""
    prim = ch.elements[0] if ch.elements else ""
    inv = st.get("invuln")
    st["invuln"] = False
    f = st.get("formation")
    for i in alive(st):
        e = st["enemies"][i]
        if e.get("boss") and not e["rage"] and e["hp"] < e["maxhp"] * 0.5:
            e["rage"] = True
            e["atk"] *= 1.25
            st["log"].append(f"{e['name']}怒吼一聲，氣勢暴漲！")
        if e.get("stun", 0) > 0:
            e["stun"] -= 1
            e["charging"] = False
            st["log"].append(f"{e['name']}被定住，無法行動")
            continue
        if not e.get("boss") and rng.random() < 0.12:
            st["log"].append(f"{e['name']}遲疑了一下")
            continue
        skill = None
        if e.get("boss"):
            e["t"] += 1
            for sk in e["skills"]:
                if e["t"] % sk["every"] == 0:
                    skill = sk
                    break
        if not skill and st.get("partner") and rng.random() < 0.35:      # 有道侶在側，部分攻擊被她擋下
            st["log"].append(f"{e['name']}撲向{st['partner']['name']}，被她輕巧地化解了")
            continue
        m = element_multiplier(e["el"], prim)
        d = e["atk"] * m * rng.uniform(.85, 1.15) * (skill["mult"] if skill else 1.0) * (0.5 if st["guard"] else 1.0)
        if st.get("mirror", 0) > 0:
            d *= 0.8
        if f and f["id"] == "kun":
            d *= 0.6
        if f and f["id"] == "hu":
            d *= 0.65
        if st.get("web", 0) > 0:
            d *= 1 - st.get("web_val", 0)
        name = f"{e['name']}的「{skill['name']}」" if skill else e["name"]
        if inv:
            st["log"].append(f"{name}襲來，卻被法寶擋了下來！")
        else:
            pup = next((a for a in st.get("allies", []) if a["type"] == "puppet" and a["hp"] > 0), None)
            if pup and d > 0 and rng.random() < pup["absorb"]:
                pup["hp"] -= d * pup["absorb_frac"]
                st["log"].append(f"{pup['name']}擋在你身前，替你承受了攻擊！")
                if pup["hp"] <= 0:
                    pup["hp"] = 0
                    st["log"].append(f"{pup['name']}破損了……（戰後需要修理）")
                d = 0
            if st["shield"] > 0:
                ab = min(st["shield"], d)
                st["shield"] -= ab
                d -= ab
                st["log"].append(f"護盾吸收了 {round(ab)} 傷害")
            if d > 0:
                ch.hp -= d
                st["log"].append(f"{name}襲來，你受到 {round(d)} 傷害" + ("（被剋制）" if m > 1 else ""))
            if ch.hp <= 0:
                ch.hp = 0
                if ch.realm >= NASCENT_REALM:
                    st["down"] = True
                    st["log"].append("你氣血耗盡，元神搖搖欲墜……只有元嬰出竅才能保住性命！")
                    return False
                st["over"] = "lose"
                st["log"].append("你重傷倒下了……")
                return True
        if e.get("boss"):
            e["charging"] = any((e["t"] + 1) % sk["every"] == 0 for sk in e["skills"])
            if e["charging"]:
                st["log"].append(f"{e['name']}周身靈氣暴漲，正在凝聚力量！（下一擊將是絕招——可防禦、開護盾或定住它）")
    return False


def _end_round(st, ch):
    st["turn"] += 1
    ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.01)
    for k in list(st["cd"]):
        st["cd"][k] = max(0, st["cd"][k] - 1)
    if st.get("mirror", 0) > 0:
        st["mirror"] -= 1
    for k in ("howl", "web"):
        if st.get(k, 0) > 0:
            st[k] -= 1
    for e in st["enemies"]:
        if e.get("stun_imm", 0) > 0 and e.get("stun", 0) == 0:
            e["stun_imm"] -= 1
    f = st.get("formation")
    if f:
        f["turns"] -= 1
        if f["turns"] <= 0:
            st["log"].append(f"{FORMATION_NAMES[f['id']]}的靈光散去了")
            st["formation"] = None


def _soul(st, ch):
    """元嬰出竅：元嬰帶著殘存的元神逃離，保住性命，但元氣大傷。"""
    ch.hp = max(1.0, ch.max_hp * 0.2)
    ch.mp = 0.0
    st["over"] = "soul"
    st["down"] = False
    st["log"].append("你的元嬰破體而出，化作一道流光遁走……肉身暫且不顧，性命保住了。")
    return True


def _pet_skill(st, ch, a, rng):
    """靈寵專屬技能。回傳 True 表示這回合用掉了技能。"""
    sk = a.get("skill")
    if not sk:
        return False
    if a["cd"] > 0:
        a["cd"] -= 1
        return False
    al = alive(st)
    t = min(al, key=lambda i: st["enemies"][i]["hp"])
    e = st["enemies"][t]
    base = hero_atk(ch, {}) * a["atk"] * rng.uniform(.9, 1.1)
    v, ty, nm = sk["val"], sk["type"], sk["name"]
    pre = f"{a['name']}施展「{nm}」"
    if ty == "howl":
        st["howl"], st["howl_val"] = sk["turns"], v
        st["log"].append(f"{pre}，你的傷害 +{round(v * 100)}%（{sk['turns']} 回合）！")
    elif ty == "shield":
        st["shield"] += ch.max_hp * v
        st["log"].append(f"{pre}，替你擋下傷害（護盾 {round(st['shield'])}）")
    elif ty == "poison":
        e["dot"] = {"turns": sk["turns"], "dmg": base * v}
        st["log"].append(f"{pre}，{e['name']}中毒了！")
    elif ty == "stun":
        _hit(st, t, base * v, pre)
        if not e["dead"]:
            _stun(st, t, 1)
    elif ty == "drain":
        _hit(st, t, base * sk.get("dmg", 1.2), pre)
        heal = ch.max_hp * v
        ch.hp = min(ch.max_hp, ch.hp + heal)
        st["log"].append(f"吸取生機，你回復了 {round(heal)} 點氣血")
    elif ty == "web":
        st["web"], st["web_val"] = sk["turns"], v
        st["log"].append(f"{pre}，敵人被絲網纏住，傷害 -{round(v * 100)}%（{sk['turns']} 回合）！")
    elif ty == "breath":
        for i in list(al):
            m = element_multiplier(a["el"], st["enemies"][i]["el"]) if a.get("el") else 1.0
            _hit(st, i, base * v * m, pre)
    a["cd"] = a["cd_max"]
    st["aact"].append({"type": "pet", "target": t, "skill": ty})
    return True


def _dot_tick(st):
    for i in alive(st):
        e = st["enemies"][i]
        d = e.get("dot")
        if d:
            _hit(st, i, d["dmg"], f"{e['name']}毒發")
            d["turns"] -= 1
            if d["turns"] <= 0:
                e.pop("dot")


def _allies_act(st, ch, rng):
    """靈寵與傀儡自動出手。"""
    st["aact"] = []
    for a in st.get("allies", []):
        al = alive(st)
        if not al or a["hp"] <= 0:
            continue
        if a["type"] == "pet" and _pet_skill(st, ch, a, rng):
            continue
        t = min(al, key=lambda i: st["enemies"][i]["hp"])
        e = st["enemies"][t]
        m = element_multiplier(a["el"], e["el"]) if a.get("el") else 1.0
        d = hero_atk(ch, {}) * a["atk"] * m * rng.uniform(.9, 1.1)
        _hit(st, t, d, f"{a['name']}撲上去攻擊" + ("（剋制！）" if m > 1 else ""))
        st["aact"].append({"type": a["type"], "target": t})


def _partner_act(st, ch, realms, rng):
    """道侶自動出手：血量低時可能治療，否則攻擊或施展五行法術。"""
    p = st.get("partner")
    st["pact"] = None
    if not p or not alive(st):
        return
    heal_p = {"healer": 0.6, "mage": 0.25, "fighter": 0.15}.get(p["role"], 0.2)
    if ch.hp < 0.5 * ch.max_hp and rng.random() < heal_p + 0.15:
        amt = ch.max_hp * (0.28 if p["role"] == "healer" else 0.18)
        ch.hp = min(ch.max_hp, ch.hp + amt)
        st["log"].append(f"{p['name']}為你施展療傷之術，回復 {round(amt)} 點氣血")
        st["pact"] = {"kind": "heal", "target": None}
        return
    al = alive(st)
    t = min(al, key=lambda i: st["enemies"][i]["hp"])
    base = hero_atk(ch, {}) * p["atk"] * rng.uniform(.9, 1.1)
    e = st["enemies"][t]
    if p["role"] != "fighter" and rng.random() < 0.55:
        m = element_multiplier(p["el"], e["el"])
        _hit(st, t, base * 1.6 * m, f"{p['name']}施展{p['el']}系法術" + ("（剋制！）" if m > 1 else ""))
        st["pact"] = {"kind": "spell", "target": t, "el": p["el"]}
    else:
        _hit(st, t, base, f"{p['name']}出手攻擊")
        st["pact"] = {"kind": "attack", "target": t}


def _win(st, ch, realms, rng):
    st["over"] = "win"
    st["log"].append("戰鬥勝利！")
    gold_mult = st.get("diff", {}).get("gold", 1.0)
    for e in st["enemies"]:
        msgs = kill_reward(realms, ch, rng, st["loc"], st["deep"], gold_mult * e.get("loot", 1.0))
        st["rewards"].extend(msgs)
    ch.mp = min(ch.max_mp, ch.mp + ch.max_mp * 0.1)
    for e in st["enemies"]:
        if e.get("boss"):
            for eff in e.get("on_win", []):
                if "flag" in eff:
                    ch.flags[eff["flag"]] = True
    st["log"].extend(st["rewards"])
    return True


def view(st, ch):
    if not st:
        return None
    return {"loc": st["loc"], "deep": st["deep"], "over": st["over"], "turn": st["turn"], "log": st["log"], "boss": st.get("boss", False),
            "down": st.get("down", False), "exhausted": ch.mp <= 0, "shield": round(st.get("shield", 0)), "formation": st.get("formation"),
            "cd": st.get("cd", {}), "mirror": st.get("mirror", 0), "attackCost": attack_cost(ch),
            "enemies": [{k: e.get(k) for k in ("id", "kind", "name", "el", "hp", "maxhp", "dead", "sprite", "boss", "charging", "stun")} for e in st["enemies"]],
            "partner": st.get("partner"), "pact": st.get("pact"), "allies": [dict({k: a.get(k) for k in ("type", "name", "kind", "el", "sprite", "hp", "maxhp", "level", "cd")}, skill=(a.get("skill") or {}).get("name")) for a in st.get("allies", [])], "aact": st.get("aact", []), "spellCost": spell_cost(ch), "diff": st.get("diff", {}).get("name", ""),
            "killed": st["killed"], "rewards": st["rewards"]}
