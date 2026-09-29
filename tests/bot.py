"""測試用機器人：只透過 Session.act 玩遊戲，直到最後一個任務完成。"""


def region_of(data, loc):
    for w in data.regions:
        for g in w["regions"]:
            if any(l["id"] == loc for l in g["locations"]):
                return g["id"]
    raise KeyError(loc)


def _quest_ids(data, h):
    arc = next(a for a in data.arcs if a["id"] == h.quest["arc"])
    return arc["quests"][h.quest["q"]]["id"]


def play_through(s, limit=3000, pick=None):
    """pick(choices)->選項 index；預設永遠選第一個。"""
    h, d = s.hero, s.data
    steps = 0

    def go(loc):
        r = region_of(d, loc)
        if s.region != r:
            s.act("travel", to=r)
            if s.region != r:
                raise AssertionError(f"無法前往 {r}（境界 {h.realm}）")
        s.act("visit", loc=loc, nofight="1")

    def grind(n=1, loc="grind"):
        for _ in range(n):
            s.act("kill", loc=loc, deep="0", hp=str(h.max_hp))

    while not (h.quest["done"] and not h.dialogue) and steps < limit:
        steps += 1
        if h.dialogue:
            v = s.snapshot()["dialogue"]
            s.act("choose", i=(pick(v["choices"]) if pick else v["choices"][0]["i"]) if v["choices"] else "")
            continue
        if h.quest["done"]:
            # 最後一卷完成，但還有 onQuestDone 對話未觸發
            s._after()
            continue
        qid = _quest_ids(d, h)
        rule = d.quest_rules[h.quest["arc"]][qid]
        cond = rule["objectives"][h.quest["o"]]
        gate = next((x["trigger"] for k, x in d.dialogues.items()
                     if not h.flags.get("seen:" + k) and x["trigger"].get("quest") == qid and x["trigger"].get("obj") == h.quest["o"]), None)
        if gate:
            if "arrive" in gate:
                s.act("travel", to=gate["arrive"])
                if s.region != gate["arrive"]:          # 已在該區域：先離開再回來
                    raise AssertionError("arrive 觸發失敗")
            else:
                go(gate["loc"])
            continue
        t = cond["type"]
        if t == "visit":
            go(cond["loc"])
        elif t == "kill":
            grind(1, cond["loc"])
        elif t == "arrive":
            if s.region == cond["loc"]:
                other = next(g for g in s.world.regions if g != cond["loc"] and s.world.can_enter(h, g))
                s.act("travel", to=other)
            s.act("travel", to=cond["loc"])
        elif t == "level":
            grind()
        elif t == "realm":
            if s.rs.at_bottleneck(h):
                if not h.count("pill"):
                    h.add("pill")
                h.hp = h.max_hp
                s.act("break")
            else:
                grind()
        elif t == "item":
            h.add(cond["item"], cond.get("n", 1))
            s._after()
        elif t == "treasure":
            h.add("lingshi", 500)
            s.act("refine")
        elif t == "flag":
            raise AssertionError(f"flag {cond['flag']} 沒有對應對話可設定 {qid}")
    return steps
