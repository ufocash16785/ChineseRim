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
        s.act("visit", loc="qingniu")
        self.assertEqual(s.hero.quest["o"], 1)
        s.act("visit", loc="caixia")            # 門派：+2 等級
        s.act("visit", loc="caixia")
        self.assertGreaterEqual(s.hero.quest["q"], 1)        # 第一個任務已完成
        self.assertIn("lingshi", s.hero.inventory)
        v = s.snapshot()["quest"]
        self.assertEqual(v["quests"][0]["state"], "done")
        # 存檔後任務進度保留
        s2 = self.Session(self.path)
        s2.load()
        self.assertEqual(s2.hero.quest, s.hero.quest)

    def test_full_arc_reachable(self):
        s = self.s
        h = s.hero
        for _ in range(400):
            if h.quest["done"]:
                break
            for loc in ("qingniu", "caixia", "taiyue", "yuejing"):
                s.act("visit", loc=loc)
            if s.rs.at_bottleneck(h):
                h.add("pill")
                s.act("break")
            h.hp = h.max_hp
            h.add("lingshi", 10)
            s.day += 30
            s.act("rest")
        self.assertTrue(h.quest["done"])
