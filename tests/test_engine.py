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
