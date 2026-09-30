"""圖錄：沒有圖錄就不知道妖獸／靈寵的知識；條目要親身遇過（養過）才會解鎖。以 Mixin 併入 Session。"""
from .elements import element_multiplier


def has_beast_book(ch, data):
    return ch.count(data.codex["beast_book"]) > 0


def has_pet_book(ch, data):
    return ch.count(data.codex["pet_book"]) > 0


def weak_elements(el):
    return [x for x in "金木水火土" if element_multiplier(x, el) > 1]


class CodexMixin:
    def codex_see_beast(self, kind, el=None):
        c = self.hero.counters
        c["seen:beast:" + kind] = c.get("seen:beast:" + kind, 0) + 1
        if el:
            c[f"seen:beast:{kind}:{el}"] = 1

    def codex_see_boss(self, bid):
        c = self.hero.counters
        c["seen:boss:" + bid] = c.get("seen:boss:" + bid, 0) + 1

    def codex_see_pet(self, kind):
        self.hero.counters["seen:pet:" + kind] = 1

    def codex_view(self):
        h, cx = self.hero, self.data.codex
        c = h.counters
        out = {"beast": {"owned": has_beast_book(h, self.data)}, "pet": {"owned": has_pet_book(h, self.data)}}
        if out["beast"]["owned"]:
            ents = []
            for kind, b in cx["beasts"].items():
                n = c.get("seen:beast:" + kind, 0)
                if not n:
                    ents.append({"id": kind, "known": False})
                    continue
                els = [e for e in "金木水火土" if c.get(f"seen:beast:{kind}:{e}")]
                ents.append({"id": kind, "known": True, "name": b["name"], "desc": b["desc"], "habitat": b["habitat"], "tip": b["tip"], "seen": n,
                             "elements": [{"el": e, "weak": weak_elements(e)} for e in els]})
            bosses = []
            for bid, b in cx["bosses"].items():
                n = c.get("seen:boss:" + bid, 0)
                bb = self.data.bosses["bosses"][bid]
                if not n:
                    bosses.append({"id": bid, "known": False})
                    continue
                el = bb["el"] if bb["el"] != "@hero" else "（隨你的靈根）"
                bosses.append({"id": bid, "known": True, "name": bb["name"], "lore": b["lore"], "tip": b["tip"], "el": el, "seen": n,
                               "weak": weak_elements(el) if el in "金木水火土" and el else [], "skills": [f"{s['name']}（每 {s['every']} 回合，傷害 ×{s['mult']}）" for s in bb["skills"]]})
            out["beast"].update({"entries": ents, "bosses": bosses, "found": sum(1 for e in ents if e["known"]) + sum(1 for b in bosses if b["known"]), "total": len(ents) + len(bosses)})
        if out["pet"]["owned"]:
            pc = self.data.pets
            ents = []
            for kind, stages in pc["pets"].items():
                if not c.get("seen:pet:" + kind):
                    ents.append({"id": kind, "known": False})
                    continue
                sk = pc["skills"][kind]
                pct = lambda v: round(v * 100) if sk["type"] in ("howl", "shield", "drain", "web") else v
                ents.append({"id": kind, "known": True, "stages": stages, "tip": cx["pet_tips"][kind],
                             "skill": {"name": sk["name"], "desc": sk["desc"].format(pct=pct(sk["val"][0])), "strong": sk["desc"].format(pct=pct(sk["val"][1])),
                                       "unlock": pc["stage_levels"][pc["skill_unlock_stage"] - 1], "cd": pc["skill_cd"]}})
            out["pet"].update({"entries": ents, "found": sum(1 for e in ents if e["known"]), "total": len(ents)})
        return out
