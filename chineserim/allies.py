"""靈寵與傀儡：戰鬥時自動出手／擋招，平時可成長。以 Mixin 併入 Session。"""
from .character import item_name


class AlliesMixin:
    # ---- 靈寵 ----
    def pet_stage(self, pet):
        cfg = self.data.pets
        return sum(1 for lv in cfg["stage_levels"] if pet["level"] >= lv)

    def pet_name(self, pet):
        return self.data.pets["pets"][pet["kind"]][self.pet_stage(pet)]

    def pet_need(self, pet):
        c = self.data.pets
        return c["exp_base"] + c["exp_per_level"] * pet["level"]

    def pet_gain_exp(self, n, log=None):
        pet = self.hero.pet
        if not pet:
            return
        c = self.data.pets
        pet["exp"] += n
        while pet["level"] < c["max_level"] and pet["exp"] >= self.pet_need(pet):
            pet["exp"] -= self.pet_need(pet)
            pet["level"] += 1
            (log if log is not None else self.log).append(f"靈寵成長了！{self.pet_name(pet)} 升到 {pet['level']} 級" + ("，並進化了！" if pet["level"] in c["stage_levels"] else "。"))
        if pet["level"] >= c["max_level"]:
            pet["exp"] = 0

    def hatch_egg(self):
        h = self.hero
        if h.pet:
            self.log.append("你已經有一隻靈寵了。（可在夥伴面板放生後再孵化）")
            return False
        h.remove(self.data.pets["egg"])
        kind = self.rng.choice(list(self.data.pets["pets"]))
        h.pet = {"kind": kind, "el": self.rng.choice("金木水火土"), "level": 1, "exp": 0}
        self.log.append(f"蛋殼裂開，一隻{h.pet['el']}屬性的「{self.pet_name(h.pet)}」鑽了出來，親暱地蹭著你！")
        return True

    def _td_pet_feed(self, **_):
        h = self.hero
        if not h.pet:
            return
        if h.pet["level"] >= self.data.pets["max_level"]:
            self.log.append("牠已經長到最強了。")
            return
        if not h.remove("herb"):
            self.log.append("沒有靈草可以餵。")
            return
        self.log.append(f"{self.pet_name(h.pet)}開心地吃掉了靈草。")
        self.pet_gain_exp(self.data.pets["feed_exp"])

    def _td_pet_release(self, **_):
        if self.hero.pet:
            self.log.append(f"你把{self.pet_name(self.hero.pet)}放歸山林，牠回頭望了你好幾眼。")
            self.hero.pet = {}

    def pet_daily(self, days):
        h = self.hero
        if not h.pet:
            return
        c = self.data.pets
        for _ in range(days):
            if self.rng.random() < c["fetch_chance"] * (0.5 + h.pet["level"] / c["max_level"]):
                h.add("herb")
                self.log.append(f"{self.pet_name(h.pet)}叼回了一株靈草。")

    # ---- 傀儡 ----
    def puppet_maxhp(self, p):
        c = self.data.pets
        return round(self.hero.max_hp * c["puppet_hp_frac"] * (1 + c["puppet_hp_per_level"] * (p["level"] - 1)))

    def _td_puppet_build(self, ptype="wood", **_):
        h, c = self.hero, self.data.pets
        spec = c["puppets"].get(ptype)
        if not spec or h.realm < spec["realm"]:
            self.log.append("你的境界還煉不出這種傀儡。" if spec else "")
            return
        cost = round(spec["cost"] * self.dcfg["price"])
        if not h.remove("lingshi", cost):
            self.log.append(f"煉製{spec['name']}需要靈石 {cost}。")
            return
        h.puppet = {"kind": ptype, "level": 1, "hp": 0}
        h.puppet["hp"] = self.puppet_maxhp(h.puppet)
        self.log.append(f"你煉成了一具{spec['name']}，它僵硬地朝你點了點頭。")

    def _td_puppet_upgrade(self, **_):
        h, c = self.hero, self.data.pets
        p = h.puppet
        if not p:
            return
        if p["level"] >= c["puppet_max_level"]:
            self.log.append("傀儡已升到最高階。")
            return
        cost = round(c["upgrade_cost"][p["level"] - 1] * self.dcfg["price"])
        if not h.remove("lingshi", cost):
            self.log.append(f"升級傀儡需要靈石 {cost}。")
            return
        p["level"] += 1
        p["hp"] = self.puppet_maxhp(p)
        self.log.append(f"{c['puppets'][p['kind']]['name']}升到了 {p['level']} 階，身軀更加堅固。")

    def _td_puppet_repair(self, **_):
        h, c = self.hero, self.data.pets
        p = h.puppet
        if not p or p["hp"] >= self.puppet_maxhp(p):
            return
        cost = round(c["repair_per_level"] * p["level"] * self.dcfg["price"])
        if not h.remove("lingshi", cost):
            self.log.append(f"修理傀儡需要靈石 {cost}。")
            return
        p["hp"] = self.puppet_maxhp(p)
        self.log.append("你替傀儡換上新的零件，它又煥然一新了。")

    # ---- 戰鬥 ----
    def allies_spec(self):
        h, c = self.hero, self.data.pets
        out = []
        if h.pet:
            out.append({"type": "pet", "name": self.pet_name(h.pet), "kind": h.pet["kind"], "el": h.pet["el"], "level": h.pet["level"],
                        "atk": c["atk_base"] + c["atk_per_level"] * h.pet["level"], "hp": 1, "maxhp": 1, "absorb": 0})
        if h.puppet:
            sp = c["puppets"][h.puppet["kind"]]
            out.append({"type": "puppet", "name": sp["name"], "sprite": sp["sprite"], "level": h.puppet["level"], "atk": sp["atk"] * (1 + 0.12 * (h.puppet["level"] - 1)),
                        "absorb": sp["absorb"], "hp": h.puppet["hp"], "maxhp": self.puppet_maxhp(h.puppet), "absorb_frac": c["absorb_damage_frac"]})
        return out

    def sync_allies(self, st, won):
        h = self.hero
        for a in st.get("allies", []):
            if a["type"] == "puppet" and h.puppet:
                h.puppet["hp"] = max(0, round(a["hp"]))
        if won and h.pet:
            self.pet_gain_exp(1)

    def allies_view(self):
        h, c = self.hero, self.data.pets
        pet = None
        if h.pet:
            pet = {"name": self.pet_name(h.pet), "kind": h.pet["kind"], "el": h.pet["el"], "level": h.pet["level"], "exp": h.pet["exp"], "need": self.pet_need(h.pet),
                   "max": c["max_level"], "stage": self.pet_stage(h.pet), "eggs": h.count(c["egg"])}
        pup = None
        if h.puppet:
            sp = c["puppets"][h.puppet["kind"]]
            mh = self.puppet_maxhp(h.puppet)
            pup = {"name": sp["name"], "level": h.puppet["level"], "hp": h.puppet["hp"], "maxhp": mh, "sprite": sp["sprite"], "atk": sp["atk"], "absorb": sp["absorb"],
                   "broken": h.puppet["hp"] <= 0, "upgrade": None if h.puppet["level"] >= c["puppet_max_level"] else round(c["upgrade_cost"][h.puppet["level"] - 1] * self.dcfg["price"]),
                   "repair": round(c["repair_per_level"] * h.puppet["level"] * self.dcfg["price"]) if h.puppet["hp"] < mh else 0}
        return {"pet": pet, "puppet": pup, "eggs": h.count(c["egg"]), "herbs": h.count("herb"),
                "build": {k: {"name": v["name"], "cost": round(v["cost"] * self.dcfg["price"]), "ok": h.realm >= v["realm"], "desc": v["desc"], "realm": v["realm"]} for k, v in c["puppets"].items()}}
