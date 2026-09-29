"""文字介面：python -m chineserim"""
import random
import sys

from . import combat, treasures
from .character import Character
from .data import GameData
from .realms import RealmSystem


def main(argv=None):
    data = GameData()
    rs = RealmSystem(data, random.Random())
    rs.on("CR_OnRealmChanged", lambda actor, order, sub, old: print(f"  ★ 境界變更 → {data.realms[order]['name']}"))
    hero = Character("韓立", elements=["金", "木", "水", "火"], root_type="quad")
    rs.set_realm(hero, "mortal")
    hero.add("lingshi", 500)
    day = 0
    print("《凡人修仙傳》獨立版（無需 Skyrim）。指令：status / train / break / pill / refine / wait / quit")
    while True:
        try:
            cmd = input("> ").strip()
        except EOFError:
            break
        r = rs.realm(hero)
        if cmd == "status":
            print(f"{hero.name} {r['name']}{r['sub'][hero.sub]} Lv{hero.level}/{r['levelRange'][1]} HP{hero.hp:.0f} MP{hero.mp:.0f} 靈石{hero.count('lingshi')}")
        elif cmd == "train":
            rs.gain_level(hero, 5)
            rs.advance_sub(hero)
            print("修煉完成" + ("（已達瓶頸，需突破）" if rs.at_bottleneck(hero) else ""))
        elif cmd in ("break", "pill"):
            if cmd == "pill":
                hero.add("pill")
            print("突破成功" if rs.attempt_breakthrough(hero, "pill" if cmd == "pill" else None) else "突破失敗或未達瓶頸")
        elif cmd == "refine":
            print("祭煉成功" if treasures.refine(rs, hero, "qingzhu_fengyunjian") else "條件不足")
        elif cmd == "wait":
            day += 30
            last = treasures.tick_zhangtianping(rs, hero, day, 22)
            print(f"第 {day} 日，靈液 {hero.count('lingye')}")
        elif cmd == "quit":
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
