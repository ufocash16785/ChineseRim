"""俯視地圖版機器人：只透過 enter/talk/battle/region/ferry/portal/leave 動作玩到最後一個任務。"""
from tests.bot import region_of


def play_through_td(s, limit=4000, pick=None):
    h, d = s.hero, s.data
    steps = 0
    loc_type = {l["id"]: l["type"] for w in d.regions for g in w["regions"] for l in g["locations"]}
    from chineserim.explore import DEEP, is_wild
    wild_of = {g["id"]: [l["id"] for l in g["locations"] if is_wild(l["type"]) and "profile" not in l]
               for w in d.regions for g in w["regions"]}

    def settle():
        while h.dialogue:
            v = s.snapshot()["dialogue"]
            s.act("choose", i=(pick(v["choices"]) if pick else v["choices"][0]["i"]) if v["choices"] else "")

    def goto_region(r):
        settle()
        if s.region == r:
            return
        if s.mode == "loc":
            s.act("leave")
        settle()
        if r == "tianyuan":
            goto_region("tiannan")
            settle()
            s.act("enter", loc="jixi")
            settle()
            s.act("portal")
            assert s.region == "tianyuan", "portal failed"
            return
        if s.region == "luanxinghai":            # 島上只能搭船回天南
            s.act("ferry", to="tiannan")
            settle()
            if r != "tiannan":
                s.act("region", to=r)
        elif r == "luanxinghai":
            goto_region("tiannan")
            s.act("ferry", to=r)
        else:
            s.act("region", to=r)
        settle()
        assert s.region == r, f"cannot reach {r} from {s.region}"

    def enter(loc):
        goto_region(region_of(d, loc))
        settle()
        if s.mode == "loc" and s.cur_loc != loc:
            s.act("leave")
        if s.mode != "loc":
            s.act("enter", loc=loc)
        assert s.mode == "loc" and s.cur_loc == loc, f"enter {loc} failed (realm {h.realm})"

    def fight_all(max_fights=3):
        settle()
        m = s.get_map(s.map_id)
        for e in [e for e in m["entities"] if e["k"] == "enemy"][:max_fights]:
            settle()
            if e["id"] in s.defeated or (h.quest["done"]):
                continue
            h.hp, h.mp = h.max_hp, h.max_mp
            h.add("heal", 1)
            s.act("battle_start", ids=e["id"])
            assert s.battle, "battle did not start"
            for _ in range(80):
                if not s.battle or s.battle["over"]:
                    break
                cost = 4 if s.battle["deep"] else 0
                if h.hp < .4 * h.max_hp and h.count("heal"):
                    s.act("battle", cmd="item")
                elif h.mp >= max(4, round(h.max_mp * .1)):
                    s.act("battle", cmd="spell", arg=0)
                else:
                    s.act("battle", cmd="attack")
            s.act("battle_end")

    def grind(loc=None):
        loc = loc or (wild_of[s.region][0] if wild_of.get(s.region) else None)
        if not loc:
            loc = wild_of["tiannan"][0]
        enter(loc)
        fight_all(1)
        s.act("leave")

    while not (h.quest["done"] and not h.dialogue) and steps < limit:
        steps += 1
        if h.dialogue:
            v = s.snapshot()["dialogue"]
            s.act("choose", i=(pick(v["choices"]) if pick else v["choices"][0]["i"]) if v["choices"] else "")
            continue
        if h.quest["done"]:
            s._after()
            continue
        qid = s.data.arcs and next(a for a in d.arcs if a["id"] == h.quest["arc"])["quests"][h.quest["q"]]["id"]
        cond = d.quest_rules[h.quest["arc"]][qid]["objectives"][h.quest["o"]]
        gate = next((x["trigger"] for k, x in d.dialogues.items()
                     if not h.flags.get("seen:" + k) and x["trigger"].get("quest") == qid and x["trigger"].get("obj") == h.quest["o"]), None)
        if gate:
            if "arrive" in gate:
                if s.region == gate["arrive"]:
                    goto_region("tiannan" if gate["arrive"] != "tiannan" else "mulan")
                goto_region(gate["arrive"])
            else:
                enter(gate["loc"])
                if s.snapshot()["questNpc"]:
                    s.act("talk", ent="quest")
                s.act("leave") if s.mode == "loc" and not h.dialogue else None
            continue
        t = cond["type"]
        if t == "visit":
            enter(cond["loc"])
            s.act("leave") if not h.dialogue else None
        elif t == "kill":
            if cond["loc"] == "total":
                grind()
            else:
                enter(cond["loc"])
                fight_all(3)
                s.act("leave") if not h.dialogue else None
        elif t == "arrive":
            if s.region == cond["loc"]:
                goto_region("mulan" if cond["loc"] != "mulan" else "tiannan")
            goto_region(cond["loc"])
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
            raise AssertionError(f"flag {cond['flag']} 無對應對話 {qid}")
    return steps
