"""遊戲工作階段：狀態、動作、任務、存檔。UI（web/cli）只負責呈現。"""
import json
import pathlib
import random
from dataclasses import asdict

from . import dialogue, quests, treasures
from .character import Character
from .data import ROOT, GameData
from .explore import WorldMap, visit
from .realms import RealmSystem

SAVE_VERSION = 1
DEFAULT_SAVE = ROOT / "saves" / "save.json"


class Session:
    def __init__(self, save_path=DEFAULT_SAVE, seed=None):
        self.data = GameData()
        self.rng = random.Random(seed)
        self.rs = RealmSystem(self.data, self.rng)
        self.world = WorldMap(self.data)
        self.save_path = pathlib.Path(save_path) if save_path else None
        self.rs.on("CR_OnRealmChanged", lambda actor, order, sub, old: self.log.append(f"★ 境界變更 → {self.data.realms[order]['name']}"))
        self.new_game()

    def new_game(self):
        self.log = []
        self.hero = Character("韓立", elements=["金", "木", "水", "火"], root_type="quad")
        self.rs.set_realm(self.hero, "mortal")
        self.hero.add("lingshi", 500)
        self.day, self.region = 0, "tiannan"
        self.log = ["你是青牛鎮少年韓立。點區域旅行、點地點探索；先去看看家鄉青牛鎮吧。"]
        quests.ensure(self.hero)

    # ---- 存檔 ----
    def to_dict(self):
        return {"version": SAVE_VERSION, "day": self.day, "region": self.region, "log": self.log[-30:], "hero": asdict(self.hero)}

    def from_dict(self, d):
        if d.get("version") != SAVE_VERSION:
            raise ValueError(f"不支援的存檔版本 {d.get('version')}")
        self.hero = Character(**d["hero"])
        self.day, self.region, self.log = d["day"], d["region"], d["log"]
        if self.region not in self.world.regions:
            raise ValueError("存檔區域不存在")

    def save(self):
        if not self.save_path:
            return False
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.save_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.save_path)
        return True

    def load(self):
        if not self.save_path or not self.save_path.exists():
            return False
        self.from_dict(json.loads(self.save_path.read_text(encoding="utf-8")))
        return True

    # ---- 動作 ----
    def advance(self, days):
        d0 = self.day
        self.day += days
        for d in range(d0 + 1, self.day + 1):
            if d % treasures.MOON_CYCLE_DAYS == 0:
                n = self.hero.count("lingye")
                treasures.tick_zhangtianping(self.rs, self.hero, d, 22)
                if self.hero.count("lingye") > n:
                    self.log.append(f"第 {d} 日月圓，掌天瓶凝出一滴靈液")

    def _after(self, loc=None):
        """任務推進與對話觸發。loc 為剛造訪的地點（用於地點型對話）。"""
        h = self.hero
        if loc and not h.dialogue:
            did = dialogue.find_trigger(self.data, h, loc)
            if did:
                dialogue.start(self.data, h, did, self.log)
                # 簡報播完才開始累計；但這次造訪本身算數
                h.quest["baseline"] = dict(h.counters)
                k = f"visit:{loc}"
                h.quest["baseline"][k] = max(0, h.quest["baseline"].get(k, 0) - 1)
        self.log.extend(quests.update(self.data, h))
        if not h.dialogue:
            did = dialogue.find_trigger(self.data, h)
            if did:
                dialogue.start(self.data, h, did, self.log)

    def act(self, kind, **q):
        h = self.hero
        if kind == "choose":
            if h.dialogue:
                idx = int(q["i"]) if q.get("i") not in (None, "") else None
                dialogue.choose(self.data, h, idx, self.log)
                self._after()
                self.save()
            return
        if h.dialogue and kind != "new":
            return          # 對話進行中，先做完對話
        if kind == "travel":
            ok, days, msg = self.world.travel(h, self.region, q["to"])
            self.log.append(msg + (f"（耗時 {days} 日）" if ok else ""))
            if ok:
                self.region = q["to"]
                self.advance(days)
        elif kind == "visit":
            msgs, days = visit(self.world, self.rs, h, self.region, q["loc"], self.rng)
            self.log.extend(msgs)
            self.advance(days)
        elif kind == "break":
            ok = self.rs.attempt_breakthrough(h, "pill" if h.count("pill") else None)
            self.log.append("突破成功！" if ok else "突破失敗或尚未到瓶頸（失敗損失一半 HP）")
        elif kind == "refine":
            self.log.append("青竹蜂雲劍祭煉成功" if treasures.refine(self.rs, h, "qingzhu_fengyunjian") else "祭煉條件不足（築基以上＋靈石）")
        elif kind == "rest":
            h.hp = h.max_hp
            self.advance(7)
            self.log.append("閉關 7 日，傷勢痊癒")
        elif kind == "new":
            self.new_game()
            self.save()
            return
        self._after(q.get("loc") if kind == "visit" else None)
        self.save()

    def snapshot(self):
        h, w = self.hero, self.world
        r = self.rs.realm(h)
        reg = w.regions[self.region]
        return {
            "name": h.name, "realm": r["name"], "sub": r["sub"][h.sub], "level": h.level, "cap": r["levelRange"][1],
            "hp": round(h.hp), "max_hp": h.max_hp, "mp": h.mp, "elements": h.elements,
            "lingshi": h.count("lingshi"), "lingye": h.count("lingye"), "pills": h.count("pill"),
            "day": self.day, "treasures": h.treasures, "sects": {self.data.sects[k]["name"]: v for k, v in h.sects.items()},
            "bottleneck": self.rs.at_bottleneck(h), "log": self.log[-14:], "realm_index": h.realm,
            "realms": [x["name"] for x in self.data.realms[:6]],
            "dialogue": dialogue.view(self.data, h),
            "region": self.region, "region_name": reg["name"], "quest": quests.view(self.data, h),
            "world": [{"id": g["id"], "name": g["name"], "x": g["coords"][0], "y": g["coords"][1], "world": g["world_name"],
                       "locked": not w.can_enter(h, g["id"]), "days": w.travel_days(h, self.region, g["id"])}
                      for g in w.regions.values()],
            "locations": [{"id": l["id"], "name": l["name"], "type": l["type"], "note": l.get("note", ""), "x": x, "y": y}
                          for l, x, y in w.location_layout(self.region)],
        }
