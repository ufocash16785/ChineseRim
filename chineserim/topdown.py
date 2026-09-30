"""俯視地圖模式：大地圖行走、進出地點、NPC 互動、遭遇戰。以 Mixin 形式併入 Session。"""
import json
from dataclasses import asdict

from . import battle, dialogue, items, loot, mapgen, quests
from .character import Character
from .character import item_name
from .explore import DEEP, min_realm

_MAP_CACHE = {}          # 地圖只由資料決定，行程內共用（唯讀）
TD_KINDS = {"sell", "appraise", "barter", "join", "board_close", "gift", "chat", "cand_close", "plant", "harvest", "boost", "craft", "shop_close", "enter", "leave", "talk", "region", "ferry", "pos", "battle_start", "battle", "battle_end", "buy", "chest", "portal", "use"}
STEPS_PER_DAY = 160
FERRY_DAYS = 8


SAFE_CATS = ("town", "sect", "garden", "dwelling")


class TopDownMixin:
    ui = {}
    pending_boss = None
    checkpoint = None

    # ---- 儲存點（死亡時回到這裡）----
    def make_checkpoint(self, label):
        self.checkpoint = {"label": label, "hero": json.loads(json.dumps(asdict(self.hero))), "day": self.day, "region": self.region, "mode": self.mode,
                           "map_id": self.map_id, "cur_loc": self.cur_loc, "pos": [round(self.pos[0], 2), round(self.pos[1], 2)]}

    def _restore_checkpoint(self):
        cp = self.checkpoint
        self.hero = Character(**dict(cp["hero"]))
        self.day, self.region, self.mode, self.map_id, self.cur_loc = cp["day"], cp["region"], cp["mode"], cp["map_id"], cp["cur_loc"]
        self.hero.hp, self.hero.mp = self.hero.max_hp, self.hero.max_mp
        self.defeated, self.battle, self.ui, self.pending_boss = [], None, {}, None
        self._teleport(*cp["pos"])
        self.log.append(f"你重傷不治……再睜開眼，已回到上一個儲存點「{cp['label']}」。")

    # ---- 主要對手 ----
    def start_boss_fight(self, bid, did=None, spec=None):
        h = self.hero
        b = dict(spec or self.data.bosses["bosses"][bid])
        deep = self.mode == "loc" and self.get_map(self.map_id)["cat"] == "deep"
        self.battle = battle.start_boss(h, b, self.cur_loc or "total", deep, self.dcfg, self.partner_spec(), boss_id=bid, retry=did)

    def _maybe_boss(self):
        pb = self.pending_boss
        if pb and not self.hero.dialogue and not self.battle:
            self.pending_boss = None
            self.start_boss_fight(pb["id"], pb["did"])

    def _start_guardian(self, e):
        g = self.data.bosses["guardian"]
        spec = {"name": e["name"], "kind": e["kind"], "el": e["el"], "hp_mult": g["hp_mult"], "atk_mult": g["atk_mult"], "skills": g["skills"],
                "drops": loot.guardian_table(e.get("profile", "normal"), self.rng), "on_win": [{"flag": "guardian:" + self.cur_loc}], "loot": 3.0}
        self.start_boss_fight("guardian", None, spec)

    def bag_view(self):
        h, reg = self.hero, items.registry()
        out = []
        for iid, n in h.inventory.items():
            if n > 0:
                out.append({"id": iid, "name": items.name(iid), "cat": items.cat(iid), "n": n, "desc": (reg["items"].get(iid) or {}).get("desc", ""), "use": (reg["items"].get(iid) or {}).get("use")})
        if loot.owned(h, "fb_qingzhu"):
            out.append({"id": "fb_qingzhu", "name": items.name("fb_qingzhu"), "cat": "法寶", "n": 1, "desc": reg["items"]["fb_qingzhu"]["desc"], "use": None})
        order = {c: i for i, c in enumerate(reg["cats"])}
        out.sort(key=lambda x: (order.get(x["cat"], 99), x["id"]))
        return out

    def _td_use(self, item="", **_):
        h = self.hero
        if h.count(item) <= 0:
            return
        u = (items.info(item) or {}).get("use")
        if u == "heal":
            h.remove(item)
            h.hp = min(h.max_hp, h.hp + h.max_hp * battle.HEAL_FRAC)
            self.log.append("服下回春丹，氣血回復了。")
        elif u == "mpill":
            h.remove(item)
            h.mp = min(h.max_mp, h.mp + h.max_mp * 0.5)
            self.log.append("服下聚氣丹，靈力恢復了一半。")
        else:
            self.log.append(f"{items.name(item)}要在對應的時機使用（符錄、陣法與法寶只能在主要對手戰中使用）。")

    # ---- 地圖 ----
    def get_map(self, map_id):
        cache = _MAP_CACHE
        if map_id not in cache:
            kind, _, name = map_id.partition(":")
            if kind == "world":
                cache[map_id] = mapgen.build_world(self.data, name)
            elif kind == "loc":
                cache[map_id] = mapgen.build_location(self.data, name)
            else:
                raise KeyError(map_id)
        return cache[map_id]

    def _world_id_of(self, region):
        return "lingjie" if region == "tianyuan" else "renjie"

    def _entrance_pos(self, loc_id):
        m = self.get_map("world:" + self._world_id_of(self.data_region_of(loc_id)))
        for e in m["entities"]:
            if e["k"] == "enter" and e["loc"] == loc_id:
                return [e["x"] + .5, e["y"] + 2.5]
        return list(m["spawn"])

    def data_region_of(self, loc_id):
        for w in self.data.regions:
            for g in w["regions"]:
                if any(l["id"] == loc_id for l in g["locations"]):
                    return g["id"]
        raise KeyError(loc_id)

    def _teleport(self, x, y):
        """伺服器主動移動角色（進出地點、渡海、傳送、戰敗）；前端看到 tp 變動就重設位置。"""
        self.pos = [x, y]
        self.tp = getattr(self, "tp", 0) + 1

    def td_reset(self):
        """新遊戲／舊存檔：站在大地圖起點（或目前區域的第一個地點門口）。"""
        self.mode, self.cur_loc, self.defeated, self.train_n, self.step_acc, self.battle = "world", None, [], 0, 0, None
        wid = self._world_id_of(self.region)
        self.map_id = "world:" + wid
        m = self.get_map(self.map_id)
        if self.region in ("tiannan",) or wid == "lingjie":
            self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
        else:
            first = self.data.regions[0]["regions"]
            g = next(g for g in first if g["id"] == self.region)
            self._teleport(*self._entrance_pos(g["locations"][0]["id"]))

    # ---- 動作 ----
    def _td(self, kind, **q):
        if self.battle and kind not in ("battle", "battle_end"):
            return
        if kind not in ("buy", "sell", "appraise", "barter", "join", "gift", "chat", "pos", "talk"):
            self.ui = {}
        fn = getattr(self, "_td_" + kind)
        fn(**q)

    def _td_shop_close(self, **_):
        self.ui = {}

    def _td_pos(self, x=None, y=None, steps=0, **_):
        if x not in (None, ""):
            self.pos = [float(x), float(y)]
        n = int(float(steps or 0))
        if n > 0:
            self.step_acc += n
            d = self.step_acc // STEPS_PER_DAY
            if d:
                self.step_acc -= d * STEPS_PER_DAY
                self.advance(d)

    def _td_enter(self, loc, **_):
        h = self.hero
        if self.mode != "world" and self.cur_loc == loc:
            return
        reg = self.data_region_of(loc)
        ldata = next(l for w in self.data.regions for g in w["regions"] if g["id"] == reg for l in g["locations"] if l["id"] == loc)
        if ldata["type"] in DEEP and h.realm < min_realm(loc, ldata):
            self.log.append("此地靈壓駭人，你的境界還不足以深入。")
            return
        self.region = reg
        self.mode, self.cur_loc, self.map_id = "loc", loc, "loc:" + loc
        m = self.get_map(self.map_id)
        self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
        self.defeated, self.train_n = [], 0
        h.counters[f"visit:{loc}"] = h.counters.get(f"visit:{loc}", 0) + 1
        self.log.append(f"進入「{m['name']}」")
        if m["cat"] in SAFE_CATS:
            self.make_checkpoint(m["name"])
        self._after_td(loc=loc, only="narration")

    def _td_leave(self, **_):
        if self.mode != "loc":
            return
        loc = self.cur_loc
        self.mode, self.cur_loc = "world", None
        self.map_id = "world:" + self._world_id_of(self.region)
        self._teleport(*self._entrance_pos(loc))
        self.defeated = []
        self.log.append("你離開了這裡，回到大地圖。")

    def _after_td(self, loc=None, arrive=None, only=None):
        h = self.hero
        if (loc or arrive) and not h.dialogue:
            did = dialogue.find_trigger(self.data, h, loc, arrive, only=only)
            if did:
                dialogue.start(self.data, h, did, self.log, self.rs)
                h.quest["baseline"] = dict(h.counters)
                k = f"visit:{loc}" if loc else f"arrive:{arrive}"
                h.quest["baseline"][k] = max(0, h.quest["baseline"].get(k, 0) - 1)
        self.log.extend(quests.update(self.data, h, self.rs))
        if not h.dialogue:
            did = dialogue.find_trigger(self.data, h)
            if did:
                dialogue.start(self.data, h, did, self.log, self.rs)

    def _td_region(self, to, **_):
        if to == self.region or to not in self.world.regions or not self.world.can_enter(self.hero, to):
            return
        self.region = to
        h = self.hero
        h.counters[f"arrive:{to}"] = h.counters.get(f"arrive:{to}", 0) + 1
        self.advance(1)
        self.log.append(f"進入{self.world.regions[to]['name']}")
        self._after_td(arrive=to)

    def _td_ferry(self, to, **_):
        m = self.get_map("world:renjie")
        if to not in m["docks"] or self.mode != "world" or self.region == to:
            return
        self.region = to
        dx, dy = m["docks"][to]
        self._teleport(dx + .5, dy + .5)
        h = self.hero
        h.counters[f"arrive:{to}"] = h.counters.get(f"arrive:{to}", 0) + 1
        self.advance(FERRY_DAYS)
        self.log.append(f"渡海抵達{self.world.regions[to]['name']}（{FERRY_DAYS} 日）")
        self._after_td(arrive=to)

    def _td_portal(self, **_):
        h = self.hero
        if self.mode != "loc" or self.cur_loc != "jixi":
            return
        if h.realm < 5:
            self.log.append("空間節點的力量深不可測，需要化神期才能穿越。")
            return
        self.region = "tianyuan"
        self.mode, self.cur_loc = "world", None
        self.map_id = "world:lingjie"
        m = self.get_map(self.map_id)
        self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
        h.counters["arrive:tianyuan"] = h.counters.get("arrive:tianyuan", 0) + 1
        self.log.append("你穿過空間節點，來到了靈界。")
        self._after_td(arrive="tianyuan")

    def _entity(self, eid):
        m = self.get_map(self.map_id)
        return next((e for e in m["entities"] if e["id"] == eid), None)

    def _td_talk(self, ent="quest", **_):
        h = self.hero
        if self.mode != "loc":
            return
        if ent == "quest":
            did = dialogue.find_trigger(self.data, h, self.cur_loc, None, only="npc")
            if did:
                dialogue.start(self.data, h, did, self.log, self.rs)
                h.quest["baseline"] = dict(h.counters)
                k = f"visit:{self.cur_loc}"
                h.quest["baseline"][k] = max(0, h.quest["baseline"].get(k, 0) - 1)
                self._after_td()
            else:
                self.log.append("對方朝你點了點頭，似乎沒有新的事情。")
            return
        if ent == "shady":
            sh = self.shady_now(self.cur_loc)
            if sh:
                self.log.append(f"「神秘商人」{_shady_line(self)}")
                self._open_shop("shady")
            return
        e = self._entity(ent)
        if not e:
            return
        k = e["k"]
        if k == "board":
            self.ui = {"board": {"loc": self.cur_loc}}
            self.log.append("你湊近布告欄，仔細看著上面的告示……")
        elif k == "candidate":
            self._talk_candidate(e)
        elif k == "npc":
            self._talk_npc(e)
        elif k == "chest":
            self._open_chest(e)
        elif k == "dummy":
            if self.train_n >= 5:
                self.log.append("今天練得夠多了，改天再來。")
            else:
                self.train_n += 1
                self.rs.gain_level(h, 1)
                self.advance(0)
                self.log.append(f"你對著木人樁演練了一番，修為略有精進（{self.train_n}/5）")
        elif k == "altar":
            h.mp = h.max_mp
            self.log.append("祭壇散發溫潤靈光，你的靈力完全恢復了。")
        elif k == "portal":
            self._td_portal()
        elif k == "well":
            self.make_checkpoint(f"{self.get_map(self.map_id)['name']}的井")
            self.log.append("你在井邊靜心，把此刻的一切記了下來——已儲存（若不幸倒下，會回到這裡）。")
        elif k == "guardian":
            if self.hero.flags.get("guardian:" + self.cur_loc):
                self.log.append("守護者已被你擊敗，這裡再沒有什麼攔著你了。")
            else:
                self._start_guardian(e)
        elif k == "sign":
            self.log.append(e.get("text", ""))
        elif k == "bed":
            h.hp, h.mp = h.max_hp, h.max_mp
            self.advance(1)
            self.log.append("你在床上睡了一覺，氣血與靈力都恢復了（過了一天）。")
            self.make_checkpoint(self.get_map(self.map_id)["name"])
            self._after_td()
        elif k == "furnace":
            self.log.append("這是一座煉丹爐。（可用靈草煉製丹藥）")

    def _talk_npc(self, e):
        h = self.hero
        role = e["role"]
        lines = self.data.ambient["lines"].get(role, ["……"])
        if role == "inn":
            h.hp, h.mp = h.max_hp, h.max_mp
            self.advance(1)
            self.log.append(f"「{e['name']}」{self.rng.choice(lines)}（歇息一晚，氣血靈力全滿）")
            self._after_td()
            return
        if role in ("shop", "pharmacy"):
            self.log.append(f"「{e['name']}」{self.rng.choice(lines)}")
            self._open_shop(role)
            return
        tgt = quests.target(self.data, h)
        if tgt and self.rng.random() < .45:
            name = self._target_name(tgt)
            if name:
                self.log.append(f"「{e['name']}」聽說「{name}」那邊有人在找你呢。")
                return
        local = self.data.ambient.get("byLoc", {}).get(self.cur_loc)
        if local and self.rng.random() < .55:
            lines = local
        self.log.append(f"「{e['name']}」{self.rng.choice(lines)}")

    def _target_name(self, tgt):
        if tgt.get("loc"):
            for w in self.data.regions:
                for g in w["regions"]:
                    for l in g["locations"]:
                        if l["id"] == tgt["loc"]:
                            return l["name"].split("（")[0]
        if tgt.get("region"):
            for w in self.data.regions:
                for g in w["regions"]:
                    if g["id"] == tgt["region"]:
                        return g["name"]
        return None

    def _open_chest(self, e):
        h = self.hero
        key = f"chest:{self.map_id}:{e['id']}"
        if h.flags.get(key):
            self.log.append("箱子已經是空的了。")
            return
        h.flags[key] = True
        loot = e.get("loot", "normal")
        scale = 1 + h.realm
        mult = self.dcfg["chest"]
        if loot == "empty":
            self.log.append("打開寶箱……裡面只有碎石和蜘蛛網。白忙一場！")
            return
        if loot == "mimic":
            m = self.get_map(self.map_id)
            self.log.append("寶箱突然張開了血盆大口——是寶箱怪！")
            self.battle = battle.start(h, self.cur_loc, [{"id": "mimic:" + e["id"], "kind": "spider", "el": self.rng.choice("金木水火土"), "name": "寶箱怪", "loot": 2.0}],
                                       m["cat"] == "deep", self.dcfg)
            self.battle["chest_bonus"] = True
            return
        rich = loot == "rich"
        gold = int(self.rng.uniform(40, 120) * scale * mult * (3.5 if rich else 1))
        h.add("lingshi", gold)
        msg = [f"獲得靈石 {gold}"]
        r = self.rng.random()
        if rich or r < .45:
            n = 3 if rich else 2
            h.add("heal", n)
            msg.append(f"回春丹 ×{n}")
        if rich or r > .8:
            h.add("pill")
            msg.append("突破丹 ×1")
        if rich or .5 < r < .7:
            h.add("lingye")
            msg.append("靈液 ×1")
        self.log.append(("打開寶箱（豐厚！）：" if rich else "打開寶箱：") + "，".join(msg))

    def _td_chest(self, ent, **_):
        e = self._entity(ent)
        if e and e["k"] == "chest":
            self._open_chest(e)

    # ---- 藥園：種植、收成、煉丹 ----
    def plot_state(self, eid):
        """回傳 {stage 0~3, left 剩餘天數, seed}；stage 0 空地、1 幼苗、2 生長中、3 成熟。"""
        pl = self.hero.plots.get(f"{self.cur_loc}:{eid}")
        if not pl:
            return {"stage": 0, "left": 0, "seed": None, "boost": False}
        seed = self.data.farming["seeds"][pl["seed"]]
        need = max(1, (seed["days"] + 1) // 2) if pl.get("boost") else seed["days"]
        elapsed = self.day - pl["day"]
        if elapsed >= need:
            return {"stage": 3, "left": 0, "seed": pl["seed"], "boost": bool(pl.get("boost"))}
        return {"stage": 1 if elapsed < need / 3 else 2, "left": need - elapsed, "seed": pl["seed"], "boost": bool(pl.get("boost"))}

    def plots_view(self):
        if self.mode != "loc":
            return {}
        m = self.get_map(self.map_id)
        return {e["id"]: self.plot_state(e["id"]) for e in m["entities"] if e["k"] == "plot"}

    def _plot_ok(self, ent):
        if self.mode != "loc":
            return None
        e = self._entity(ent)
        return e if e and e["k"] == "plot" else None

    def _td_plant(self, ent, seed="common", **_):
        h = self.hero
        if not self._plot_ok(ent) or self.plot_state(ent)["stage"] != 0 or seed not in self.data.farming["seeds"]:
            return
        sd = self.data.farming["seeds"][seed]
        cost = round(sd["cost"] * self.dcfg["price"])
        if not h.remove("lingshi", cost):
            self.log.append("靈石不夠買種子。")
            return
        h.plots[f"{self.cur_loc}:{ent}"] = {"seed": seed, "day": self.day, "boost": False}
        self.log.append(f"種下了{sd['name']}（-{cost} 靈石），約 {sd['days']} 日成熟。")

    def _td_boost(self, ent, **_):
        h = self.hero
        if not self._plot_ok(ent):
            return
        st = self.plot_state(ent)
        pl = h.plots.get(f"{self.cur_loc}:{ent}")
        if not pl or st["stage"] in (0, 3) or pl.get("boost"):
            return
        if not h.remove("lingye"):
            self.log.append("沒有靈液可以催熟。")
            return
        pl["boost"] = True
        self.log.append("你把一滴靈液灑在藥苗上，它眼看著長快了。")

    def _td_harvest(self, ent, **_):
        h = self.hero
        if not self._plot_ok(ent) or self.plot_state(ent)["stage"] != 3:
            return
        pl = h.plots.pop(f"{self.cur_loc}:{ent}")
        sd = self.data.farming["seeds"][pl["seed"]]
        n = self.rng.randint(*sd["yield"]) + (1 if pl.get("boost") else 0)
        h.add("herb", n)
        msg = f"收成了 {n} 株靈草。"
        if sd.get("lingye") and self.rng.random() < sd["lingye"] * (1.5 if pl.get("boost") else 1):
            h.add("lingye")
            msg += "藥株根部竟凝出一滴靈液！"
        self.log.append(msg)

    def _td_craft(self, recipe, **_):
        h = self.hero
        r = self.data.farming["recipes"].get(recipe)
        if self.mode != "loc" or not r or not any(e["k"] == "furnace" for e in self.get_map(self.map_id)["entities"]):
            return
        needs = {k: v for k, v in r["needs"].items()}
        if "lingshi" in needs:
            needs["lingshi"] = round(needs["lingshi"] * self.dcfg["price"])
        lack = [f"{item_name(k)}×{v}" for k, v in needs.items() if h.count(k) < v]
        if lack:
            self.log.append("材料不足：" + "、".join(lack))
            return
        chance = max(.05, min(1.0, r["chance"] + ((self.dcfg["craft"] + self.perk_totals()["craft"]) if r["chance"] < 1 else 0)))
        self.advance(1)
        if self.rng.random() < chance:
            for k, v in needs.items():
                h.remove(k, v)
            for k, v in r["gives"].items():
                h.add(k, v)
            self.log.append(f"丹成！獲得 {'、'.join(f'{item_name(k)}×{v}' for k, v in r['gives'].items())}。")
        else:
            for k, v in needs.items():
                h.remove(k, (v + 1) // 2 if k != "lingye" else v)
            self.log.append("丹爐轟然一震……煉製失敗了，損失了一半材料。")

    # ---- 戰鬥 ----
    def _td_battle_start(self, ids="", **_):
        if self.mode != "loc":
            return
        m = self.get_map(self.map_id)
        idl = [i for i in str(ids).split(",") if i and i not in self.defeated]
        ents = [e for e in m["entities"] if e["k"] == "enemy" and e["id"] in idl]
        if not ents:
            return
        deep = m["cat"] == "deep"
        self.battle = battle.start(self.hero, self.cur_loc, [{"id": e["id"], "kind": e["kind"], "el": e["el"], "loot": e.get("loot", 1.0) * (1 + self.perk_totals()["loot"]), "name": e.get("name")} for e in ents], deep, self.dcfg, self.partner_spec())

    def _td_battle(self, cmd="attack", arg=None, target=None, **_):
        if not self.battle:
            return
        h = self.hero
        a = (arg if cmd in ("talisman", "formation", "treasure") else int(arg)) if arg not in (None, "") else None
        t = int(target) if target not in (None, "") else None
        done = battle.command(self.battle, h, self.rs, self.rng, cmd, a, t, self.combat_bonus())
        if done:
            st = self.battle
            over = st["over"]
            self.defeated.extend(st["killed"])
            if st.get("boss") and over != "win" and st.get("retry"):
                h.flags.pop("seen:" + st["retry"], None)          # 強敵還在，重新進入此地可再戰
                self.log.append("強敵仍在原地等著你，準備好了再來。")
            if over == "lose":
                if self.checkpoint:
                    self._restore_checkpoint()
                else:
                    lost = min(self.dcfg["death_loss"], h.count("lingshi"))
                    h.remove("lingshi", lost)
                    h.hp = h.max_hp / 2
                    self.log.append(f"你被人救回，損失靈石 {lost}。")
                    m = self.get_map(self.map_id)
                    self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
            elif over == "soul":
                lost = min(self.dcfg["death_loss"], h.count("lingshi"))
                h.remove("lingshi", lost)
                self.log.append(f"元嬰帶著殘存的元神遁走，肉身重塑耗去靈石 {lost}。")
                if self.mode == "loc":
                    m = self.get_map(self.map_id)
                    self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
            elif over == "win":
                drops = []
                if st.get("boss"):
                    for e in st["enemies"]:
                        if e.get("drops"):
                            drops += loot.roll_table(self.data, e["drops"], h, self.rng, self.dcfg["chest"])
                else:
                    drops += loot.roll_minion(self.data, h, self.rng)
                msgs = loot.grant(h, drops)
                st["rewards"].extend(msgs)
                self.log.extend(msgs)
                if st.get("chest_bonus"):
                    gold = int(self.rng.uniform(60, 150) * (1 + h.realm) * self.dcfg["chest"])
                    h.add("lingshi", gold)
                    h.add("heal", 1)
                    self.log.append(f"寶箱怪的肚子裡吐出了靈石 {gold} 和一顆回春丹。")
                self._after_td()

    def _td_battle_end(self, **_):
        self.battle = None


def _shady_line(sess):
    return sess.rng.choice(sess.data.market["shady"]["greetings"])
