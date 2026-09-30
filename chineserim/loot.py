"""掉寶：依掉落表擲骰，戰利品一律收入儲物袋（容量無限）。"""
from . import items


def owned(ch, item_id):
    if item_id == "fb_qingzhu":
        return ch.treasures.get("qingzhu_fengyunjian", 0) >= 1
    return ch.count(item_id) > 0


def roll_table(data, table, ch, rng, mult=1.0):
    """table：drops.json tables 的名稱或列表。回傳 [(item, n)]。mult 影響數量（靈石為主）。"""
    rows = data.drops["tables"][table] if isinstance(table, str) else table
    out = []
    for r in rows:
        if rng.random() > min(1.0, r.get("chance", 1.0) * (1.0 if r["item"] not in ("lingshi",) else 1.0)):
            continue
        if r.get("unique") and owned(ch, r["item"]):
            continue
        lo, hi = r.get("n", [1, 1])
        n = rng.randint(lo, hi)
        if r.get("scale"):
            n = int(n * (1 + ch.realm))
        if r["item"] == "lingshi":
            n = int(n * mult)
        if n > 0:
            out.append((r["item"], n))
    return out


def roll_minion(data, ch, rng):
    m = data.drops["minion"]
    if rng.random() >= m["chance"]:
        return []
    t = m["table"]
    r = rng.choices(t, weights=[x["w"] for x in t])[0]
    lo, hi = r.get("n", [1, 1])
    return [(r["item"], rng.randint(lo, hi))]


def guardian_table(profile, rng):
    return {"rich": "guardian_rich", "poor": "guardian_poor", "trap": "guardian_trap",
            "mixed": rng.choice(["guardian_normal", "guardian_rich", "guardian_poor"])}.get(profile, "guardian_normal")


def grant(ch, drops):
    """放進儲物袋，回傳訊息列表。"""
    if not drops:
        return []
    for item, n in drops:
        ch.add(item, n)
    txt = "、".join(f"{items.name(i)}×{n}" for i, n in drops)
    return [f"戰利品收入儲物袋：{txt}"]
