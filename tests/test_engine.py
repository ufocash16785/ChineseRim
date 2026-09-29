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
