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
        self.assertEqual(len(pts), 18)


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
        self.assertEqual(set(s.data.dialogues) - seen, set(), "有對話沒被觸發")


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
        self.assertEqual(seen, 42)

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
        self.assertIn("靈力不足", st["log"][0])
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
        s.hero.hp = 1
        s.act("battle", cmd="guard")
        while s.battle and not s.battle["over"]:
            s.hero.hp = 1
            s.act("battle", cmd="guard")
        if s.battle["over"] == "lose":
            self.assertGreaterEqual(s.hero.hp, s.hero.max_hp / 2)

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
        shop = next(e for e in m["entities"] if e.get("role") == "shop")
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
        self.assertEqual(set(s.data.dialogues) - seen, set())


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
        shop = next(e for e in s.get_map(s.map_id)["entities"] if e.get("role") == "shop")
        s.act("talk", ent=shop["id"])
        self.assertEqual(s.snapshot()["prices"]["heal"], round(30 * 1.25))
        s.act("leave")
        s.act("enter", loc="taiyue")
        e = next(e for e in s.get_map(s.map_id)["entities"] if e["k"] == "enemy")
        s.act("battle_start", ids=e["id"])
        n = s.hero.count("lingshi")
        s.hero.hp = 1
        for _ in range(40):
            if s.battle["over"]:
                break
            s.hero.hp = 1
            s.act("battle", cmd="guard")
        if s.battle["over"] == "lose":
            self.assertEqual(s.hero.count("lingshi"), n - 150 if n >= 150 else 0)

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
