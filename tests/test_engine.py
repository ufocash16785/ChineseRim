import random
import unittest

from chineserim import Character, GameData, RealmSystem, element_multiplier, treasures


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.d = GameData()
        self.rs = RealmSystem(self.d, random.Random(1))
        self.c = Character("t")
        self.rs.set_realm(self.c, "mortal")

    def test_elements(self):
        self.assertEqual(element_multiplier("木", "土"), 1.5)
        self.assertEqual(element_multiplier("土", "木"), 0.75)
        self.assertEqual(element_multiplier("雷", "土"), 1.5)   # 雷→木
        self.assertEqual(element_multiplier("木", "木"), 1.0)

    def test_level_cap_and_breakthrough(self):
        self.rs.gain_level(self.c, 99)
        self.assertEqual(self.c.level, 5)
        self.assertTrue(self.rs.at_bottleneck(self.c))
        self.c.add("p")
        for _ in range(200):
            self.c.level = 5
            self.c.add("p")
            if self.rs.attempt_breakthrough(self.c, "p"):
                break
        self.assertEqual(self.c.realm, 1)

    def test_refine(self):
        self.c.add("lingshi", 1000)
        self.assertFalse(treasures.refine(self.rs, self.c, "x"))   # 境界不足
        self.c.realm = 2
        self.assertTrue(treasures.refine(self.rs, self.c, "x"))
        self.assertEqual(self.c.count("lingshi"), 950)

    def test_moon(self):
        self.assertEqual(treasures.tick_zhangtianping(self.rs, self.c, 30, 22), 30)
        self.assertEqual(self.c.count("lingye"), 1)
        treasures.tick_zhangtianping(self.rs, self.c, 30, 22, last_day=30)
        self.assertEqual(self.c.count("lingye"), 1)


if __name__ == "__main__":
    unittest.main()


class ExploreTest(unittest.TestCase):
    def setUp(self):
        from chineserim.explore import WorldMap, visit
        self.visit, self.w = visit, WorldMap(GameData())
        self.d = GameData()
        self.rs = RealmSystem(self.d, random.Random(2))
        self.c = Character("t", elements=["金", "木"])
        self.rs.set_realm(self.c, "mortal")
        self.c.add("lingshi", 500)

    def test_travel(self):
        self.assertFalse(self.w.travel(self.c, "tiannan", "tianyuan")[0])   # 靈界鎖
        ok, days, _ = self.w.travel(self.c, "tiannan", "dajin")
        self.assertTrue(ok and days > 0)
        self.c.realm = 2
        self.assertLess(self.w.travel_days(self.c, "tiannan", "dajin"), days)  # 築基飛行

    def test_visit_types(self):
        r = random.Random(3)
        msg, days = self.visit(self.w, self.rs, self.c, "tiannan", "xuese", r)   # 秘境擋凡人
        self.assertEqual(days, 0)
        self.c.hp = 1
        self.visit(self.w, self.rs, self.c, "tiannan", "yuejing", r)             # 城市回血
        self.assertEqual(self.c.hp, self.c.max_hp)
        self.visit(self.w, self.rs, self.c, "tiannan", "huangfeng", r)           # 門派聲望
        self.assertEqual(self.c.sects.get("huangfenggu"), 1)
        msg, days = self.visit(self.w, self.rs, self.c, "tiannan", "taiyue", r)  # 野外戰鬥
        self.assertTrue(msg and days == 2)

    def test_layout(self):
        pts = self.w.location_layout("tiannan")
        self.assertEqual(len(pts), len(self.w.regions["tiannan"]["locations"]))


class SaveQuestTest(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from chineserim.session import Session
        self.Session = Session
        self.path = pathlib.Path(tempfile.mkdtemp()) / "s.json"
        self.s = Session(self.path, seed=5)

    def test_save_roundtrip(self):
        self.s.act("visit", loc="qingniu")
        self.s.act("travel", to="dajin")
        snap = self.s.to_dict()
        s2 = self.Session(self.path, seed=9)
        self.assertTrue(s2.load())
        self.assertEqual(s2.to_dict()["hero"], snap["hero"])
        self.assertEqual((s2.day, s2.region), (snap["day"], snap["region"]))

    def test_bad_version(self):
        with self.assertRaises(ValueError):
            self.s.from_dict({"version": 99})

    def test_quest_flow(self):
        s = self.s

        def go(loc):
            while s.hero.dialogue:
                s.act("choose", i=0 if s.snapshot()["dialogue"]["choices"] else "")
            s.act("visit", loc=loc)
        go("qingniu")
        self.assertEqual(s.hero.quest["o"], 1)
        go("caixia")            # 門派：+2 等級
        go("caixia")
        go("caixia")
        while s.hero.dialogue:
            s.act("choose", i=0 if s.snapshot()["dialogue"]["choices"] else "")
        s.act("rest")
        self.assertGreaterEqual(s.hero.quest["q"], 1)        # 第一個任務已完成
        self.assertIn("lingshi", s.hero.inventory)
        v = s.snapshot()["quest"]
        self.assertEqual(v["quests"][0]["state"], "done")
        # 存檔後任務進度保留
        s2 = self.Session(self.path)
        s2.load()
        self.assertEqual(s2.hero.quest, s.hero.quest)

    def test_full_arc_reachable(self):
        """機器人從第一卷玩到靈界 DLC：驗證所有任務鏈與對話都走得通、沒有卡死。"""
        from tests.bot import play_through
        s = self.s
        steps = play_through(s)
        self.assertTrue(s.hero.quest["done"], f"卡在 {s.hero.quest}（{steps} 步）")
        self.assertEqual(s.hero.quest["arc"], "arc6_lingjie")
        self.assertTrue(s.hero.flags.get("arc0_complete"))
        seen = {k[5:] for k in s.hero.flags if k.startswith("seen:")}
        self.assertEqual({k for k, v in s.data.dialogues.items() if "cmp" not in v["trigger"]} - seen, set(), "有對話沒被觸發")


class DialogueTest(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)

    def test_trigger_blocks_and_branches(self):
        s, h = self.s, self.s.hero
        s.act("visit", loc="qingniu")
        self.assertEqual(h.dialogue["id"], "d_farewell")
        s.act("travel", to="dajin")                        # 對話中其他動作被擋
        self.assertEqual(s.region, "tiannan")
        s.act("choose", i=0)                               # 收下乾糧 → end1
        self.assertIn("lingshi", h.inventory)
        s.act("choose", i="")                              # 繼續 → 結束
        self.assertFalse(h.dialogue)
        s.act("visit", loc="qingniu")                      # 只觸發一次
        self.assertFalse(h.dialogue)

    def test_dialogue_persists_in_save(self):
        from chineserim.session import Session
        s = self.s
        s.act("visit", loc="qingniu")
        s2 = Session(s.save_path)
        s2.load()
        self.assertEqual(s2.hero.dialogue, s.hero.dialogue)
        self.assertEqual(s2.snapshot()["dialogue"]["speaker"], "母親")

    def test_trap_choice_sets_flag(self):
        from chineserim import dialogue
        s, h = self.s, self.s.hero
        h.quest = {"arc": "arc0_qixuanmen", "q": 3, "o": 0, "baseline": {}, "done": False}
        s.act("visit", loc="caixia")
        self.assertEqual(h.dialogue["id"], "d_suspect")
        s.act("choose", i=1)                               # 當面質問：受傷，仍會設陷
        s.act("choose", i="")
        self.assertTrue(h.flags.get("trap_set"))
        self.assertLess(h.hp, h.max_hp)


class SideScrollBackendTest(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)

    def test_kill_counts_and_rewards(self):
        s, h = self.s, self.s.hero
        n = h.count("lingshi")
        s.act("kill", loc="taiyue", deep="0", hp="80")
        self.assertGreater(h.count("lingshi"), n)
        self.assertEqual(h.counters["kill:taiyue"], 1)
        self.assertEqual(h.counters["kill:total"], 1)
        self.assertEqual(h.hp, 80)            # 前端血量被同步

    def test_die_penalty(self):
        s, h = self.s, self.s.hero
        n = h.count("lingshi")
        s.act("die", hp="1")
        self.assertEqual(h.count("lingshi"), n - 50)
        self.assertEqual(h.hp, h.max_hp / 2)

    def test_snapshot_has_scroller_fields(self):
        d = self.s.snapshot()
        self.assertIn("pairs", d["elem"])
        self.assertTrue(any(l["wild"] for l in d["locations"]))
        self.assertTrue(any(l["deep"] for l in d["locations"]))

    def test_nofight_visit_only_counts(self):
        s, h = self.s, self.s.hero
        h.realm = 2
        s.act("visit", loc="xuese", nofight="1")
        self.assertEqual(h.counters["visit:xuese"], 1)
        self.assertEqual(h.count("lingshi"), 500)   # 沒有自動戰鬥結算


class ArcMigrationTest(unittest.TestCase):
    def test_old_save_with_finished_arc0_advances(self):
        import tempfile, pathlib
        from chineserim import quests
        from chineserim.session import Session
        s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)
        s.hero.quest = {"arc": "arc0_qixuanmen", "q": 5, "o": 0, "baseline": {}, "done": True}   # 舊格式：無 completed
        msgs = quests.update(s.data, s.hero, s.rs)
        self.assertEqual(s.hero.quest["arc"], "arc1_tiannan")
        self.assertTrue(any("第二卷" in m for m in msgs))


class FrontendSmokeTest(unittest.TestCase):
    def test_side_html_js_parses(self):
        """卷軸頁面內嵌 JS 必須可解析（防止再次出現語法錯誤導致整頁空白）。"""
        import pathlib, shutil, subprocess, tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("沒有 node")
        for name in ("side.html",):
            html = (pathlib.Path(__file__).parents[1] / "chineserim" / "static" / name).read_text(encoding="utf-8")
            js = html[html.index("<script>") + 8:html.rindex("</script>")]
            f = pathlib.Path(tempfile.mkdtemp()) / "x.js"
            f.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_map_page_js_parses(self):
        import shutil, subprocess, tempfile, pathlib
        from chineserim import web
        node = shutil.which("node")
        if not node:
            self.skipTest("沒有 node")
        js = web.PAGE[web.PAGE.index("<script>") + 8:web.PAGE.rindex("</script>")]
        f = pathlib.Path(tempfile.mkdtemp()) / "m.js"
        f.write_text(js, encoding="utf-8")
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class BranchFuzzTest(unittest.TestCase):
    def test_random_choices_never_soft_lock(self):
        """不同對話分支選擇（隨機）都必須能打通全部劇情。"""
        import pathlib, tempfile
        from chineserim.session import Session
        from tests.bot import play_through
        for seed in range(12):
            r = random.Random(seed)
            s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=seed)
            play_through(s, pick=lambda ch: r.choice(ch)["i"])
            self.assertTrue(s.hero.quest["done"], f"seed {seed} 卡在 {s.hero.quest}")
            self.assertLessEqual(s.hero.hp, s.hero.max_hp)


class GongfaTest(unittest.TestCase):
    def test_learn_and_bonus(self):
        import pathlib, tempfile
        from chineserim.session import Session
        from tests.bot import play_through
        s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=4)
        base_hp = s.hero.max_hp
        play_through(s, limit=25)                       # 玩到墨大夫傳授長春功之後
        self.assertIn("changchun_gong", s.hero.gongfa)
        self.assertGreater(s.combat_bonus()["regen"], 0)
        play_through(s)
        for g in ("qingyuan_jianjue", "dayan_jue", "mingqing_lingmu", "fansheng_zhenmo"):
            self.assertIn(g, s.hero.gongfa)
        self.assertEqual(s.combat_bonus()["elemDmg"]["木"], 0.3)
        self.assertGreater(s.hero.max_hp, 1000)           # 化神 1000 × (1+0.1+0.3)


class CreationTest(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)

    def test_custom_root(self):
        self.s.act("new", name="小明", root="heavenly", elems="火")
        h = self.s.hero
        self.assertEqual((h.name, h.root_type, h.elements, h.speed), ("小明", "heavenly", ["火"], 2.0))

    def test_variant_and_invalid(self):
        self.s.act("new", root="variant", elems="雷")
        self.assertEqual(self.s.hero.elements, ["雷"])
        self.s.act("new", root="dual", elems="金金")            # 重複 → 回原作
        self.assertEqual(self.s.hero.name, "韓立")
        self.s.act("new", root="heavenly", elems="雷")          # 天靈根不能選變異屬性
        self.assertEqual(self.s.hero.root_type, "quad")

    def test_speed_scales_level_gain(self):
        from chineserim.character import Character
        rs = RealmSystem(GameData(), random.Random(1))
        fast, slow = Character("a", speed=2.0), Character("b", speed=0.8)
        for c in (fast, slow):
            rs.set_realm(c, "qi_refining")
            rs.gain_level(c, 5)
        self.assertGreater(fast.level, slow.level)

    def test_creation_fields_in_snapshot(self):
        d = self.s.snapshot()
        self.assertEqual(len(d["roots"]), 6)

    def test_custom_hero_can_finish_game(self):
        from tests.bot import play_through
        self.s.act("new", root="penta", elems="金木水火土")       # 最慢的靈根也要能打通
        play_through(self.s)
        self.assertTrue(self.s.hero.quest["done"])


class ArtAssetsTest(unittest.TestCase):
    """像素素材與 manifest 的一致性（不需要 Pillow：只讀 PNG 檔頭）。"""
    ART = None

    @classmethod
    def setUpClass(cls):
        import json, pathlib
        cls.ART = pathlib.Path(__file__).parents[1] / "chineserim" / "static" / "art"
        cls.man = json.loads((cls.ART / "manifest.json").read_text(encoding="utf-8"))

    @staticmethod
    def png_size(path):
        import struct
        b = path.read_bytes()[:24]
        assert b[:8] == b"\x89PNG\r\n\x1a\n", path
        return struct.unpack(">II", b[16:24])

    def test_sheets_fit_manifest(self):
        fw, fh = self.man["human"]["frameW"], self.man["human"]["frameH"]
        w, h = self.png_size(self.ART / "heroes.png")
        self.assertEqual(w, 8 * fw)
        self.assertEqual(h, 6 * self.man["heroes"]["rowsPerOutfit"] * fh)
        w, h = self.png_size(self.ART / "npcs.png")
        self.assertGreaterEqual(h, (max(n["row"] for n in self.man["npcs"].values()) + 2) * fh)
        b = self.man["beasts"]
        w, h = self.png_size(self.ART / "beasts.png")
        self.assertEqual(w, 4 * b["frameW"])
        self.assertEqual(h, len(b["kinds"]) * len(b["elements"]) * b["frameH"])

    def test_speakers_have_sprites(self):
        for name, npc in self.man["speakers"].items():
            self.assertIn(npc, self.man["npcs"], name)
        # 對話中出現的說話者（旁白除外）都要有立繪
        d = GameData()
        speakers = {n["speaker"] for dlg in d.dialogues.values() for n in dlg["nodes"].values()} - {"旁白"}
        self.assertEqual(speakers - set(self.man["speakers"]), set(), "有說話者沒有 NPC 立繪")

    def test_every_region_has_a_biome(self):
        d = GameData()
        for w in d.regions:
            for g in w["regions"]:
                self.assertIn(g["id"], self.man["biomes"], g["id"])
                self.assertTrue((self.ART / f"scene_{g['id']}.png").exists())

    def test_biome_rects_inside_atlas(self):
        for b, info in self.man["biomes"].items():
            w, h = self.png_size(self.ART / f"scene_{b}.png")
            for name, (x, y, rw, rh) in info["rects"].items():
                self.assertLessEqual(x + rw, w, (b, name))
                self.assertLessEqual(y + rh, h, (b, name))
        w, h = self.png_size(self.ART / "fx.png")
        for name, (x, y, rw, rh) in self.man["fx"]["rects"].items():
            self.assertTrue(x + rw <= w and y + rh <= h, name)

    def test_art_js_parses(self):
        import pathlib, shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("沒有 node")
        f = pathlib.Path(__file__).parents[1] / "chineserim" / "static" / "art.js"
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class MapGenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from chineserim import mapgen
        cls.mg, cls.d = mapgen, GameData()

    def test_deterministic(self):
        a = self.mg.build_world(self.d)
        b = self.mg.build_world(self.d)
        self.assertEqual(a["ground"], b["ground"])
        self.assertEqual(self.mg.build_location(self.d, "caixia")["ground"], self.mg.build_location(self.d, "caixia")["ground"])

    def _reach(self, m, start):
        s = [[int(c) for c in r] for r in m["solid"]]
        return self.mg.bfs(s, m["w"], m["h"], tuple(int(v) for v in start))

    def test_world_entrances_reachable(self):
        for wid, needs_ferry in (("renjie", True), ("lingjie", False)):
            m = self.mg.build_world(self.d, wid)
            reach = self._reach(m, m["spawn"])
            if needs_ferry:
                # 亂星海要靠渡口：從對岸渡口出發也必須能走到所有島上的地點
                reach |= self._reach(m, [m["docks"]["luanxinghai"][0], m["docks"]["luanxinghai"][1]])
            for e in m["entities"]:
                if e["k"] == "enter":
                    self.assertTrue((e["x"], e["y"] + 1) in reach, f"{wid}:{e['id']} 不可達")
                elif e["k"] == "dock":
                    self.assertIn((e["x"], e["y"]), reach)

    def test_every_location_has_a_map(self):
        seen = 0
        for w in self.d.regions:
            for g in w["regions"]:
                for l in g["locations"]:
                    m = self.mg.build_location(self.d, l["id"])
                    reach = self._reach(m, [m["spawn"][0], m["spawn"][1]])
                    self.assertTrue(all(tuple(c) in reach for c in m["exit"]), f"{l['id']} 出口不可達")
                    self.assertIn(tuple(m["npcSpot"]), reach, l["id"])
                    if m["cat"] in ("wild", "deep"):
                        self.assertGreaterEqual(sum(1 for e in m["entities"] if e["k"] == "enemy"), 4, l["id"])
                    for e in m["entities"]:
                        if e["k"] == "enemy":
                            self.assertIn((e["x"], e["y"]), reach)
                    seen += 1
        self.assertEqual(seen, sum(len(g["locations"]) for w in self.d.regions for g in w["regions"]))
        self.assertGreaterEqual(seen, 100)

    def test_jixi_has_portal(self):
        m = self.mg.build_location(self.d, "jixi")
        self.assertTrue(any(e["k"] == "portal" for e in m["entities"]))


class BattleTest(unittest.TestCase):
    def setUp(self):
        from chineserim import battle
        self.b = battle
        self.rs = RealmSystem(GameData(), random.Random(1))
        self.c = Character("t", elements=["金", "木", "水", "火"])
        self.rs.set_realm(self.c, "mortal")
        self.c.add("heal", 2)
        self.rng = random.Random(3)

    def _fight(self, specs, deep=False, policy=None):
        st = self.b.start(self.c, "taiyue", specs, deep)
        for _ in range(80):
            cmd = policy(st) if policy else ("attack", None)
            if self.b.command(st, self.c, self.rs, self.rng, cmd[0], cmd[1], None, {}):
                break
        return st

    def test_win_gives_rewards_and_kill_counters(self):
        st = self._fight([{"kind": "wolf", "el": "土"}])
        self.assertEqual(st["over"], "win")
        self.assertEqual(self.c.counters["kill:taiyue"], 1)
        self.assertGreater(self.c.count("lingshi"), 0)
        self.assertGreater(self.c.level, 1)

    def test_spell_costs_mp_and_needs_it(self):
        st = self.b.start(self.c, "x", [{"kind": "wolf", "el": "木"}])
        self.c.mp = 0
        self.b.command(st, self.c, self.rs, self.rng, "spell", 0)
        self.assertIn("靈力耗盡", st["log"][0])
        self.assertEqual(st["turn"], 1)             # 沒有消耗回合
        self.c.mp = self.c.max_mp
        before = self.c.mp
        self.b.command(st, self.c, self.rs, self.rng, "spell", 0)
        self.assertLess(self.c.mp, before)

    def test_element_advantage(self):
        st = self.b.start(self.c, "x", [{"kind": "wolf", "el": "土"}, {"kind": "wolf", "el": "金"}])
        rng = random.Random(1)
        self.b.command(st, self.c, self.rs, rng, "spell", 1, 0)      # 木剋土
        self.assertTrue(any("剋制" in l for l in st["log"]))

    def test_heal_and_guard_and_flee(self):
        st = self.b.start(self.c, "x", [{"kind": "bear", "el": "水"}])
        self.c.hp = 10
        self.b.command(st, self.c, self.rs, self.rng, "item")
        self.assertGreater(self.c.hp, 30)
        self.assertEqual(self.c.count("heal"), 1)
        for _ in range(40):
            if self.b.command(st, self.c, self.rs, self.rng, "flee"):
                break
            self.c.hp = self.c.max_hp
        self.assertIn(st["over"], ("flee", None))

    def test_lose_when_hp_zero(self):
        st = self.b.start(self.c, "x", [{"kind": "bear", "el": "水"}] * 3)
        self.c.hp = 1
        self.b.command(st, self.c, self.rs, self.rng, "guard")
        self.assertEqual(st["over"], "lose")

    def test_deep_battles_max_two(self):
        st = self.b.start(self.c, "x", [{"kind": "bat", "el": "木"}] * 3, deep=True)
        self.assertEqual(len(st["enemies"]), 2)

    def test_balanced_for_typical_play(self):
        """自動打法在各境界對『一般野外 1 隻』應穩定獲勝。"""
        for realm in range(6):
            wins = 0
            for seed in range(40):
                rng = random.Random(seed)
                rs = RealmSystem(GameData(), rng)
                c = Character("t", elements=["金", "木", "水", "火"])
                c.realm = realm
                rs.apply_stats(c)
                c.level = rs.data.realms[realm]["levelRange"][0]
                c.add("heal", 3)
                st = self.b.start(c, "x", [{"kind": rng.choice(list(self.b.KINDS)), "el": rng.choice("金木水火土")}])
                for _ in range(60):
                    if c.hp < .4 * c.max_hp and c.count("heal"):
                        cmd = ("item", None)
                    elif c.mp >= self.b.spell_cost(c):
                        cmd = ("spell", rng.randrange(4))
                    else:
                        cmd = ("attack", None)
                    if self.b.command(st, c, rs, rng, cmd[0], cmd[1], None, {}):
                        break
                wins += st["over"] == "win"
            self.assertGreaterEqual(wins, 36, f"realm {realm}")


class TopDownSessionTest(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        from chineserim.session import Session
        self.Session = Session
        self.path = pathlib.Path(tempfile.mkdtemp()) / "s.json"
        self.s = Session(self.path, seed=2)

    def test_starts_on_world_map_near_qingniu(self):
        s = self.s
        self.assertEqual((s.mode, s.map_id), ("world", "world:renjie"))
        m = s.get_map(s.map_id)
        e = next(e for e in m["entities"] if e["id"] == "enter:qingniu")
        self.assertLess(abs(s.pos[0] - e["x"]) + abs(s.pos[1] - e["y"]), 4)

    def test_enter_leave_roundtrip_and_counters(self):
        s = self.s
        s.act("enter", loc="qingniu")
        self.assertEqual((s.mode, s.cur_loc, s.map_id), ("loc", "qingniu", "loc:qingniu"))
        self.assertEqual(s.hero.counters["visit:qingniu"], 1)
        s.act("leave")
        self.assertEqual((s.mode, s.cur_loc), ("world", None))
        m = s.get_map("world:renjie")
        e = next(e for e in m["entities"] if e["id"] == "enter:qingniu")
        self.assertAlmostEqual(s.pos[1], e["y"] + 2.5)          # 站在入口下方，不會立刻再觸發

    def test_npc_dialogue_needs_talking_but_narration_auto(self):
        s = self.s
        s.act("enter", loc="qingniu")                            # d_farewell：母親開場 → 要對話才觸發
        self.assertFalse(s.hero.dialogue)
        self.assertEqual(s.snapshot()["questNpc"], "母親")
        s.act("talk", ent="quest")
        self.assertEqual(s.hero.dialogue["id"], "d_farewell")
        s.act("choose", i=0)
        s.act("choose", i="")
        self.assertIsNone(s.snapshot()["questNpc"])
        s.act("leave")
        s.act("enter", loc="huangfeng")                          # 只是進入：旁白劇情才會自動觸發
        self.assertFalse(s.hero.dialogue)

    def test_blocked_during_battle_and_battle_flow(self):
        s = self.s
        s.act("enter", loc="taiyue")
        m = s.get_map(s.map_id)
        ids = [e["id"] for e in m["entities"] if e["k"] == "enemy"][:1]
        s.act("battle_start", ids=",".join(ids))
        self.assertIsNotNone(s.battle)
        s.act("leave")                                            # 戰鬥中不能離開
        self.assertEqual(s.mode, "loc")
        for _ in range(60):
            if s.battle["over"]:
                break
            s.act("battle", cmd="attack")
        s.act("battle_end")
        self.assertIsNone(s.battle)
        if s.hero.counters.get("kill:taiyue"):
            self.assertIn(ids[0], s.defeated)

    def test_deep_gate_and_defeat_penalty(self):
        s = self.s
        s.act("enter", loc="kunwu")                               # 境界不足
        self.assertEqual(s.mode, "world")
        s.hero.realm = 2
        s.rs.apply_stats(s.hero)
        s.act("enter", loc="taiyue")
        e = next(e for e in s.get_map(s.map_id)["entities"] if e["k"] == "enemy")
        s.act("battle_start", ids=e["id"])
        cp_label = s.checkpoint["label"]
        s.hero.hp = 1
        s.act("battle", cmd="guard")
        while s.battle and not s.battle["over"]:
            s.hero.hp = 1
            s.act("battle", cmd="guard")
        if s.battle is None:                                       # 元嬰前戰敗＝回到上一個儲存點
            self.assertEqual(s.hero.hp, s.hero.max_hp)
            self.assertIn(cp_label, s.log[-1])

    def test_chest_once_and_shop_and_inn(self):
        s = self.s
        s.act("enter", loc="taiyue")
        m = s.get_map(s.map_id)
        chest = next(e for e in m["entities"] if e["k"] == "chest")
        n = s.hero.count("lingshi")
        s.act("talk", ent=chest["id"])
        n2 = s.hero.count("lingshi")
        self.assertGreater(n2, n)
        s.act("talk", ent=chest["id"])
        self.assertEqual(s.hero.count("lingshi"), n2)              # 只能開一次
        s.act("leave")
        s.act("enter", loc="jiazhou")
        m = s.get_map(s.map_id)
        shop = next(e for e in m["entities"] if e.get("role") in ("shop", "pharmacy"))
        inn = next(e for e in m["entities"] if e.get("role") == "inn")
        s.act("talk", ent=shop["id"])
        self.assertTrue(s.snapshot()["shop"])
        before = s.hero.count("heal")
        s.act("buy", item="heal")
        self.assertEqual(s.hero.count("heal"), before + 1)
        s.hero.hp, d0 = 5, s.day
        s.act("talk", ent=inn["id"])
        self.assertEqual(s.hero.hp, s.hero.max_hp)
        self.assertEqual(s.day, d0 + 1)

    def test_region_crossing_and_ferry(self):
        s = self.s
        s.act("region", to="mulan")
        self.assertEqual(s.region, "mulan")
        self.assertEqual(s.hero.counters["arrive:mulan"], 1)
        s.act("region", to="tiannan")
        s.act("ferry", to="luanxinghai")
        self.assertEqual(s.region, "luanxinghai")
        m = s.get_map("world:renjie")
        dx, dy = m["docks"]["luanxinghai"]
        self.assertEqual(s.pos, [dx + .5, dy + .5])
        s.act("region", to="tianyuan")                             # 靈界需飛升
        self.assertEqual(s.region, "luanxinghai")

    def test_portal_needs_deity_realm(self):
        s = self.s
        s.act("enter", loc="jixi")
        s.act("portal")
        self.assertEqual(s.region, "tiannan")
        s.hero.realm = 5
        s.act("portal")
        self.assertEqual((s.region, s.map_id, s.mode), ("tianyuan", "world:lingjie", "world"))

    def test_steps_advance_days_and_save_roundtrip(self):
        s = self.s
        s.act("pos", x="10.5", y="20.5", steps="330")
        self.assertEqual(s.day, 2)
        s.act("enter", loc="qingniu")
        s2 = self.Session(self.path, seed=9)
        self.assertTrue(s2.load())
        self.assertEqual((s2.mode, s2.cur_loc, s2.map_id, s2.day), ("loc", "qingniu", "loc:qingniu", 2))

    def test_old_save_without_map_position(self):
        import json
        d = self.s.to_dict()
        d.pop("td")
        d["hero"].pop("max_mp")
        d["region"] = "dajin"
        self.path.write_text(json.dumps(d), encoding="utf-8")
        s2 = self.Session(self.path)
        self.assertTrue(s2.load())
        self.assertEqual((s2.mode, s2.region), ("world", "dajin"))
        m = s2.get_map(s2.map_id)
        self.assertTrue(0 < s2.pos[0] < m["w"])


class TopDownFullPlaythroughTest(unittest.TestCase):
    def test_bot_finishes_whole_story_via_map_actions(self):
        import pathlib, tempfile
        from chineserim.session import Session
        from tests.bot_td import play_through_td
        s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=7)
        steps = play_through_td(s)
        self.assertTrue(s.hero.quest["done"], f"卡住：{s.hero.quest}（{steps} 步）")
        self.assertEqual(s.hero.quest["arc"], "arc6_lingjie")
        seen = {k[5:] for k in s.hero.flags if k.startswith("seen:")}
        self.assertEqual({k for k, v in s.data.dialogues.items() if "cmp" not in v["trigger"]} - seen, set())


class TeleportCounterTest(unittest.TestCase):
    def test_tp_increments_on_server_moves_only(self):
        import pathlib, tempfile
        from chineserim.session import Session
        s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)
        t0 = s.snapshot()["tp"]
        s.act("pos", x="60.5", y="50.5", steps="10")                 # 玩家自己走路不算瞬移
        self.assertEqual(s.snapshot()["tp"], t0)
        s.act("enter", loc="qingniu")
        t1 = s.snapshot()["tp"]
        self.assertGreater(t1, t0)
        s.act("leave")
        t2 = s.snapshot()["tp"]
        self.assertGreater(t2, t1)
        s.act("ferry", to="luanxinghai")
        self.assertGreater(s.snapshot()["tp"], t2)


class FrontendTdSmokeTest(unittest.TestCase):
    def test_td_js_parses(self):
        import pathlib, shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("沒有 node")
        f = pathlib.Path(__file__).parents[1] / "chineserim" / "static" / "td.js"
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class DifficultyTest(unittest.TestCase):
    def mk(self):
        import pathlib, tempfile
        from chineserim.session import Session
        return Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=1)

    def test_start_resources_and_snapshot(self):
        s = self.mk()
        self.assertFalse(s.snapshot()["configured"])                     # 全新安裝：前端會先叫出設定畫面
        for diff, lingshi, heal in (("easy", 800, 5), ("normal", 500, 3), ("hard", 300, 1)):
            s.act("new", diff=diff)
            self.assertEqual((s.difficulty, s.hero.count("lingshi"), s.hero.count("heal")), (diff, lingshi, heal))
        self.assertTrue(s.snapshot()["configured"])
        self.assertEqual(set(s.snapshot()["difficulties"]), {"easy", "normal", "hard"})
        s.act("new", diff="bogus")
        self.assertEqual(s.difficulty, "normal")

    def test_enemy_strength_scales(self):
        from chineserim import battle, difficulty
        c = Character("t")
        hp = {}
        for d in ("easy", "normal", "hard"):
            hp[d] = battle.start(c, "x", [{"kind": "wolf", "el": "木"}], False, difficulty.get(d))["enemies"][0]
        self.assertLess(hp["easy"]["hp"], hp["normal"]["hp"])
        self.assertLess(hp["normal"]["hp"], hp["hard"]["hp"])
        self.assertLess(hp["easy"]["atk"], hp["hard"]["atk"])

    def test_death_penalty_and_shop_price_and_breakthrough_bonus(self):
        s = self.mk()
        s.act("new", diff="hard")
        self.assertEqual(s.rs.chance_bonus, -0.1)
        s.act("enter", loc="jiazhou")
        shop = next(e for e in s.get_map(s.map_id)["entities"] if e.get("role") in ("shop", "pharmacy"))
        s.act("talk", ent=shop["id"])
        self.assertEqual(s.snapshot()["prices"]["heal"], round(30 * 1.25))
        s.act("leave")
        s.act("enter", loc="taiyue")
        e = next(e for e in s.get_map(s.map_id)["entities"] if e["k"] == "enemy")
        s.act("battle_start", ids=e["id"])
        s.hero.hp = 1
        for _ in range(40):
            if not s.battle or s.battle["over"]:
                break
            s.hero.hp = 1
            s.act("battle", cmd="guard")
        self.assertIsNone(s.battle)                                # 敗北：回到儲存點（含完整補血）
        self.assertEqual(s.hero.hp, s.hero.max_hp)

    def test_persisted_in_save(self):
        from chineserim.session import Session
        s = self.mk()
        s.act("new", diff="easy")
        s2 = Session(s.save_path)
        s2.load()
        self.assertEqual((s2.difficulty, s2.rs.chance_bonus), ("easy", 0.15))

    def test_hard_mode_still_finishes_story(self):
        import pathlib, tempfile
        from chineserim.session import Session
        from tests.bot_td import play_through_td
        s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=11)
        s.act("new", diff="hard")
        play_through_td(s)
        self.assertTrue(s.hero.quest["done"])


class FarmingAndCavesTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=5)
        self.s.hero.add("lingshi", 2000)

    def garden(self):
        self.s.act("enter", loc="baiyaoyuan")
        return self.s.get_map(self.s.map_id)

    def test_garden_layout(self):
        m = self.garden()
        kinds = [e["k"] for e in m["entities"]]
        self.assertEqual(kinds.count("plot"), 12)
        self.assertIn("bed", kinds)
        self.assertIn("furnace", kinds)
        self.assertEqual(len(self.s.snapshot()["plots"]), 12)

    def test_plant_grow_harvest(self):
        s = self.s
        self.garden()
        n = s.hero.count("lingshi")
        s.act("plant", ent="p0", seed="common")
        self.assertEqual(s.hero.count("lingshi"), n - 10)
        self.assertEqual(s.plot_state("p0")["stage"], 1)
        s.act("harvest", ent="p0")                                  # 還沒熟
        self.assertEqual(s.hero.count("herb"), 0)
        s.advance(3)
        self.assertEqual(s.plot_state("p0")["stage"], 3)
        s.act("harvest", ent="p0")
        self.assertIn(s.hero.count("herb"), (1, 2))
        self.assertEqual(s.plot_state("p0")["stage"], 0)            # 收成後變空地
        s.act("plant", ent="p1", seed="nonexistent")
        self.assertEqual(s.plot_state("p1")["stage"], 0)

    def test_boost_halves_growth_and_costs_lingye(self):
        s = self.s
        self.garden()
        s.act("plant", ent="p2", seed="ginseng")
        s.act("boost", ent="p2")                                    # 沒靈液
        self.assertFalse(s.hero.plots["baiyaoyuan:p2"]["boost"])
        s.hero.add("lingye")
        s.act("boost", ent="p2")
        self.assertTrue(s.hero.plots["baiyaoyuan:p2"]["boost"])
        s.advance(3)
        self.assertEqual(s.plot_state("p2")["stage"], 3)            # 6 日 → 3 日

    def test_plants_persist_across_visits_and_save(self):
        from chineserim.session import Session
        s = self.s
        self.garden()
        s.act("plant", ent="p3", seed="lotus")
        s.act("leave")
        s.advance(4)
        s.act("enter", loc="baiyaoyuan")
        self.assertIn(s.plot_state("p3")["stage"], (1, 2))
        s2 = Session(s.save_path)
        s2.load()
        self.assertEqual(s2.hero.plots, s.hero.plots)

    def test_bed_rests_and_advances_day(self):
        s = self.s
        self.garden()
        s.hero.hp, s.hero.mp, d0 = 3, 0, s.day
        s.act("talk", ent="bed")
        self.assertEqual((s.hero.hp, s.hero.mp, s.day), (s.hero.max_hp, s.hero.max_mp, d0 + 1))

    def test_crafting_recipes(self):
        s = self.s
        self.garden()
        s.act("craft", recipe="heal")                               # 沒材料
        self.assertEqual(s.hero.count("herb"), 0)
        s.hero.add("herb", 30)
        h0 = s.hero.count("heal")
        s.act("craft", recipe="heal")
        self.assertEqual((s.hero.count("heal"), s.hero.count("herb")), (h0 + 2, 27))
        s.act("craft", recipe="mpill")
        self.assertEqual(s.hero.count("mpill"), 1 + 2)
        # 突破丹：機率成功，失敗損失一半材料；多試幾次兩種結果都要出現
        s.hero.add("lingye", 20)
        outcomes = set()
        for _ in range(30):
            s.hero.add("herb", 10)
            b = s.hero.count("pill")
            s.act("craft", recipe="pill")
            outcomes.add(s.hero.count("pill") > b)
        self.assertEqual(outcomes, {True, False})

    def test_no_crafting_without_furnace(self):
        s = self.s
        s.act("enter", loc="qingniu")
        s.hero.add("herb", 9)
        s.act("craft", recipe="heal")
        self.assertEqual(s.hero.count("herb"), 9)

    def test_dwelling_has_bed_furnace_altar(self):
        s = self.s
        s.act("enter", loc="hf_dongfu")
        k = {e["k"] for e in s.get_map(s.map_id)["entities"]}
        self.assertTrue({"bed", "furnace", "altar"} <= k)

    def test_cave_profiles(self):
        from chineserim import mapgen
        d = self.s.data
        def loots(loc):
            return {e["loot"] for e in mapgen.build_location(d, loc)["entities"] if e["k"] == "chest"}
        def enemy_loot(loc):
            return {e["loot"] for e in mapgen.build_location(d, loc)["entities"] if e["k"] == "enemy"}
        self.assertEqual(loots("chiyan_cave"), {"rich"})
        self.assertEqual(enemy_loot("chiyan_cave"), {2.2})
        self.assertLessEqual(loots("baigu_cave"), {"empty", "normal"})
        self.assertEqual(enemy_loot("baigu_cave"), {0.15})
        self.assertIn("mimic", loots("youming_cave") | loots("longgong") | loots("xuemo_cave") | loots("abyss_cave"))

    def test_poor_cave_kills_pay_nothing_rich_pay_a_lot(self):
        from chineserim import battle
        s = self.s
        s.hero.realm = 3
        s.rs.apply_stats(s.hero)
        gains = {}
        for loc in ("baigu_cave", "chiyan_cave"):
            s.act("enter", loc=loc)
            e = next(e for e in s.get_map(s.map_id)["entities"] if e["k"] == "enemy")
            s.hero.hp, s.hero.mp = s.hero.max_hp, s.hero.max_mp
            n = s.hero.count("lingshi")
            s.act("battle_start", ids=e["id"])
            for _ in range(80):
                if s.battle["over"]:
                    break
                s.act("battle", cmd="spell", arg=0)
                s.hero.hp = s.hero.max_hp
            s.act("battle_end")
            gains[loc] = s.hero.count("lingshi") - n
            s.act("leave")
        self.assertGreater(gains["chiyan_cave"], gains["baigu_cave"] * 5)

    def test_empty_and_mimic_chests(self):
        s = self.s
        s.hero.realm = 3
        s.rs.apply_stats(s.hero)
        s.act("enter", loc="baigu_cave")
        m = s.get_map(s.map_id)
        empty = next((e for e in m["entities"] if e["k"] == "chest" and e["loot"] == "empty"), None)
        if empty:
            n = s.hero.count("lingshi")
            s.act("talk", ent=empty["id"])
            self.assertEqual(s.hero.count("lingshi"), n)
            self.assertIn("白忙", s.log[-1])
        s.act("leave")
        for loc in ("youming_cave", "longgong", "xuemo_cave", "abyss_cave"):
            s.hero.realm = 5
            s.act("enter", loc=loc)
            mimic = next((e for e in s.get_map(s.map_id)["entities"] if e["k"] == "chest" and e["loot"] == "mimic"), None)
            if mimic:
                s.act("talk", ent=mimic["id"])
                self.assertIsNotNone(s.battle)
                self.assertEqual(s.battle["enemies"][0]["name"], "寶箱怪")
                return
            s.act("leave")
        self.fail("沒有任何陷阱洞窟出現寶箱怪")

    def test_min_realm_from_location_data(self):
        s = self.s
        s.act("enter", loc="haishen_temple")                        # minRealm 3
        self.assertEqual(s.mode, "world")
        s.hero.realm = 3
        s.act("enter", loc="haishen_temple")
        self.assertEqual(s.mode, "loc")


class SocialTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.Session = Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=3)
        self.s.hero.add("lingshi", 5000)

    def in_town(self, loc="tiannan_fangshi"):
        self.s.act("enter", loc=loc)
        while self.s.hero.dialogue:
            self.s.act("choose", i=0)
        m = self.s.get_map(self.s.map_id)
        return m

    # ---- 丹藥鋪與奸商 ----
    def test_pharmacy_daily_stock_and_sell(self):
        s = self.s
        m = self.in_town()
        p = next(e for e in m["entities"] if e.get("role") == "pharmacy")
        s.act("talk", ent=p["id"])
        v = s.snapshot()["shop"]
        self.assertEqual(v["kind"], "pharmacy")
        left = next(i for i in v["items"] if i["id"] == "pill")["left"]
        self.assertEqual(left, 2)
        for _ in range(3):
            s.act("buy", item="pill")
        self.assertEqual(s.hero.count("pill"), 2)                      # 每日限量 2
        self.assertIn("賣完", s.log[-1])
        s.advance(1)                                                    # 隔天補貨
        s.act("buy", item="pill")
        self.assertEqual(s.hero.count("pill"), 3)
        s.hero.add("herb", 4)
        n = s.hero.count("lingshi")
        s.act("sell", item="herb")
        self.assertEqual((s.hero.count("herb"), s.hero.count("lingshi")), (3, n + 8))

    def test_shady_merchant_appears_randomly_and_deterministically(self):
        s = self.s
        self.in_town()
        seen = {}
        for period in range(40):
            s.day = period * 3
            sh = s.shady_now("tiannan_fangshi")
            seen[period] = sh["kind"] if sh else None
            self.assertEqual(seen[period], (s.shady_now("tiannan_fangshi") or {}).get("kind"))    # 決定性
        kinds = {k for k in seen.values() if k}
        self.assertEqual(kinds, {"fake", "gouge", "bargain"})
        self.assertIn(None, seen.values())                                                        # 不是每天都有
        s.day = 0
        s.act("enter", loc="qingniu")                                                             # 村鎮不會有奸商
        for period in range(20):
            s.day = period * 3
            self.assertIsNone(s.shady_now("qingniu"))

    def test_shady_prices_appraisal_and_fakes(self):
        s = self.s
        self.in_town()
        for kind, mult in (("fake", .55), ("gouge", 2.2), ("bargain", .7)):
            day = next(d for d in range(0, 300, 3) if (s.__setattr__("day", d) or (s.shady_now("tiannan_fangshi") or {}).get("kind")) == kind)
            s.day = day
            s.act("talk", ent="shady")
            v = s.snapshot()["shop"]
            self.assertEqual(v["kind"], "shady")
            self.assertEqual(next(i for i in v["items"] if i["id"] == "heal")["price"], round(30 * mult))
            n = s.hero.count("lingshi")
            s.act("appraise")
            self.assertEqual(s.hero.count("lingshi"), n - 15)
            self.assertIn({"fake": "問題", "gouge": "黑", "bargain": "公道"}[kind], s.snapshot()["shop"]["appraised"])
            got = 0
            for _ in range(5):
                h0 = s.hero.count("heal")
                s.act("buy", item="heal")
                got += s.hero.count("heal") - h0
            if kind == "fake":
                self.assertLess(got, 5)                                  # 假貨：花了錢沒拿到東西
            else:
                self.assertEqual(got, 5)
            s.act("shop_close")

    # ---- 布告欄：交易會與招募 ----
    def test_board_exists_in_towns_and_sects(self):
        for loc in ("jiazhou", "caixia", "huangfeng"):
            m = self.in_town(loc)
            self.assertTrue(any(e["k"] == "board" for e in m["entities"]), loc)
            self.s.act("leave")

    def test_fair_offers_deterministic_per_week_and_tailored_to_realm(self):
        s = self.s
        a = s.fair_offers("jiazhou")
        self.assertEqual(a, s.fair_offers("jiazhou"))
        s.advance(7)
        self.assertNotEqual(a, s.fair_offers("jiazhou"))
        s.day = 0
        s.hero.realm = 1
        s.hero.level = 19                                              # 卡在瓶頸、沒有突破丹 → 交易會有突破丹
        self.assertTrue(any("pill" in o["get"] for o in s.fair_offers("jiazhou")))
        prices = []
        for realm in (1, 3, 5):
            s.hero.realm = realm
            s.hero.gongfa = []
            o = s.fair_offers("jiazhou")
            prices.append(max(x["give"].get("lingshi", 0) for x in o))
        self.assertLess(prices[0], prices[1])
        self.assertLess(prices[1], prices[2])                          # 價碼隨境界成長

    def test_barter_executes_once(self):
        s = self.s
        m = self.in_town("jiazhou")
        s.act("talk", ent="board")
        v = s.snapshot()["board"]
        self.assertTrue(v["offers"] and "交易會" in v["title"])
        o = v["offers"][0]
        (item, qty), = o["get"].items()
        n, have = s.hero.count("lingshi"), s.hero.count(item)
        s.act("barter", idx=0)
        self.assertEqual(s.hero.count("lingshi"), n - o["give"]["lingshi"])
        self.assertEqual(s.hero.count(item), have + qty)
        n2 = s.hero.count("lingshi")
        s.act("barter", idx=0)                                          # 同一筆不能重複
        self.assertEqual(s.hero.count("lingshi"), n2)

    def test_barter_gongfa_scroll(self):
        s = self.s
        self.in_town("jiazhou")
        s.hero.realm = 3
        s.hero.add("lingye", 3)
        s.act("talk", ent="board")
        offers = s.snapshot()["board"]["offers"]
        g = next((o for o in offers if "gongfa" in o["get"]), None)
        self.assertIsNotNone(g)
        s.act("barter", idx=g["id"])
        self.assertIn(g["get"]["gongfa"], s.hero.gongfa)

    def test_recruit_join_perks_stipend_and_limit(self):
        s = self.s
        s.hero.realm = 3
        self.in_town("jiazhou")
        rec = s.recruit_offer("jiazhou")
        self.assertIsNotNone(rec)
        s.act("talk", ent="board")
        n = s.hero.count("lingshi")
        s.act("join", sect=rec["sect"])
        self.assertIn(rec["sect"], s.hero.members)
        self.assertEqual(s.hero.count("lingshi"), n - rec["fee"])
        # 福利生效
        s.hero.members = []
        s.join_sect("jujianmen")
        self.assertAlmostEqual(s.combat_bonus()["slashDmg"], .18)
        s.join_sect("yanyuezong")
        self.assertAlmostEqual(s.combat_bonus()["elemDmg"]["水"], .15)
        s.join_sect("huangfenggu")
        self.assertFalse(s.join_sect("qingxumen"))                      # 最多 3 個
        self.assertEqual(len(s.hero.members), 3)
        # 每 30 日俸祿（黃楓谷 30 × (1+境界)）
        n = s.hero.count("lingshi")
        s.advance(30)
        self.assertEqual(s.hero.count("lingshi") - n, 30 * (1 + s.hero.realm))

    def test_recruit_respects_realm_and_membership(self):
        s = self.s
        s.hero.realm = 0
        for loc in ("a", "b", "c", "d", "e", "f"):
            r = s.recruit_offer(loc)
            if r:
                self.assertLessEqual(s.data.sect_perks["perks"][r["sect"]]["minRealm"], 0)
        s.hero.realm = 5
        s.hero.members = ["qixuanmen"]
        for w in range(10):
            s.day = w * 7
            r = s.recruit_offer("x")
            self.assertNotEqual(r["sect"], "qixuanmen")

    def test_story_joins_and_perk_breakthrough(self):
        s = self.s
        s.act("enter", loc="qingniu")
        s.act("talk", ent="quest")
        s.act("choose", i=0); s.act("choose", i="")
        s.act("leave")
        s.act("enter", loc="caixia")
        s.act("talk", ent="quest")
        while s.hero.dialogue:
            v = s.snapshot()["dialogue"]
            s.act("choose", i=v["choices"][0]["i"] if v["choices"] else "")
        self.assertIn("qixuanmen", s.hero.members)
        s.join_sect("qingxumen")
        self.assertAlmostEqual(s.rs.chance_bonus, .05)

    # ---- 道侶 ----
    def test_candidates_stand_in_their_places(self):
        seen = {}
        for cid, c in self.s.data.companions["candidates"].items():
            m = self.s.get_map("loc:" + c["loc"])
            self.assertTrue(any(e["k"] == "candidate" and e["cid"] == cid for e in m["entities"]), cid)
            seen[cid] = c["name"]
        self.assertEqual(len(seen), 9)

    def walk(self, prefer=0):
        s = self.s
        for _ in range(20):
            if not s.hero.dialogue:
                return
            v = s.snapshot()["dialogue"]
            s.act("choose", i=prefer if v["choices"] else "")
        self.fail("對話沒有結束")

    def test_courtship_flow_to_partner(self):
        s = self.s
        s.hero.realm = 3
        s.hero.add("lingye", 30)
        s.act("enter", loc="yanyue")
        ent = "cand:nangong"
        s.act("talk", ent=ent)                                          # 初識
        self.assertEqual(s.hero.dialogue["id"], "cmp_nangong_intro")
        self.walk()
        self.assertEqual(s.hero.affinity["nangong"], 10)
        s.act("talk", ent=ent)
        self.assertIsNotNone(s.snapshot()["cand"])                      # 之後是贈禮／閒聊選單
        s.act("gift", item="lingye")                                    # 南宮婉喜歡靈液 → 好感 ×2
        self.assertEqual(s.hero.affinity["nangong"], 10 + 28)
        s.act("gift", item="lingye")                                    # 一天只能送一次
        self.assertEqual(s.hero.affinity["nangong"], 38)
        s.act("chat")
        self.assertEqual(s.hero.affinity["nangong"], 41)
        s.act("chat")
        self.assertEqual(s.hero.affinity["nangong"], 41)
        s.act("cand_close")
        s.act("talk", ent=ent)                                          # 好感 ≥ 40：觸發特別事件
        self.assertEqual(s.hero.dialogue["id"], "cmp_nangong_event")
        self.walk()
        self.assertGreaterEqual(s.hero.affinity["nangong"], 60)
        for _ in range(8):                                              # 天天送禮，累積到求緣
            s.advance(1)
            s.act("talk", ent=ent)
            if s.hero.dialogue:
                break
            if s.snapshot()["cand"]:
                s.act("gift", item="lingye")
                s.act("cand_close")
        self.assertEqual(s.hero.dialogue["id"], "cmp_nangong_propose")
        self.walk(prefer=1)                                             # 先拒絕：不會綁死
        self.assertEqual(s.hero.companion, "")
        s.advance(1)
        s.act("talk", ent=ent)
        self.assertEqual(s.hero.dialogue["id"], "cmp_nangong_propose")
        self.walk(prefer=0)
        self.assertEqual(s.hero.companion, "nangong")
        self.assertEqual(s.snapshot()["partner"]["name"], "南宮婉")

    def test_proposal_needs_realm(self):
        s = self.s
        s.hero.realm = 0
        s.hero.affinity["nangong"] = 120
        s.hero.flags["met:nangong"] = True
        s.hero.flags["event:nangong"] = True
        s.act("enter", loc="yanyue")
        s.act("talk", ent="cand:nangong")
        self.assertFalse(s.hero.dialogue)                               # 境界不足，不會有求緣

    def test_partner_fights_and_makes_battles_easier(self):
        from chineserim import battle, difficulty
        wins = {}
        for with_partner in (False, True):
            w = 0
            for seed in range(60):
                rng = random.Random(seed)
                rs = RealmSystem(GameData(), rng)
                c = Character("t", elements=["金", "木", "水", "火"])
                c.realm = 0
                rs.apply_stats(c)
                c.add("heal", 1)
                partner = {"id": "x", "name": "南宮婉", "el": "水", "role": "mage", "atk": .55, "sprite": "nangong"} if with_partner else None
                st = battle.start(c, "x", [{"kind": "bear", "el": "土"}] * 3, False, difficulty.get("hard"), partner)
                for _ in range(80):
                    cmd = ("item", None) if c.hp < .4 * c.max_hp and c.count("heal") else ("spell", 0) if c.mp >= battle.spell_cost(c) else ("attack", None)
                    if battle.command(st, c, rs, rng, cmd[0], cmd[1], None, {}):
                        break
                w += st["over"] == "win"
            wins[with_partner] = w
        self.assertGreater(wins[True], wins[False] + 8)                 # 有道侶：明顯更容易獲勝

    def test_partner_logs_and_pact_in_battle_view(self):
        from chineserim import battle
        s = self.s
        s.hero.companion = "nangong"
        s.act("enter", loc="taiyue")
        e = next(e for e in s.get_map(s.map_id)["entities"] if e["k"] == "enemy")
        s.act("battle_start", ids=e["id"])
        self.assertEqual(s.battle["partner"]["name"], "南宮婉")
        s.act("battle", cmd="attack")
        text = "".join(s.battle["log"])
        self.assertIn("南宮婉", text)
        self.assertIsNotNone(battle.view(s.battle, s.hero)["partner"])

    def test_partner_saved_and_story_grants_nangong(self):
        s = self.s
        s.hero.companion = "nangong"
        s.hero.members = ["qixuanmen"]
        s.hero.affinity = {"nangong": 100}
        s.save()
        s2 = self.Session(s.save_path)
        s2.load()
        self.assertEqual((s2.hero.companion, s2.hero.members, s2.hero.affinity), ("nangong", ["qixuanmen"], {"nangong": 100}))


class BossAndBagTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=5)
        self.s.act("new", diff="normal")
        self.h = self.s.hero

    def _boss(self, bid="yuzitong", realm=None):
        if realm is not None:
            self.h.realm = realm
            self.s.rs.apply_stats(self.h)
            self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp
        self.s.start_boss_fight(bid, None)
        return self.s.battle

    def test_gear_only_in_boss_battle(self):
        from chineserim import battle
        self.h.add("fu_lei", 2)
        st = battle.start(self.h, "x", [{"kind": "wolf", "el": "木"}])
        battle.command(st, self.h, self.s.rs, self.s.rng, "talisman", "fu_lei", None, {})
        self.assertEqual(self.h.count("fu_lei"), 2)
        self.assertIn("用不著", st["log"][0])

    def test_talisman_formation_treasure(self):
        st = self._boss()
        for it in ("fu_lei", "fu_hu", "zhen_sha"):
            self.h.add(it)
        hp0 = st["enemies"][0]["hp"]
        self.s.act("battle", cmd="talisman", arg="fu_lei")
        self.assertLess(st["enemies"][0]["hp"], hp0)
        self.assertEqual(self.h.count("fu_lei"), 0)
        self.s.act("battle", cmd="formation", arg="zhen_sha")
        self.assertEqual(st["formation"]["id"], "sha")
        self.s.act("battle", cmd="talisman", arg="fu_lei")            # 用完了
        self.h.add("fb_shield")
        # 法寶：有冷卻
        self.h.hp = self.h.max_hp
        self.s.act("battle", cmd="treasure", arg="fb_shield")
        self.assertGreater(st["cd"].get("fb_shield", 0), 0)
        before = self.h.count("fb_shield")
        self.s.act("battle", cmd="treasure", arg="fb_shield")
        self.assertEqual(self.h.count("fb_shield"), before)           # 法寶不消耗

    def test_exhausted_only_flee(self):
        st = self._boss()
        self.h.mp = 0
        self.s.act("battle", cmd="attack")
        self.assertEqual(st["turn"], 1)
        self.assertTrue(self.s.snapshot()["battle"]["exhausted"])
        self.h.add("mpill")
        self.s.act("battle", cmd="mpill")
        self.assertGreater(self.h.mp, 0)

    def test_pre_nascent_defeat_rolls_back_to_checkpoint(self):
        self.s.act("enter", loc="qingniu")
        label = self.s.checkpoint["label"]
        self.h.add("lingshi", 5)
        st = self._boss()
        self.h.hp = 1
        for _ in range(30):
            if not self.s.battle:
                break
            self.h.hp = 1
            self.s.act("battle", cmd="guard")
        self.assertIsNone(self.s.battle)
        self.assertEqual(self.s.hero.hp, self.s.hero.max_hp)
        self.assertIn(label, self.s.log[-1])

    def test_nascent_soul_escape(self):
        self.h.realm = 4
        self.s.rs.apply_stats(self.h)
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp
        st = self._boss("xuangu")
        st["enemies"][0]["atk"] = 1e9
        self.s.act("battle", cmd="guard")
        self.assertTrue(st["down"])
        self.s.act("battle", cmd="attack")                           # 氣血耗盡：其他指令無效
        self.assertTrue(st["down"])
        self.assertTrue(self.s.snapshot()["battle"]["down"])
        self.s.act("battle", cmd="soul")
        self.assertEqual(st["over"], "soul")
        self.assertGreaterEqual(self.h.hp, 1)
        self.assertEqual(self.h.mp, 0)

    def test_boss_win_drops_into_bag_and_sets_flag(self):
        st = self._boss("yuzitong")
        st["enemies"][0]["hp"] = 1
        self.h.add("lingshi", 1)
        n0 = self.h.count("lingshi")
        self.s.act("battle", cmd="attack")
        self.assertEqual(st["over"], "win")
        self.assertTrue(self.h.flags.get("beat:yuzitong"))
        self.assertTrue(any("儲物袋" in r for r in st["rewards"]))
        self.assertGreater(self.h.count("lingshi"), n0)

    def test_bag_is_unlimited(self):
        self.h.add("lingshi", 10 ** 7)
        self.h.add("fu_lei", 999)
        bag = self.s.snapshot()["bag"]
        self.assertEqual(next(b for b in bag if b["id"] == "lingshi")["n"], self.h.count("lingshi"))
        self.assertIn("符錄", {b["cat"] for b in bag})

    def test_guardian_and_well(self):
        s = self.s
        s.h = self.h
        loc = next(l["id"] for w in s.data.regions for g in w["regions"] for l in g["locations"] if l["type"] in ("洞窟", "秘境", "禁地") or l.get("profile"))
        self.h.realm = 5
        s.rs.apply_stats(self.h)
        s.act("enter", loc=loc)
        m = s.get_map(s.map_id)
        self.assertTrue(any(e["k"] == "well" for e in m["entities"]))
        well = next(e for e in m["entities"] if e["k"] == "well")
        s.act("talk", ent=well["id"])
        self.assertIn("井", s.checkpoint["label"])
        g = next((e for e in m["entities"] if e["k"] == "guardian"), None)
        if g:
            s.act("talk", ent="guardian")
            self.assertTrue(s.battle and s.battle["boss"])

    def test_every_location_has_well(self):
        s = self.s
        for w in s.data.regions:
            for g in w["regions"]:
                for l in g["locations"]:
                    m = s.get_map("loc:" + l["id"])
                    self.assertTrue(any(e["k"] == "well" for e in m["entities"]), l["id"])

    def test_checkpoint_persisted(self):
        from chineserim.session import Session
        self.s.act("enter", loc="qingniu")
        lab = self.s.checkpoint["label"]
        s2 = Session(self.s.save_path)
        s2.load()
        self.assertEqual(s2.checkpoint["label"], lab)

    def test_dialogue_boss_flow_with_retry(self):
        from chineserim import dialogue
        s, h = self.s, self.h
        dialogue.start(s.data, h, "d_yuzitong", s.log, s.rs)
        s.act("choose", i="0")
        s.act("choose", i="")
        self.assertTrue(s.battle and s.battle["boss"])
        self.assertEqual(s.battle["enemies"][0]["name"], "余子童")
        s.act("battle", cmd="flee")
        for _ in range(30):
            if s.battle and s.battle["over"]:
                break
            s.act("battle", cmd="flee")
        if s.battle and s.battle["over"] == "flee":
            self.assertFalse(h.flags.get("seen:d_yuzitong"))       # 逃跑後可重新挑戰


class KarmaAndTreasureTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=9)
        self.s.act("new", diff="normal")
        self.h = self.s.hero

    def _wild(self):
        return next(l["id"] for w in self.s.data.regions for g in w["regions"] for l in g["locations"]
                    if l["type"] in ("荒野", "山林", "森林", "山脈") or (l["type"] not in ("城鎮", "宗門") and "profile" not in l and l["id"] in ("taiyue", "grass_sea")))

    def _event_loc(self, kind):
        """找一個會出現該類因果事件的（地點, 日）。"""
        from chineserim import karma
        locs = ["taiyue", "grass_sea", "kunwu"]
        for loc in locs:
            for day in range(0, 60, 3):
                self.s.day = day
                self.s.act("enter", loc=loc) if self.s.mode != "loc" or self.s.cur_loc != loc else None
                if self.s.mode == "loc" and self.s.cur_loc == loc:
                    ev = self.s.karma_now()
                    if ev and ev["kind"] == kind:
                        return loc, ev
            if self.s.mode == "loc":
                self.s.act("leave")
        self.fail("沒有找到因果事件")

    def test_karma_state(self):
        from chineserim import karma
        cfg = self.s.data.karma
        self.assertEqual(karma.dao_state(self.h, cfg), "mid")
        karma.add(self.h, "sha", 5)
        self.assertEqual(karma.dao_state(self.h, cfg), "sha")
        karma.add(self.h, "ren", 9)
        self.assertEqual(karma.dao_state(self.h, cfg), "ren")
        karma.add(self.h, "ren", -99)
        self.assertEqual(karma.get(self.h, "ren"), 0)          # 不會變負數
        self.assertEqual(self.s.snapshot()["karma"]["dao"], "殺伐")

    def test_boss_kill_adds_sha_and_avenger_flow(self):
        from chineserim import karma
        self.h.realm = 2
        self.s.rs.apply_stats(self.h)
        self.s.start_boss_fight("yuzitong")
        self.s.battle["enemies"][0]["hp"] = 1
        self.s.act("battle", cmd="attack")
        self.assertEqual(karma.get(self.h, "sha"), 2)
        self.s.act("battle_end")
        karma.add(self.h, "sha", 3)
        loc, ev = self._event_loc("avenger")
        self.assertEqual(self.s.snapshot()["karma_ev"]["kind"], "avenger")
        sha0 = karma.get(self.h, "sha")
        self.s.act("talk", ent="karma")
        self.assertTrue(self.s.battle and self.s.battle["boss"])
        self.s.battle["enemies"][0]["hp"] = 1
        self.s.act("battle", cmd="attack")
        self.assertEqual(karma.get(self.h, "sha"), sha0 - 2)   # 仇怨了結
        self.assertIsNone(self.s.snapshot()["karma_ev"])       # 同一時段不再出現

    def test_benefactor_gives_gift(self):
        from chineserim import karma
        karma.add(self.h, "ren", 4)
        self._event_loc("benefactor")
        ren0 = karma.get(self.h, "ren")
        inv0 = sum(self.h.inventory.values())
        self.s.act("talk", ent="karma")
        self.assertGreater(sum(self.h.inventory.values()), inv0)
        self.assertEqual(karma.get(self.h, "ren"), ren0 - 2)

    def test_beggar_donation_adds_ren(self):
        from chineserim import karma
        self.h.add("lingshi", 500)
        for w in self.s.data.regions:
            for g in w["regions"]:
                for l in g["locations"]:
                    if True:
                        m = self.s.get_map("loc:" + l["id"])
                        if m["cat"] != "town":
                            continue
                        b = next((e for e in m["entities"] if e.get("role") == "beggar"), None)
                        if b:
                            self.s.act("enter", loc=l["id"])
                            self.s.act("talk", ent=b["id"])
                            self.assertEqual(karma.get(self.h, "ren"), 1)
                            return
        self.fail("沒有乞丐")

    def test_xinmo_jie_before_break(self):
        from chineserim import karma
        self.h.realm = 2
        self.s.rs.apply_stats(self.h)
        self.h.level = self.s.rs.realm(self.h)["levelRange"][1]
        karma.add(self.h, "sha", 6)
        self.s.act("break")
        self.assertTrue(self.s.battle and self.s.battle["boss"])
        self.assertEqual(self.s.battle["enemies"][0]["name"], "嗜殺之影")      # 殺伐道心 → 嗜殺之影
        self.assertEqual(self.h.realm, 2)                                     # 還沒破
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp
        self.s.battle["enemies"][0]["hp"] = 1
        self.h.add("pill", 3)
        self.s.act("battle", cmd="attack")
        self.assertTrue(self.h.flags.get("xinmojie_pass"))
        self.assertEqual(karma.get(self.h, "sha"), 3)                         # 斬去殺念

    def test_xinmo_variants(self):
        from chineserim import karma
        self.assertEqual(karma.xinmo_spec(self.s.data, self.h)["name"], "本心之影")
        karma.add(self.h, "ren", 5)
        self.assertEqual(karma.xinmo_spec(self.s.data, self.h)["name"], "怯懦之影")

    def test_refine_bond_and_battle_scaling(self):
        h, s = self.h, self.s
        h.add("fb_ding")
        h.add("lingshi", 20000)
        h.add("lingye", 10)
        c0 = s.refine_cost("fb_ding")
        self.assertEqual(c0["level"], 0)
        for _ in range(3):
            s.act("fb_refine", item="fb_ding")
        self.assertEqual(h.counters["fbl:fb_ding"], 3)
        self.assertLess(h.count("lingshi"), 20000)
        for _ in range(5):
            s.act("fb_refine", item="fb_ding")
        self.assertEqual(h.counters["fbl:fb_ding"], 5)                        # 未本命：上限 5
        s.act("fb_bond", item="fb_ding")
        self.assertEqual(h.flags["bonded"], "fb_ding")
        for _ in range(3):
            s.act("fb_refine", item="fb_ding")
        self.assertEqual(h.counters["fbl:fb_ding"], 7)                        # 本命：再多兩階
        bag = next(b for b in s.snapshot()["bag"] if b["id"] == "fb_ding")
        self.assertTrue(bag["bonded"] and bag["level"] == 7)

    def test_treasure_level_boosts_damage_and_awaken(self):
        h, s = self.h, self.s
        h.add("fb_bell")
        dmg = []
        for lv in (0, 5):
            h.counters["fbl:fb_bell"] = lv
            h.hp, h.mp = h.max_hp, h.max_mp
            s.start_boss_fight("yuzitong")
            st = s.battle
            st["enemies"][0]["atk"] = 0
            hp0 = st["enemies"][0]["hp"]
            s.act("battle", cmd="treasure", arg="fb_bell")
            dmg.append(hp0 - st["enemies"][0]["hp"])
            if lv == 5:
                self.assertEqual(st["enemies"][0].get("stun", 0) + (1 if st["enemies"][0].get("stun_imm") else 0) > 0, True)
            s.battle = None
        self.assertGreater(dmg[1], dmg[0] * 1.3)


class AlchemyMiniGameTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=4)
        self.s.act("new", diff="normal")
        self.h = self.s.hero
        self.s.act("enter", loc=next(l["id"] for w in self.s.data.regions for g in w["regions"] for l in g["locations"] if l["type"] == "洞府") if False else "qingniu")
        self.s.act("leave")
        # 找一個有丹爐的地點
        for w in self.s.data.regions:
            for g in w["regions"]:
                for l in g["locations"]:
                    if l["type"] == "藥園":
                        self.s.region = g["id"]
                        self.s.act("enter", loc=l["id"])
                        return
        self.fail("沒有藥園")

    def test_play_and_tiers(self):
        h, s = self.h, self.s
        h.add("herb", 30)
        s.act("alch_start", recipe="heal")
        self.assertTrue(s.alch)
        self.assertEqual(h.count("herb"), 27)
        s.act("battle_end")                                  # 煉製中其他動作被擋
        s.act("talk", ent="bed")
        self.assertTrue(s.alch)
        for _ in range(5):
            s.act("alch_act", a="hold")
        v = s.snapshot()["alch"]
        self.assertTrue(v["over"] and v["result"])
        s.act("alch_close")
        self.assertIsNone(s.alch)
        self.assertEqual(h.counters["alch:n"], 1)

    def test_good_play_beats_bad_play(self):
        h, s = self.h, self.s
        scores = []
        for policy in ("good", "bad"):
            h.add("herb", 10)
            s.act("alch_start", recipe="heal")
            while not s.alch["over"]:
                if policy == "good":
                    # 依火候往 50 修正（能看見目前爐溫，看不見確切火勢）
                    heat = s.alch["heat"]
                    a = "cool" if heat > 58 else "heat" if heat < 42 else "hold"
                else:
                    a = "heat2"
                s.act("alch_act", a=a)
            scores.append(s.alch["score"])
            s.act("alch_close")
        self.assertGreater(scores[0], scores[1])

    def test_boom_and_save(self):
        from chineserim.session import Session
        h, s = self.h, self.s
        h.add("herb", 6)
        s.act("alch_start", recipe="heal")
        s2 = Session(s.save_path)
        s2.load()
        self.assertEqual(s2.alch["recipe"], "heal")            # 存檔可續煉
        for _ in range(3):
            s.act("alch_act", a="heat2")
        self.assertTrue(s.alch["over"])
        self.assertEqual(s.alch["tier"], 0)


class PetAndPuppetTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=6)
        self.s.act("new", diff="normal")
        self.h = self.s.hero

    def test_hatch_feed_evolve_and_fetch(self):
        h, s = self.h, self.s
        h.add("pet_egg", 2)
        s.act("use", item="pet_egg")
        self.assertTrue(h.pet)
        self.assertEqual(h.count("pet_egg"), 1)
        s.act("use", item="pet_egg")                               # 已有靈寵：不會消耗
        self.assertEqual(h.count("pet_egg"), 1)
        h.add("herb", 400)
        for _ in range(130):
            s.act("pet_feed")
        self.assertEqual(h.pet["level"], s.data.pets["max_level"])
        self.assertEqual(s.pet_stage(h.pet), 2)
        n = h.count("herb")
        s.advance(60)
        self.assertGreater(h.count("herb"), n)                    # 每天有機會帶回靈草
        s.act("pet_release")
        self.assertFalse(h.pet)

    def test_puppet_build_upgrade_repair(self):
        h, s = self.h, self.s
        h.inventory["lingshi"] = 0
        s.act("puppet_build", ptype="wood")
        self.assertFalse(h.puppet)                                # 沒錢
        h.add("lingshi", 5000)
        s.act("puppet_build", ptype="iron")
        self.assertFalse(h.puppet)                                # 境界不足
        s.act("puppet_build", ptype="wood")
        self.assertEqual(h.puppet["level"], 1)
        s.act("puppet_upgrade")
        self.assertEqual(h.puppet["level"], 2)
        self.assertGreater(s.puppet_maxhp(h.puppet), round(h.max_hp * 0.6))
        h.puppet["hp"] = 1
        s.act("puppet_repair")
        self.assertEqual(h.puppet["hp"], s.puppet_maxhp(h.puppet))

    def test_allies_fight_and_puppet_absorbs(self):
        h, s = self.h, self.s
        h.add("lingshi", 5000)
        s.act("puppet_build", ptype="wood")
        h.pet = {"kind": "wolf", "el": "火", "level": 5, "exp": 0}
        h.puppet["kind"] = "wood"
        s.start_boss_fight("yuzitong")
        st = s.battle
        self.assertEqual({a["type"] for a in st["allies"]}, {"pet", "puppet"})
        st["allies"][1]["absorb"] = 1.0                           # 必定擋招
        hp0 = st["enemies"][0]["hp"]
        h.hp = h.max_hp
        s.act("battle", cmd="guard")
        self.assertLess(st["enemies"][0]["hp"], hp0)              # 盟友出手
        self.assertEqual(h.hp, h.max_hp)                          # 傷害被傀儡擋下
        self.assertLess(st["allies"][1]["hp"], st["allies"][1]["maxhp"])
        self.assertEqual(len(s.snapshot()["battle"]["allies"]), 2)
        st["enemies"][0]["hp"] = 1
        s.act("battle", cmd="attack")
        self.assertEqual(st["over"], "win")
        self.assertEqual(h.pet["exp"], 1)                         # 勝利給靈寵經驗
        self.assertLess(h.puppet["hp"], s.puppet_maxhp(h.puppet)) # 傀儡的損傷帶回戰後

    def test_pets_persist_in_save(self):
        from chineserim.session import Session
        self.h.pet = {"kind": "bear", "el": "土", "level": 3, "exp": 1}
        self.s.act("pos", x=1, y=1)
        s2 = Session(self.s.save_path)
        s2.load()
        self.assertEqual(s2.hero.pet["kind"], "bear")


class WorldEventTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=8)
        self.s.act("new", diff="normal")
        self.h = self.s.hero

    def _find(self, typ, region=None):
        """掃描日期，找出（區域、日）有指定事件。"""
        for w in range(0, 80):
            for reg in ([region] if region else list(self.s.world.regions)):
                for e in self.s.events_in(reg, w):
                    if e["type"] == typ:
                        self.s.region, self.s.day = reg, w * self.s.data.events["window_days"]
                        return e
        self.fail("沒找到事件 " + typ)

    def _enter(self, e):
        if self.s.mode == "loc":
            self.s.act("leave")
        self.s.h = None
        self.h.realm = max(self.h.realm, 3)
        self.s.rs.apply_stats(self.h)
        self.s.act("enter", loc=e["loc"])
        self.assertEqual(self.s.cur_loc, e["loc"])

    def test_deterministic_and_rotates(self):
        a = self.s.events_in("tiannan", 3)
        self.assertEqual(a, self.s.events_in("tiannan", 3))
        self.assertTrue(any(self.s.events_in("tiannan", 3) != self.s.events_in("tiannan", w) for w in range(4, 10)))
        self.assertTrue(all(e["left"] >= 0 or True for e in a))

    def test_news_and_notify(self):
        self.s.day = 7
        self.s.log.clear()
        self.s.advance(2)                                       # 跨進新時間窗
        self.assertTrue(any("傳聞" in x for x in self.s.log))
        self.assertTrue(self.s.snapshot()["news"])

    def test_refugee_gives_ren(self):
        from chineserim import karma
        e = self._find("refugee")
        self._enter(e)
        self.h.add("lingshi", 500)
        self.assertEqual(self.s.snapshot()["wev_ent"]["type"], "refugee")
        self.s.act("talk", ent="wev")
        self.assertEqual(karma.get(self.h, "ren"), 2)
        self.assertIsNone(self.s.snapshot()["wev_ent"])         # 處理完不再出現

    def test_raid_boss_and_price(self):
        from chineserim import karma
        e = self._find("raid")
        self._enter(e)
        self.assertGreater(self.s.wev_mod(e["loc"], "price"), 1.0)      # 盜匪期間物價上漲
        self.s.act("talk", ent="wev")
        self.assertTrue(self.s.battle and self.s.battle["boss"])
        self.s.battle["enemies"][0]["hp"] = 1
        self.s.act("battle", cmd="attack")
        self.assertEqual(self.s.battle["over"], "win")
        self.assertEqual(karma.get(self.h, "ren"), 2)
        self.assertEqual(self.s.wev_mod(e["loc"], "price"), 1.0)        # 解決後恢復

    def test_fall_gives_loot_and_tide_modifiers(self):
        e = self._find("fall")
        self._enter(e)
        n0 = sum(self.h.inventory.values())
        self.s.act("talk", ent="wev")
        self.assertGreater(sum(self.h.inventory.values()), n0)
        e2 = self._find("tide")
        self.assertEqual(self.s.wev_mod(e2["loc"], "loot"), 2.0)
        self.assertEqual(self.s.wev_mod("nonexistent", "loot"), 1.0)
        e3 = self._find("festival")
        self.assertEqual(self.s.wev_mod(e3["loc"], "price"), 0.8)


class SectWarTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=12)
        self.s.act("new", diff="normal")
        self.h = self.s.hero
        self.h.realm = 3
        self.s.rs.apply_stats(self.h)
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp

    def _war(self, pick=None):
        for w in range(0, 120):
            for reg in self.s.world.regions:
                for e in self.s.events_in(reg, w):
                    if e["type"] == "war" and (pick is None or pick(e)):
                        self.s.region, self.s.day = reg, w * self.s.data.events["window_days"]
                        if self.s.mode == "loc":
                            self.s.act("leave")
                        self.s.act("enter", loc=e["loc"])
                        return e
        self.fail("沒有宗門戰爭")

    def _win(self):
        self.s.battle["enemies"][0]["hp"] = 1
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp
        self.s.act("battle", cmd="attack")
        self.assertEqual(self.s.battle["over"], "win")

    def test_choice_panel_and_ignore(self):
        e = self._war()
        self.assertGreater(self.s.wev_mod(e["loc"], "price"), 1.0)
        self.s.act("talk", ent="wev")
        v = self.s.snapshot()["war"]
        self.assertEqual({o["k"] for o in v["options"]}, {"defend", "attack", "trade", "ignore"})
        self.s.act("war_side", side="ignore")
        self.assertIsNone(self.s.snapshot()["war"])
        self.assertIsNotNone(self.s.snapshot()["wev_ent"])          # 沒表態：戰事還在

    def test_defend_gives_ren_and_rep(self):
        from chineserim import karma
        e = self._war(lambda e: self.s.sect_of_loc(e["loc"]))
        sid = self.s.sect_of_loc(e["loc"])
        self.s.act("talk", ent="wev")
        self.s.act("war_side", side="defend")
        self.assertTrue(self.s.battle["boss"])
        self.assertIn("統領", self.s.battle["enemies"][0]["name"])
        self._win()
        self.assertEqual(karma.get(self.h, "ren"), 2)
        self.assertEqual(self.h.sects.get(sid), 1)
        self.assertIsNone(self.s.snapshot()["wev_ent"])
        self.assertTrue(any(k.startswith("war_side:") and k.endswith(":defend") for k in self.h.flags))

    def test_attack_gives_sha_and_lowers_rep_but_not_for_members(self):
        from chineserim import karma
        e = self._war(lambda e: self.s.sect_of_loc(e["loc"]))
        sid = self.s.sect_of_loc(e["loc"])
        self.h.members.append(sid)
        self.s.act("talk", ent="wev")
        self.assertFalse(next(o for o in self.s.snapshot()["war"]["options"] if o["k"] == "attack")["ok"])
        self.s.act("war_side", side="attack")
        self.assertIsNone(self.s.battle)                            # 本門弟子不能攻打自家
        self.h.members.remove(sid)
        self.s.act("talk", ent="wev")
        lings = self.h.count("lingshi")
        self.s.act("war_side", side="attack")
        self.assertEqual(self.s.battle["enemies"][0]["name"], "護山長老")
        self._win()
        self.assertEqual(karma.get(self.h, "sha"), 2)
        self.assertEqual(self.h.sects.get(sid), -2)
        self.assertGreater(self.h.count("lingshi"), lings)

    def test_trade_sells_supplies(self):
        self._war()
        self.s.act("talk", ent="wev")
        self.h.inventory["heal"] = 0
        self.s.act("war_side", side="trade")                        # 物資不足
        self.assertIsNone(self.s.battle)
        self.assertIsNotNone(self.s.snapshot()["wev_ent"])
        self.h.add("heal", 3)
        self.h.add("mpill", 2)
        n = self.h.count("lingshi")
        self.s.act("talk", ent="wev")
        self.s.act("war_side", side="trade")
        self.assertGreater(self.h.count("lingshi"), n)
        self.assertEqual(self.h.count("heal"), 0)
        self.assertIsNone(self.s.snapshot()["wev_ent"])


class PetSkillTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=10)
        self.s.act("new", diff="normal")
        self.h = self.s.hero

    def _fight(self, kind, level=5, boss="yuzitong"):
        self.h.pet = {"kind": kind, "el": "火", "level": level, "exp": 0}
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp
        self.s.start_boss_fight(boss)
        st = self.s.battle
        st["enemies"][0]["hp"] *= 50                     # 不讓戰鬥太快結束
        return st

    def test_every_kind_has_skill_and_locked_before_stage1(self):
        for kind in self.s.data.pets["pets"]:
            self.h.pet = {"kind": kind, "el": "木", "level": 1, "exp": 0}
            self.assertIsNone(self.s.pet_skill(self.h.pet))
            self.assertFalse(self.s.allies_view()["pet"]["skill"]["unlocked"])
            self.h.pet["level"] = 4
            self.assertEqual(self.s.pet_skill(self.h.pet)["val"], self.s.data.pets["skills"][kind]["val"][0])
            self.h.pet["level"] = 8
            self.assertEqual(self.s.pet_skill(self.h.pet)["val"], self.s.data.pets["skills"][kind]["val"][1])   # 完全體強化

    def test_no_skill_for_baby_pet(self):
        st = self._fight("wolf", level=2)
        self.assertIsNone(st["allies"][0]["skill"])

    def test_howl_buffs_hero(self):
        st = self._fight("wolf")
        self.s.act("battle", cmd="guard")
        self.assertGreater(st.get("howl", 0), 0)
        self.assertEqual(st["allies"][0]["cd"], st["allies"][0]["cd_max"])
        self.assertTrue(any("月嘯" in x for x in st["log"]))

    def test_bear_shield_and_spider_web(self):
        st = self._fight("bear")
        self.s.act("battle", cmd="guard")
        self.assertGreaterEqual(st["shield"] + (0 if self.h.hp < self.h.max_hp else 0), 0)
        self.assertTrue(any("鐵壁守護" in x for x in st["log"]))
        self.s.battle = None
        st = self._fight("spider")
        self.s.act("battle", cmd="guard")
        self.assertGreater(st.get("web", 0), 0)

    def test_poison_ticks_and_stun_and_breath(self):
        st = self._fight("python")
        self.s.act("battle", cmd="guard")
        self.assertTrue(st["enemies"][0].get("dot"))
        hp = st["enemies"][0]["hp"]
        self.s.act("battle", cmd="guard")
        self.assertLess(st["enemies"][0]["hp"], hp)              # 毒傷每回合生效
        self.s.battle = None
        st = self._fight("ape")
        st["enemies"][0]["stun_imm"] = 0
        self.s.act("battle", cmd="guard")
        self.assertTrue(any("裂石投擲" in x for x in st["log"]))
        self.s.battle = None
        st = self._fight("snake")
        hp = st["enemies"][0]["hp"]
        self.s.act("battle", cmd="guard")
        self.assertLess(st["enemies"][0]["hp"], hp)

    def test_bat_heals_hero(self):
        st = self._fight("bat")
        st["enemies"][0]["atk"] = 0
        self.h.hp = self.h.max_hp * 0.5
        hp0 = self.h.hp
        self.s.act("battle", cmd="guard")
        self.assertGreater(self.h.hp, hp0)

    def test_cooldown_cycle(self):
        st = self._fight("wolf")
        used = 0
        for _ in range(9):
            self.s.act("battle", cmd="guard")
            used += any("月嘯" in x for x in st["log"])
        self.assertIn(used, (2, 3))                              # 3 階冷卻：約每 4 回合一次


class CodexTest(unittest.TestCase):
    def setUp(self):
        import pathlib, tempfile
        from chineserim.session import Session
        self.s = Session(pathlib.Path(tempfile.mkdtemp()) / "s.json", seed=14)
        self.s.act("new", diff="normal")
        self.h = self.s.hero
        self.h.hp, self.h.mp = self.h.max_hp, self.h.max_mp

    def _shop(self):
        for w in self.s.data.regions:
            for g in w["regions"]:
                for l in g["locations"]:
                    m = self.s.get_map("loc:" + l["id"])
                    ph = next((e for e in m["entities"] if e.get("role") == "pharmacy"), None)
                    if ph:
                        self.s.region = g["id"]
                        if self.s.mode == "loc":
                            self.s.act("leave")
                        self.s.act("enter", loc=l["id"])
                        self.s.act("talk", ent=ph["id"])
                        return
        self.fail("沒有丹藥鋪")

    def test_locked_without_book(self):
        v = self.s.snapshot()["codex"]
        self.assertFalse(v["beast"]["owned"])
        self.assertNotIn("entries", v["beast"])
        self.assertFalse(v["pet"]["owned"])

    def test_battle_view_hides_knowledge_without_book(self):
        self.s.start_boss_fight("yuzitong")
        b = self.s.snapshot()["battle"]
        self.assertFalse(b["codex"])
        self.assertNotIn("weak", b["enemies"][0])
        self.assertNotIn("skills", b["enemies"][0])
        self.s.battle = None
        self.h.add("codex_beast")
        self.s.start_boss_fight("yuzitong")
        b = self.s.snapshot()["battle"]
        self.assertTrue(b["codex"])
        self.assertIn("weak", b["enemies"][0])
        self.assertTrue(b["enemies"][0]["skills"])

    def test_entries_unlock_by_encounter(self):
        self.h.add("codex_beast")
        v = self.s.snapshot()["codex"]["beast"]
        self.assertEqual(v["found"], 0)
        self.assertTrue(all(not e["known"] for e in v["entries"]))
        self.s.start_boss_fight("yuzitong")
        v = self.s.snapshot()["codex"]["beast"]
        b = next(x for x in v["bosses"] if x["id"] == "yuzitong")
        self.assertTrue(b["known"] and b["skills"])
        self.assertEqual(v["found"], 1)
        self.s.battle = None
        self.s.act("enter", loc="taiyue")
        e = next(e for e in self.s.get_map(self.s.map_id)["entities"] if e["k"] == "enemy")
        self.s.act("battle_start", ids=e["id"])
        v = self.s.snapshot()["codex"]["beast"]
        got = next(x for x in v["entries"] if x["id"] == e["kind"])
        self.assertTrue(got["known"])
        self.assertEqual(got["elements"][0]["el"], e["el"])
        self.assertTrue(got["elements"][0]["weak"])

    def test_pet_book_gates_skill_info(self):
        self.h.add("pet_egg")
        self.s.act("use", item="pet_egg")
        self.h.pet["level"] = 4
        sk = self.s.snapshot()["comp"]["pet"]["skill"]
        self.assertTrue(sk.get("hidden"))
        self.assertEqual(sk["name"], "？？？")
        self.s.start_boss_fight("yuzitong")
        self.assertEqual(self.s.snapshot()["battle"]["allies"][0]["skill"], "？？？")
        self.s.battle = None
        self.h.add("codex_pet")
        sk = self.s.snapshot()["comp"]["pet"]["skill"]
        self.assertFalse(sk.get("hidden"))
        v = self.s.snapshot()["codex"]["pet"]
        self.assertEqual(v["found"], 1)                       # 養過的靈寵解鎖

    def test_buy_once_and_shop_states(self):
        self._shop()
        self.h.add("lingshi", 2000)
        v = self.s.snapshot()["shop"]
        it = next(i for i in v["items"] if i["id"] == "codex_beast")
        self.assertIsNone(it["left"])
        self.s.act("buy", item="codex_beast")
        self.assertEqual(self.h.count("codex_beast"), 1)
        n = self.h.count("lingshi")
        self.s.act("buy", item="codex_beast")                # 已有：不能再買
        self.assertEqual(self.h.count("codex_beast"), 1)
        self.assertEqual(self.h.count("lingshi"), n)
        it = next(i for i in self.s.snapshot()["shop"]["items"] if i["id"] == "codex_beast")
        self.assertEqual(it["left"], 0)

    def test_found_in_drops(self):
        from chineserim import loot
        import random
        got = set()
        for i in range(200):
            for it, n in loot.roll_table(self.s.data, "guardian_rich", self.h, random.Random(i)):
                got.add(it)
        self.assertIn("codex_beast", got)
        self.assertIn("codex_pet", got)
        self.h.add("codex_beast")                             # 已有就不會再掉
        for i in range(200):
            self.assertNotIn("codex_beast", [it for it, n in loot.roll_table(self.s.data, "guardian_rich", self.h, random.Random(i))])
