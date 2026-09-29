"""任務系統：依 data/quests.json 的條件推進 story_arcs.json 的任務，卷與卷之間自動銜接。
進度存在 Character.quest（隨存檔保存）。visit/kill/arrive 條件從目標啟用時開始累計。"""
from . import dialogue
from .character import item_name

COUNTED = ("visit", "kill", "arrive")


def arc_order(data):
    return [a["id"] for a in data.arcs if a["id"] in data.quest_rules]


def _arc(data, arc_id):
    return next(a for a in data.arcs if a["id"] == arc_id)


def _rules(data, arc_id):
    return data.quest_rules.get(arc_id, {})


def ensure(ch, data=None):
    if not ch.quest:
        first = arc_order(data)[0] if data else "arc0_qixuanmen"
        ch.quest = {"arc": first, "q": 0, "o": 0, "baseline": dict(ch.counters), "done": False, "completed": []}
    return ch.quest


def _met(cond, ch, base):
    t, n = cond["type"], cond.get("n", 1)
    if t in COUNTED:
        key = f"{t}:{cond['loc']}"
        return ch.counters.get(key, 0) - base.get(key, 0) >= n
    if t == "level":
        return ch.level >= n
    if t == "realm":
        return ch.realm >= n
    if t == "item":
        return ch.count(cond["item"]) >= n
    if t == "flag":
        return bool(ch.flags.get(cond["flag"]))
    if t == "treasure":
        return ch.treasures.get(cond["id"], 0) >= n
    return False


def _progress_text(cond, ch, base):
    t, n = cond["type"], cond.get("n", 1)
    if t in COUNTED:
        key = f"{t}:{cond['loc']}"
        return f"{min(n, ch.counters.get(key, 0) - base.get(key, 0))}/{n}"
    if t == "flag":
        return "1/1" if ch.flags.get(cond["flag"]) else "0/1"
    if t == "treasure":
        return f"{min(n, ch.treasures.get(cond['id'], 0))}/{n}"
    cur = {"level": ch.level, "realm": ch.realm}.get(t, ch.count(cond.get("item", "")))
    return f"{min(n, cur)}/{n}"


def _reward(realms, ch, reward, msgs):
    for item, n in reward.items():
        if item == "level":
            realms.gain_level(ch, n)
            msgs.append(f"  修為精進：等級 +{n}")
        else:
            ch.add(item, n)
            msgs.append(f"  獎勵 {item_name(item)} ×{n}")


def update(data, ch, realms):
    """推進任務；回傳新訊息列表。"""
    q = ensure(ch, data)
    q.setdefault("completed", [])
    msgs = []
    order = arc_order(data)
    while True:
        if q["done"]:                       # 舊存檔：上一卷已完成但後面還有卷
            i = order.index(q["arc"])
            if i + 1 >= len(order):
                break
            q.update(arc=order[i + 1], q=0, o=0, done=False, baseline=dict(ch.counters))
            msgs.append(f"══ {_arc(data, q['arc'])['name']} ══")
            continue
        arc = _arc(data, q["arc"])
        quest = arc["quests"][q["q"]]
        rule = _rules(data, q["arc"]).get(quest["id"])
        if not rule:
            break
        cond = rule["objectives"][q["o"]]
        if dialogue.gating(data, ch, quest["id"], q["o"]) or not _met(cond, ch, q["baseline"]):
            break
        msgs.append(f"✔ 目標完成：{quest['objectives'][q['o']]}")
        q["o"] += 1
        q["baseline"] = dict(ch.counters)
        if q["o"] >= len(rule["objectives"]):
            msgs.append(f"★ 任務完成：{quest['name']}")
            _reward(realms, ch, rule.get("reward", {}), msgs)
            q["completed"].append(quest["id"])
            q["q"] += 1
            q["o"] = 0
            if q["q"] >= len(arc["quests"]):
                msgs.append(f"★★ {arc['name']} 完成！")
                q["done"] = True            # 下一輪迴圈決定是否銜接下一卷
    return msgs


def view(data, ch):
    q = ensure(ch, data)
    arc = _arc(data, q["arc"])
    last = arc_order(data)[-1] == q["arc"]
    out = {"arc": arc["name"], "done": q["done"] and last, "quests": []}
    for i, quest in enumerate(arc["quests"]):
        rule = _rules(data, q["arc"]).get(quest["id"], {"objectives": []})
        state = "done" if q["done"] or i < q["q"] else "active" if i == q["q"] else "locked"
        objs = []
        for j, text in enumerate(quest["objectives"]):
            if state == "done" or (state == "active" and j < q["o"]):
                objs.append({"text": text, "state": "done"})
            elif state == "active" and j == q["o"]:
                hint = dialogue.gating_hint(data, ch, quest["id"], j) if dialogue.gating(data, ch, quest["id"], j) else ""
                prog = hint or (_progress_text(rule["objectives"][j], ch, q["baseline"]) if rule["objectives"] else "")
                objs.append({"text": text, "state": "active", "progress": prog})
            else:
                objs.append({"text": text, "state": "locked"})
        out["quests"].append({"name": quest["name"], "state": state, "objectives": objs})
    return out


def _region_of(data, loc):
    for w in data.regions:
        for g in w["regions"]:
            if any(l["id"] == loc for l in g["locations"]):
                return g["id"]
    return None


def target(data, ch):
    """目前目標該去哪裡：{"loc":地點id|None, "region":區域id|None}；沒有明確地點時回傳 None。"""
    q = ensure(ch, data)
    if q["done"] and arc_order(data)[-1] == q["arc"]:
        return None
    arc = _arc(data, q["arc"])
    quest = arc["quests"][q["q"]] if q["q"] < len(arc["quests"]) else None
    rule = _rules(data, q["arc"]).get(quest["id"]) if quest else None
    if not rule:
        return None
    for did, d in data.dialogues.items():        # 尚未播放的簡報優先
        t = d["trigger"]
        if not ch.flags.get("seen:" + did) and t.get("quest") == quest["id"] and t.get("obj") == q["o"]:
            if "arrive" in t:
                return {"loc": None, "region": t["arrive"]}
            return {"loc": t["loc"], "region": _region_of(data, t["loc"])}
    cond = rule["objectives"][q["o"]]
    if cond["type"] in ("visit", "kill") and cond["loc"] != "total":
        return {"loc": cond["loc"], "region": _region_of(data, cond["loc"])}
    if cond["type"] == "arrive":
        return {"loc": None, "region": cond["loc"]}
    return None
