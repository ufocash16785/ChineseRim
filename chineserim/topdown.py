"""俯視地圖模式：大地圖行走、進出地點、NPC 互動、遭遇戰。以 Mixin 形式併入 Session。"""
from . import battle, dialogue, mapgen, quests
from .explore import DEEP, min_realm

_MAP_CACHE = {}          # 地圖只由資料決定，行程內共用（唯讀）
TD_KINDS = {"shop_close", "enter", "leave", "talk", "region", "ferry", "pos", "battle_start", "battle", "battle_end", "buy", "chest", "portal"}
STEPS_PER_DAY = 160
FERRY_DAYS = 8


class TopDownMixin:
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
        if kind not in ("buy", "pos", "talk"):
            self.shop_open = False
        fn = getattr(self, "_td_" + kind)
        fn(**q)

    def _td_shop_close(self, **_):
        self.shop_open = False

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
        ltype = next(l["type"] for w in self.data.regions for g in w["regions"] if g["id"] == reg for l in g["locations"] if l["id"] == loc)
        if ltype in DEEP and h.realm < min_realm(loc):
            self.log.append("此地靈壓駭人，你的境界還不足以深入。")
            return
        self.region = reg
        self.mode, self.cur_loc, self.map_id = "loc", loc, "loc:" + loc
        m = self.get_map(self.map_id)
        self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
        self.defeated, self.train_n = [], 0
        h.counters[f"visit:{loc}"] = h.counters.get(f"visit:{loc}", 0) + 1
        self.log.append(f"進入「{m['name']}」")
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
        e = self._entity(ent)
        if not e:
            return
        k = e["k"]
        if k == "npc":
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
        elif k == "sign":
            self.log.append(e.get("text", ""))

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
        if role == "shop":
            self.log.append(f"「{e['name']}」{self.rng.choice(lines)}（回春丹 30 靈石／突破丹 100 靈石）")
            self.shop_open = True
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

    def _td_buy(self, item="heal", **_):
        prices = self.data.ambient["shop"]
        if item not in prices or self.mode != "loc":
            return
        if self.hero.remove("lingshi", prices[item]):
            self.hero.add(item)
            from .character import item_name
            self.log.append(f"買下了{item_name(item)}（-{prices[item]} 靈石）")
        else:
            self.log.append("靈石不夠。")

    def _open_chest(self, e):
        h = self.hero
        key = f"chest:{self.map_id}:{e['id']}"
        if h.flags.get(key):
            self.log.append("箱子已經是空的了。")
            return
        h.flags[key] = True
        scale = 1 + h.realm
        gold = int(self.rng.uniform(40, 120) * scale)
        h.add("lingshi", gold)
        msg = [f"獲得靈石 {gold}"]
        r = self.rng.random()
        if r < .45:
            h.add("heal", 2)
            msg.append("回春丹 ×2")
        if r > .8:
            h.add("pill")
            msg.append("突破丹 ×1")
        if .5 < r < .7:
            h.add("lingye")
            msg.append("靈液 ×1")
        self.log.append("打開寶箱：" + "，".join(msg))

    def _td_chest(self, ent, **_):
        e = self._entity(ent)
        if e and e["k"] == "chest":
            self._open_chest(e)

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
        self.battle = battle.start(self.hero, self.cur_loc, [{"id": e["id"], "kind": e["kind"], "el": e["el"]} for e in ents], deep)

    def _td_battle(self, cmd="attack", arg=None, target=None, **_):
        if not self.battle:
            return
        h = self.hero
        a = int(arg) if arg not in (None, "") else None
        t = int(target) if target not in (None, "") else None
        done = battle.command(self.battle, h, self.rs, self.rng, cmd, a, t, self.combat_bonus())
        if done:
            over = self.battle["over"]
            self.defeated.extend(self.battle["killed"])
            if over == "lose":
                lost = min(50, h.count("lingshi"))
                h.remove("lingshi", lost)
                h.hp = h.max_hp / 2
                self.log.append(f"你被人救回，損失靈石 {lost}。")
                m = self.get_map(self.map_id)
                self._teleport(m["spawn"][0] + .5, m["spawn"][1] + .5)
            elif over == "win":
                self._after_td()

    def _td_battle_end(self, **_):
        self.battle = None
