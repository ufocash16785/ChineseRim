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
