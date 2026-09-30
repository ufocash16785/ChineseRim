"""因果與道心：殺業（sha）與善緣（ren）記在 Character.counters，決定仇家／故人事件與心魔劫的樣貌。"""
import random


def get(ch, kind):
    return ch.counters.get("karma:" + kind, 0)


def add(ch, kind, n, log=None):
    old = get(ch, kind)
    ch.counters["karma:" + kind] = max(0, old + n)
    if log is not None and n:
        name = "殺業" if kind == "sha" else "善緣"
        log.append(f"因果：{name} {'+' if n > 0 else ''}{n}（現為 {ch.counters['karma:' + kind]}）")


def dao_state(ch, cfg):
    sha, ren, th = get(ch, "sha"), get(ch, "ren"), cfg["thresholds"]["heavy"]
    if sha >= ren + th:
        return "sha"
    if ren >= sha + th:
        return "ren"
    return "mid"


DAO_NAME = {"sha": "殺伐", "ren": "仁厚", "mid": "中正"}


def view(ch, cfg):
    st = dao_state(ch, cfg)
    return {"sha": get(ch, "sha"), "ren": get(ch, "ren"), "dao": DAO_NAME[st], "state": st}


def xinmo_spec(data, ch):
    """心魔的樣貌由道心決定。"""
    v = data.karma["xinmo"][dao_state(ch, data.karma)]
    base = data.bosses["bosses"]["xinmo"]
    spec = dict(base)
    spec.update({"name": v["name"], "hp_mult": v["hp_mult"], "atk_mult": v["atk_mult"], "skills": v["skills"], "el": "@hero",
                 "intro": v["intro"], "karma": {k[7:]: n for k, n in v.items() if k.startswith("on_win_")}})
    return spec


def event_at(data, ch, loc, day, wild):
    """這個地點此刻有沒有因果事件？決定性：每 period_days 日重新抽籤。回傳 {kind, name, sprite, key} 或 None。"""
    if not wild:
        return None
    cfg = data.karma
    period = day // cfg["period_days"]
    r = random.Random(f"karma|{loc}|{period}|{get(ch, 'sha')}|{get(ch, 'ren')}")
    kinds = []
    if get(ch, "sha") >= cfg["thresholds"]["avenger"]:
        kinds.append("avenger")
    if get(ch, "ren") >= cfg["thresholds"]["benefactor"]:
        kinds.append("benefactor")
    r.shuffle(kinds)
    for k in kinds:
        if r.random() < cfg["event_chance"][k]:
            key = f"kev:{loc}:{period}"
            if ch.flags.get(key):
                return None
            c = cfg[k]
            return {"kind": k, "name": r.choice(c["names"]), "sprite": r.choice(c["sprites"]), "key": key, "el": r.choice(cfg["avenger"]["el"])}
    return None
