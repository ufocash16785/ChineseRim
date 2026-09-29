"""境界與突破（原 CR_RealmSystem / CR_Breakthrough）。等級取代 Skyrim PlayerLevel：純數值。"""
import random

BASE_CHANCE = 0.35
PILL_BONUS = 0.45
SUB_BONUS = 0.05


class RealmSystem:
    def __init__(self, data, rng=None, listeners=None):
        self.data = data
        self.rng = rng or random.Random()
        self.listeners = listeners if listeners is not None else {}   # 事件名 -> [callable]

    def emit(self, event, **kw):
        for f in self.listeners.get(event, []):
            f(**kw)

    def on(self, event, fn):
        self.listeners.setdefault(event, []).append(fn)

    def realm(self, ch):
        return self.data.realms[ch.realm]

    def apply_stats(self, ch):
        st = self.realm(ch).get("stats")
        if st:
            bonus = 1 + sum(self.data.gongfa.get(g, {}).get("combat", {}).get("maxHp", 0) for g in ch.gongfa)
            ch.max_hp = ch.hp = st["hp"] * bonus
            ch.mp, ch.stamina = st["mp"], st["stamina"]

    def set_realm(self, ch, realm_id, sub=0):
        old = ch.realm
        ch.realm, ch.sub = self.data.realm_index(realm_id), sub
        self.apply_stats(ch)
        self.emit("CR_OnRealmChanged", actor=ch, order=ch.realm, sub=sub, old=old)

    def advance_sub(self, ch):
        if ch.sub < len(self.realm(ch)["sub"]) - 1:
            ch.sub += 1

    def at_bottleneck(self, ch):
        return ch.level >= self.realm(ch)["levelRange"][1]

    def gain_level(self, ch, n=1):
        """升級受境界上限鎖住：達上限後必須突破（原 Lock/Unlock）。"""
        cap = self.realm(ch)["levelRange"][1]
        ch.level = min(cap, ch.level + max(1, round(n * ch.speed)))
        return ch.level

    def _required_pill(self, ch):
        return self.data.realms[ch.realm + 1].get("pill") if ch.realm + 1 < len(self.data.realms) else None

    def attempt_breakthrough(self, ch, pill=None):
        r = self.realm(ch)
        bt = r["breakthrough"]["type"]
        if bt in ("insight", "ascension") or ch.realm + 1 >= len(self.data.realms):
            return False            # 由劇情/試煉直接 set_realm
        if not self.at_bottleneck(ch):
            return False
        if bt == "pill" and pill is None:
            return False
        chance = BASE_CHANCE + ch.sub * SUB_BONUS
        if pill and ch.remove(pill):
            chance += PILL_BONUS
        ok = self.rng.random() < min(chance, 1.0)
        self.emit("CR_OnBreakthrough", actor=ch, success=ok, realm=r["id"])
        if ok:
            self.set_realm(ch, self.data.realms[ch.realm + 1]["id"])
            ch.level = self.realm(ch)["levelRange"][0]
        else:
            ch.hp = ch.hp * 0.5     # 反噬
        return ok
