"""任務系統：依 data/quests.json 的條件推進 story_arcs.json 的任務。
進度存在 Character.quest（隨存檔保存）。visit/kill 條件從目標啟用時開始累計。"""

from . import dialogue

ARC = "arc0_qixuanmen"


def _arc(data, arc_id):
    return next(a for a in data.arcs if a["id"] == arc_id)


def _rules(data, arc_id):
    return data.quest_rules.get(arc_id, {})


def ensure(ch, arc_id=ARC):
    if not ch.quest:
        ch.quest = {"arc": arc_id, "q": 0, "o": 0, "baseline": dict(ch.counters), "done": False}
    return ch.quest


def _met(cond, ch, base):
    t, n = cond["type"], cond.get("n", 1)
    if t in ("visit", "kill"):
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
    return False


def _progress_text(cond, ch, base):
    t, n = cond["type"], cond.get("n", 1)
    if t in ("visit", "kill"):
        key = f"{t}:{cond['loc']}"
        return f"{min(n, ch.counters.get(key, 0) - base.get(key, 0))}/{n}"
    if t == "flag":
        return "1/1" if ch.flags.get(cond["flag"]) else "0/1"
    cur = {"level": ch.level, "realm": ch.realm}.get(t, ch.count(cond.get("item", "")))
    return f"{min(n, cur)}/{n}"


def update(data, ch):
    """推進任務；回傳新訊息列表。"""
    q = ensure(ch)
    msgs = []
    arc = _arc(data, q["arc"])
    while not q["done"]:
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
            for item, n in rule.get("reward", {}).items():
                ch.add(item, n)
                msgs.append(f"  獎勵 {item} ×{n}")
            q.setdefault("completed", []).append(quest["id"])
            q["q"] += 1
            q["o"] = 0
            if q["q"] >= len(arc["quests"]):
                q["done"] = True
                msgs.append(f"★★ {arc['name']} 完成！")
    return msgs


def view(data, ch):
    q = ensure(ch)
    arc = _arc(data, q["arc"])
    out = {"arc": arc["name"], "done": q["done"], "quests": []}
    for i, quest in enumerate(arc["quests"]):
        rule = _rules(data, q["arc"]).get(quest["id"], {"objectives": []})
        state = "done" if q["done"] or i < q["q"] else "active" if i == q["q"] else "locked"
        objs = []
        for j, text in enumerate(quest["objectives"]):
            if state == "done" or (state == "active" and j < q["o"]):
                objs.append({"text": text, "state": "done"})
            elif state == "active" and j == q["o"]:
                objs.append({"text": text, "state": "active", "progress": (dialogue.gating_hint(data, ch, quest["id"], j) if dialogue.gating(data, ch, quest["id"], j) else _progress_text(rule["objectives"][j], ch, q["baseline"])) if rule["objectives"] else ""})
            else:
                objs.append({"text": text, "state": "locked"})
        out["quests"].append({"name": quest["name"], "state": state, "objectives": objs})
    return out
