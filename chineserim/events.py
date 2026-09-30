"""世界動態事件：每個時間窗（預設 8 日）各區域抽出幾件，玩家可以參與、也可以無視。以 Mixin 併入 Session。"""
import random

from . import karma, loot
from .character import item_name
from .mapgen import loc_category


class EventsMixin:
    _loc_cache = None

    def _locs_by_region(self):
        if self._loc_cache is None:
            self._loc_cache = {g["id"]: [{"id": l["id"], "name": l["name"].split("（")[0], "cat": loc_category(l["type"])} for l in g["locations"]]
                               for w in self.data.regions for g in w["regions"]}
        return self._loc_cache

    def _wseed(self):
        c = self.hero.counters
        if "wseed" not in c:
            c["wseed"] = self.rng.randrange(1, 10 ** 6)
        return c["wseed"]

    def window(self, day=None):
        return (self.day if day is None else day) // self.data.events["window_days"]

    def events_in(self, region, window=None):
        """該區域此時間窗的事件（決定性）。回傳 dict 列表（含 resolved 狀態）。"""
        cfg = self.data.events
        w = self.window() if window is None else window
        r = random.Random(f"wev|{self._wseed()}|{w}|{region}")
        locs = self._locs_by_region().get(region, [])
        out, used = [], set()
        types = list(cfg["types"])
        for _ in range(cfg["per_region"] * 3):
            if len(out) >= cfg["per_region"]:
                break
            t = r.choices(types, weights=[cfg["types"][x]["weight"] for x in types])[0]
            tc = cfg["types"][t]["cat"]
            pool = [l for l in locs if l["id"] not in used and (l["cat"] in ("wild", "deep") if tc == "any_wild" else l["cat"] == tc)]
            if not pool:
                continue
            l = r.choice(pool)
            used.add(l["id"])
            eid = f"{w}:{l['id']}:{t}"
            out.append({"id": eid, "type": t, "loc": l["id"], "loc_name": l["name"], "window": w, "kind": cfg["types"][t]["kind"], "title": cfg["types"][t]["title"],
                        "text": cfg["types"][t]["text"].format(loc=l["name"]), "resolved": bool(self.hero.flags.get("wev:" + eid)),
                        "left": (w + 1) * cfg["window_days"] - self.day})
        return out

    def event_at(self, loc):
        for e in self.events_in(self.region):
            if e["loc"] == loc:
                return e
        return None

    def wev_mod(self, loc, key, default=1.0):
        """該地點目前的規則修正（獸潮／盛會／盜匪／秘境異動）。"""
        e = self.event_at(loc) if loc else None
        if not e:
            return default
        tc = self.data.events["types"][e["type"]]
        if e["kind"] == "entity" and e["resolved"]:
            return default
        return tc.get(key, default)

    def wev_entity(self):
        """目前地圖上要顯示的事件人物（entity 型且尚未處理）。"""
        if self.mode != "loc":
            return None
        e = self.event_at(self.cur_loc)
        if not e or e["kind"] != "entity" or e["resolved"]:
            return None
        tc = self.data.events["types"][e["type"]]
        m = self.get_map(self.map_id)
        r = random.Random(f"wpos|{e['id']}")
        x, y = r.choice(m.get("spots") or [m["npcSpot"]])
        names = tc.get("names") or [e["title"]]
        return {"id": e["id"], "type": e["type"], "name": r.choice(names), "sprite": (r.choice(tc["sprites"]) if tc.get("sprites") else None), "x": x, "y": y, "label": tc.get("label", "!")}

    def news_view(self):
        out = []
        for e in self.events_in(self.region):
            out.append({"loc": e["loc"], "loc_name": e["loc_name"], "title": e["title"], "text": e["text"], "left": e["left"], "kind": e["kind"], "resolved": e["resolved"]})
        return out

    def events_notify(self, d0):
        """日期跨入新時間窗時，把當地傳聞寫進紀錄。"""
        if self.window(d0) != self.window():
            for e in self.events_in(self.region):
                self.log.append("📰 傳聞：" + e["text"])

    def _talk_wev(self):
        ent = self.wev_entity()
        h = self.hero
        if not ent:
            return
        e = self.event_at(self.cur_loc)
        tc = self.data.events["types"][e["type"]]
        key = "wev:" + e["id"]
        if e["type"] == "refugee":
            cost = round(tc["cost"] * self.dcfg["price"])
            self.log.append(f"「{ent['name']}」{tc['greet']}")
            if not h.remove("lingshi", cost):
                self.log.append(f"（你身上的靈石不夠 {cost} 顆。）")
                return
            g = self.rng.choice(tc["gifts"])
            h.add(g["item"], g["n"])
            self.log.append(f"你資助了他們 {cost} 靈石。對方千恩萬謝，硬塞給你 {item_name(g['item'])}×{g['n']}。")
            karma.add(h, "ren", tc["reward_ren"], self.log)
            h.flags[key] = True
        elif e["type"] == "fall":
            drops = loot.roll_table(self.data, tc["table"], h, self.rng, self.dcfg["chest"])
            self.log.append("你循著流星的軌跡，在焦黑的土坑裡找到了一塊尚有餘溫的異寶。")
            self.log.extend(loot.grant(h, drops))
            h.flags[key] = True
        elif e["type"] == "raid":
            self.log.append(f"「{ent['name']}」{tc['greet']}")
            spec = {"name": ent["name"], "sprite": ent["sprite"], "el": self.rng.choice("金木水火土"), "hp_mult": tc["hp_mult"], "atk_mult": tc["atk_mult"],
                    "skills": tc["skills"], "drops": tc["drops"], "on_win": [{"flag": key}], "loot": 3.0, "karma": {"ren": tc["reward_ren"]}}
            self.start_boss_fight("wev_raid", None, spec)
