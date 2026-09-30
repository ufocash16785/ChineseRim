"""結局：全部任務完成後，依道心（殺業／善緣）與道侶決定結局，並附上旅程回顧。以 Mixin 併入 Session。"""
from . import karma, items


def ending_list(ch, data):
    return data.endings.get("campaign_endings", {}).get(getattr(ch, "campaign", "fanren")) or data.endings["endings"]


def pick_ending(ch, data):
    cfg = ending_list(ch, data)
    st = karma.dao_state(ch, data.karma)
    sha, ren = karma.get(ch, "sha"), karma.get(ch, "ren")
    for e in cfg:
        w = e["when"]
        if "state" in w and w["state"] != st:
            continue
        if sha < w.get("sha_min", 0) or ren < w.get("ren_min", 0):
            continue
        if w.get("companion") and not ch.companion:
            continue
        if w.get("companion_id") and ch.companion != w["companion_id"]:
            continue
        return e
    return cfg[-1]


class EndingMixin:
    def ending_check(self):
        """全部任務完成、對話與戰鬥都結束後，決定一次結局並存進存檔。"""
        h = self.hero
        if h.flags.get("ending") or self.battle or h.dialogue:
            return
        if not (h.quest.get("done") and quests_last(self.data, h)):
            return
        e = pick_ending(h, self.data)
        h.flags["ending"] = {"id": e["id"], "stats": self._ending_stats()}
        h.flags["ending_seen"] = False

    def _ending_stats(self):
        h, d = self.hero, self.data
        c = h.counters
        wars = [k for k, v in h.flags.items() if k.startswith("war_side:") and v]
        cand = self.cand_of(h.companion)["name"] if h.companion else None
        pet = f"{self.pet_name(h.pet)}（{h.pet['level']} 級）" if h.pet else None
        pup = f"{d.pets['puppets'][h.puppet['kind']]['name']}（{h.puppet['level']} 階）" if h.puppet else None
        bonded = h.flags.get("bonded")
        return {"day": self.day, "realm": self.rs.realm(h)["name"], "level": h.level, "sha": karma.get(h, "sha"), "ren": karma.get(h, "ren"),
                "dao": karma.view(h, d.karma)["dao"], "companion": cand, "sects": [d.sects[m]["name"] for m in h.members if m in d.sects],
                "pet": pet, "puppet": pup, "treasure": (f"{items.name(bonded)}（{h.counters.get('fbl:' + bonded, 0)} 階）" if bonded else None),
                "kills": c.get("kill:total", 0), "bosses": sum(1 for k in h.flags if k.startswith("beat:") and h.flags[k]) + sum(1 for k, v in c.items() if k.startswith("seen:boss:")),
                "wars_defend": sum(1 for k in wars if k.endswith(":defend")), "wars_attack": sum(1 for k in wars if k.endswith(":attack")),
                "alch": c.get("alch:n", 0), "codex": sum(1 for k in c if k.startswith("seen:beast:") and k.count(":") == 2) + sum(1 for k in c if k.startswith("seen:boss:")) + sum(1 for k in c if k.startswith("seen:pet:"))}

    def ending_view(self):
        h = self.hero
        info = h.flags.get("ending")
        if not info:
            return None
        cfg = self.data.endings
        e = next((x for x in ending_list(h, self.data) if x["id"] == info["id"]), None)
        if not e:
            return None
        s, ex = info["stats"], cfg["extras"]
        lines = [e["epilogue"]]
        if s["companion"]:
            lines.append(ex["companion"].format(name=s["companion"]))
        if s["sects"]:
            lines.append(ex["sects"].format(names="、".join(s["sects"])))
        if s["wars_defend"]:
            lines.append(ex["war_defend"].format(n=s["wars_defend"]))
        if s["wars_attack"]:
            lines.append(ex["war_attack"].format(n=s["wars_attack"]))
        if s["pet"]:
            lines.append(ex["pet"].format(name=s["pet"].split("（")[0], lv=s["pet"].split("（")[1].split(" ")[0]))
        if s["puppet"]:
            lines.append(ex["puppet"].format(name=s["puppet"].split("（")[0], lv=s["puppet"].split("（")[1].split(" ")[0]))
        if s["treasure"]:
            lines.append(ex["treasure"].format(name=s["treasure"].split("（")[0], lv=s["treasure"].split("（")[1].split(" ")[0]))
        if s["codex"]:
            lines.append(ex["codex"].format(n=s["codex"]))
        art = e.get("art") or e["id"]
        if e["id"] == "together" and h.companion in self.data.companions["candidates"]:
            art = f"together_{h.companion}"                   # 依實際的道侶換插圖
        return {"id": e["id"], "art": art, "title": e["title"], "subtitle": e["subtitle"], "paras": e["paras"], "epilogue": lines, "stats": s, "seen": bool(h.flags.get("ending_seen")),
                "all": [{"id": x["id"], "title": x["title"], "got": x["id"] == e["id"]} for x in ending_list(h, self.data)]}

    def _td_ending_close(self, **_):
        self.hero.flags["ending_seen"] = True


def quests_last(data, ch):
    from .quests import arc_order
    return arc_order(data, ch.campaign)[-1] == ch.quest.get("arc")
