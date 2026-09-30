"""遊戲工作階段：狀態、動作、任務、存檔。UI（web/cli）只負責呈現。"""
import json
import pathlib
import random
from dataclasses import asdict

from . import battle, dialogue, difficulty, karma, quests, treasures
from .character import Character
from .data import ROOT, GameData
from .elements import ADV_MULT, DIS_MULT, PAIRS, PARENT
from .explore import DEEP, WorldMap, is_wild, kill_reward, min_realm, visit
from .realms import RealmSystem
from .alchemy import AlchemyMixin
from .allies import AlliesMixin
from .events import EventsMixin
from .social import SocialMixin
from .topdown import TD_KINDS, TopDownMixin

SAVE_VERSION = 1
DEFAULT_SAVE = ROOT / "saves" / "save.json"


class Session(TopDownMixin, SocialMixin, AlchemyMixin, AlliesMixin, EventsMixin):
    def __init__(self, save_path=DEFAULT_SAVE, seed=None):
        self.data = GameData()
        self.rng = random.Random(seed)
        self.rs = RealmSystem(self.data, self.rng)
        self.rs.session = self
        self.world = WorldMap(self.data)
        self.save_path = pathlib.Path(save_path) if save_path else None
        self.rs.on("CR_OnRealmChanged", lambda actor, order, sub, old: self.log.append(f"★ 境界變更 → {self.data.realms[order]['name']}"))
        self.difficulty = difficulty.DEFAULT
        # 全新安裝（沒有存檔）時，前端會先叫出「難度＋角色」設定畫面
        self.new_game(configured=bool(self.save_path and self.save_path.exists()) if self.save_path else True)

    def create_hero(self, name=None, root=None, elems=None):
        """依靈根規則建立角色；資料不合法時回到原作設定（韓立·四靈根）。"""
        default = ("韓立", "quad", ["金", "木", "水", "火"])
        try:
            t = self.data.root_type(root or "quad")
            elems = list(elems or default[2]) if root else default[2]
            allowed = t.get("elements") or self.data.spirit_roots["elements"]
            if len(elems) != t["count"] or len(set(elems)) != len(elems) or any(e not in allowed for e in elems):
                raise ValueError("靈根屬性不符")
            return Character((name or default[0])[:12], elements=elems, root_type=t["id"], speed=t["speed"])
        except (KeyError, ValueError):
            return Character(*default[:1], elements=default[2], root_type=default[1])

    @property
    def dcfg(self):
        return difficulty.get(self.difficulty)

    def set_difficulty(self, name):
        self.difficulty = name if name in difficulty.DIFFICULTY else difficulty.DEFAULT
        self.rs.chance_bonus = self.dcfg["breakthrough"] + (self.perk_totals()["breakthrough"] if getattr(self, "hero", None) else 0)

    def new_game(self, name=None, root=None, elems=None, diff=None, configured=True):
        self.log = []
        self.set_difficulty(diff)
        self.configured = configured
        self.hero = self.create_hero(name, root, elems)
        self.rs.set_realm(self.hero, "mortal")
        self.hero.add("lingshi", self.dcfg["start_lingshi"])
        self.hero.add("mpill", self.dcfg["start_mpill"]) if self.dcfg["start_mpill"] else None
        self.day, self.region = 0, "tiannan"
        self.hero.add("heal", self.dcfg["start_heal"])
        self.log = ["你是青牛鎮少年韓立。走上地圖上的地點圖示就能進入；先去看看家鄉青牛鎮吧。"]
        quests.ensure(self.hero, self.data)
        self.ui = {}
        self.pending_boss = None
        self.alch = None
        self.td_reset()
        self.make_checkpoint("旅程起點")

    # ---- 存檔 ----
    def to_dict(self):
        return {"version": SAVE_VERSION, "day": self.day, "region": self.region, "log": self.log[-30:], "hero": asdict(self.hero), "difficulty": self.difficulty, "configured": self.configured,
                "td": {"mode": self.mode, "map_id": self.map_id, "pos": self.pos, "tp": getattr(self, "tp", 0), "cur_loc": self.cur_loc, "defeated": self.defeated,
                       "train_n": self.train_n, "step_acc": self.step_acc, "battle": self.battle, "checkpoint": self.checkpoint, "alch": self.alch}}

    def from_dict(self, d):
        if d.get("version") != SAVE_VERSION:
            raise ValueError(f"不支援的存檔版本 {d.get('version')}")
        hd = dict(d["hero"])
        hd.setdefault("max_mp", hd.get("mp", 20))
        self.hero = Character(**hd)
        self.day, self.region, self.log = d["day"], d["region"], d["log"]
        if self.region not in self.world.regions:
            raise ValueError("存檔區域不存在")
        self.ui = {}
        self.set_difficulty(d.get("difficulty"))
        self.configured = d.get("configured", True)
        td = d.get("td")
        if td and td["map_id"].split(":")[0] in ("world", "loc"):
            try:
                self.get_map(td["map_id"])
                self.mode, self.map_id, self.pos, self.cur_loc = td["mode"], td["map_id"], td["pos"], td["cur_loc"]
                self.defeated, self.train_n, self.step_acc, self.battle = td["defeated"], td["train_n"], td["step_acc"], td["battle"]
                self.alch = td.get("alch")
                self.checkpoint = td.get("checkpoint")
                if not self.checkpoint:
                    self.make_checkpoint("目前位置")
                return
            except (KeyError, StopIteration):
                pass
        self.td_reset()          # 舊版存檔（沒有地圖位置）

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
        self.pet_daily(days)
        self.events_notify(d0)
        for d in range(d0 + 1, self.day + 1):
            if d % 30 == 0:
                self.pay_stipends()
            if d % treasures.MOON_CYCLE_DAYS == 0:
                n = self.hero.count("lingye")
                treasures.tick_zhangtianping(self.rs, self.hero, d, 22)
                if self.hero.count("lingye") > n:
                    self.log.append(f"第 {d} 日月圓，掌天瓶凝出一滴靈液")

    def _after(self, loc=None, arrive=None):
        """任務推進與對話觸發。loc 為剛造訪的地點（用於地點型對話）。"""
        h = self.hero
        if (loc or arrive) and not h.dialogue:
            did = dialogue.find_trigger(self.data, h, loc, arrive)
            if did:
                dialogue.start(self.data, h, did, self.log, self.rs)
                # 簡報播完才開始累計；但這次造訪／抵達本身算數
                h.quest["baseline"] = dict(h.counters)
                k = f"visit:{loc}" if loc else f"arrive:{arrive}"
                h.quest["baseline"][k] = max(0, h.quest["baseline"].get(k, 0) - 1)
        self.log.extend(quests.update(self.data, h, self.rs))
        if not h.dialogue:
            did = dialogue.find_trigger(self.data, h)
            if did:
                dialogue.start(self.data, h, did, self.log, self.rs)

    def act(self, kind, **q):
        h = self.hero
        if kind == "choose":
            if h.dialogue:
                idx = int(q["i"]) if q.get("i") not in (None, "") else None
                dialogue.choose(self.data, h, idx, self.log, self.rs)
                self._after()
                self._maybe_boss()
                self.save()
            return
        if h.dialogue and kind not in ("new", "battle_end"):
            return          # 對話進行中，先做完對話（戰鬥結算畫面可關閉）
        if kind in TD_KINDS:
            self._td(kind, **q)
            if kind != "pos":
                self.log.extend([])
            self.save()
            return
        if q.get("hp") not in (None, ""):
            h.hp = max(1.0, min(h.max_hp, float(q["hp"])))    # 卷軸前端即時戰鬥的血量
        arrived = ok = None
        if kind == "kill":
            self.log.extend(kill_reward(self.rs, h, self.rng, q.get("loc", "total"), q.get("deep") == "1"))
        elif kind == "die":
            lost = min(self.dcfg["death_loss"], h.count("lingshi"))
            h.remove("lingshi", lost)
            h.hp = h.max_hp / 2
            self.log.append(f"你重傷倒下，被人救回，損失靈石 {lost}")
        elif kind == "travel":
            ok, days, msg = self.world.travel(h, self.region, q["to"])
            self.log.append(msg + (f"（耗時 {days} 日）" if ok else ""))
            if ok:
                self.region = q["to"]
                key = f"arrive:{q['to']}"
                h.counters[key] = h.counters.get(key, 0) + 1
                self.advance(days)
                arrived = q["to"]
        elif kind == "visit":
            msgs, days = visit(self.world, self.rs, h, self.region, q["loc"], self.rng, fight_wild=q.get("nofight") != "1")
            self.log.extend(msgs)
            self.advance(days)
        elif kind == "break":
            self.try_break()
            self._after()
            self.save()
            return
        elif kind == "refine":
            self.log.append("青竹蜂雲劍祭煉成功" if treasures.refine(self.rs, h, "qingzhu_fengyunjian") else "祭煉條件不足（築基以上＋靈石）")
        elif kind == "rest":
            h.hp = h.max_hp
            self.advance(7)
            self.log.append("閉關 7 日，傷勢痊癒")
        elif kind == "new":
            self.new_game(q.get("name"), q.get("root"), list(q["elems"]) if q.get("elems") else None, q.get("diff"))
            self.save()
            return
        self._after(q.get("loc") if kind == "visit" else None, arrived if kind == "travel" and ok else None)
        self.save()

    def combat_bonus(self):
        """已學功法的戰鬥加成總和。"""
        out = {"regen": 0.0, "maxHp": 0.0, "slashDmg": 0.0, "allDmg": 0.0, "critChance": 0.0, "elemDmg": {}}
        for gid in self.hero.gongfa:
            c = self.data.gongfa.get(gid, {}).get("combat", {})
            for k in ("regen", "maxHp", "slashDmg", "allDmg", "critChance"):
                out[k] += c.get(k, 0.0)
            for el, v in c.get("elemDmg", {}).items():
                out["elemDmg"][el] = out["elemDmg"].get(el, 0.0) + v
        pt = self.perk_totals()
        for k in ("allDmg", "slashDmg", "critChance"):
            out[k] += pt[k]
        for el, v in pt["elemDmg"].items():
            out["elemDmg"][el] = out["elemDmg"].get(el, 0.0) + v
        return out

    def karma_view(self):
        ev = self.karma_now()
        return {"kind": ev["kind"], "name": ev["name"], "sprite": ev["sprite"], "x": ev["x"], "y": ev["y"]} if ev else None

    def shady_view(self):
        if self.mode != "loc":
            return None
        sh = self.shady_now(self.cur_loc)
        return {"x": sh["x"], "y": sh["y"]} if sh else None

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
            "elem": {"adv": ADV_MULT, "dis": DIS_MULT, "parent": PARENT, "pairs": PAIRS},
            "dialogue": dialogue.view(self.data, h),
            "difficulty": self.difficulty, "difficultyName": self.dcfg["name"], "configured": self.configured, "difficulties": {k: {"name": v["name"], "desc": v["desc"]} for k, v in difficulty.DIFFICULTY.items()},
            "mode": self.mode, "map_id": self.map_id, "pos": self.pos, "tp": getattr(self, "tp", 0), "cur_loc": self.cur_loc, "defeated": self.defeated,
            "battle": battle.view(self.battle, h), "bag": self.bag_view(), "news": self.news_view(), "war": self.war_view(), "wev_ent": self.wev_entity(), "comp": self.allies_view(), "alch": self.alch_view(), "alch_n": h.counters.get("alch:n", 0), "karma": karma.view(h, self.data.karma), "karma_ev": self.karma_view(), "checkpoint": (self.checkpoint or {}).get("label"), "guardians": [k[9:] for k, v in h.flags.items() if k.startswith("guardian:") and v], "shop": self.shop_view(), "board": self.board_view(), "cand": self.cand_view(), "shady": self.shady_view(),
            "members": [{"id": m, "name": self.data.sects[m]["name"], "perk": self.perk_of(m)["name"], "desc": self.perk_of(m)["desc"]} for m in h.members],
            "partner": self.partner_spec(), "affinity": h.affinity, "mp": round(h.mp), "max_mp": round(h.max_mp), "heal": h.count("heal"), "mpills": h.count("mpill"), "herbs": h.count("herb"), "plots": self.plots_view(),
            "seeds": {k: dict(v, cost=round(v["cost"] * self.dcfg["price"])) for k, v in self.data.farming["seeds"].items()},
            "recipes": {k: dict(v, needs={n: (round(c * self.dcfg["price"]) if n == "lingshi" else c) for n, c in v["needs"].items()}) for k, v in self.data.farming["recipes"].items()}, "prices": {k: round(v["price"] * self.dcfg["price"]) for k, v in self.data.market["shops"]["shop"]["items"].items()},
            "questNpc": dialogue.pending_npc(self.data, h, self.cur_loc) if self.mode == "loc" else None,
            "opened": [k.split(":", 3)[3] for k in h.flags if k.startswith(f"chest:{self.map_id}:")],
            "region": self.region, "region_name": reg["name"], "gongfa": [{"id": g, "name": self.data.gongfa[g]["name"]} for g in h.gongfa if g in self.data.gongfa],
            "combat": self.combat_bonus(),
            "roots": self.data.spirit_roots["types"], "root_type": h.root_type, "root_elements": self.data.spirit_roots["elements"],
            "quest": quests.view(self.data, h), "target": quests.target(self.data, h),
            "world": [{"id": g["id"], "name": g["name"], "x": g["coords"][0], "y": g["coords"][1], "world": g["world_name"],
                       "locked": not w.can_enter(h, g["id"]), "days": w.travel_days(h, self.region, g["id"])}
                      for g in w.regions.values()],
            "locations": [{"id": l["id"], "name": l["name"], "type": l["type"], "wild": is_wild(l["type"]), "deep": l["type"] in DEEP, "min_realm": min_realm(l["id"], l), "note": l.get("note", ""), "x": x, "y": y}
                          for l, x, y in w.location_layout(self.region)],
        }
