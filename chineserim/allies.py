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

    def pet_skill(self, pet):
        """專屬技能（1 階＝進化後習得；2 階＝完全體強化）。回傳 {id,name,type,val,...} 或 None。"""
        c = self.data.pets
        stage = self.pet_stage(pet)
        if stage < c["skill_unlock_stage"]:
            return None
        sk = dict(c["skills"][pet["kind"]])
        sk["id"] = pet["kind"]
        sk["val"] = sk["val"][min(1, stage - 1)]
        sk["stage"] = stage
        return sk

    def hatch_egg(self):
        h = self.hero
        if h.pet:
            self.log.append("你已經有一隻靈寵了。（可在夥伴面板放生後再孵化）")
            return False
        h.remove(self.data.pets["egg"])
        kind = self.rng.choice(list(self.data.pets["pets"]))
        h.pet = {"kind": kind, "el": self.rng.choice("金木水火土"), "level": 1, "exp": 0}
        self.codex_see_pet(kind)
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
        base = self.hero.max_hp * c["puppet_hp_frac"] * (1 + c["puppet_hp_per_level"] * (p["level"] - 1))
        return round(base * (1.3 if "armor" in p.get("mods", []) else 1.0))

    def puppet_stats(self, p):
        c = self.data.pets
        sp = c["puppets"][p["kind"]]
        mods = p.get("mods", [])
        return {"atk": sp["atk"] * (1 + 0.12 * (p["level"] - 1)) * (1.4 if "cannon" in mods else 1.0), "absorb": sp["absorb"],
                "absorb_frac": c["absorb_damage_frac"] * (0.75 if "armor" in mods else 1.0), "maxhp": self.puppet_maxhp(p)}

    def puppet_skill(self, p):
        c = self.data.pets
        if p["level"] < c["puppet_skill_unlock"]:
            return None
        base = c["puppet_skills"].get(p["kind"])
        if not base:
            return None
        tier = 1 if p["level"] >= c["puppet_max_level"] else 0
        sk = {k: (v[tier] if isinstance(v, list) else v) for k, v in base.items()}
        sk["tier"] = tier
        return sk

    def puppet_slots(self, p):
        return self.data.pets["puppet_slots"][p["level"] - 1]

    def _td_puppet_mod(self, mod="", slot=None, **_):
        h, c = self.hero, self.data.pets
        p = h.puppet
        m = c["puppet_mods"].get(mod)
        if not p or not m:
            return
        mods = p.setdefault("mods", [])
        if mod in mods:
            self.log.append("這個改造已經裝上了。")
            return
        if p["level"] < m["level"]:
            self.log.append(f"傀儡需要升到 {m['level']} 階才能裝「{m['name']}」。")
            return
        slots = self.puppet_slots(p)
        idx = int(slot) if slot not in (None, "") else (len(mods) if len(mods) < slots else None)
        if idx is None or not 0 <= idx < slots:
            self.log.append("改造槽已滿，請指定要替換的槽位。")
            return
        cost = round(m["cost"] * self.dcfg["price"])
        if not h.remove("lingshi", cost):
            self.log.append(f"改造需要靈石 {cost}。")
            return
        old_max = self.puppet_maxhp(p)
        if idx < len(mods):
            mods[idx] = mod
        else:
            mods.append(mod)
        p["hp"] = min(self.puppet_maxhp(p), p["hp"] + max(0, self.puppet_maxhp(p) - old_max))
        self.log.append(f"你替傀儡裝上了「{m['name']}」。")

    def _td_puppet_unmod(self, slot=0, **_):
        p = self.hero.puppet
        if not p:
            return
        mods = p.setdefault("mods", [])
        i = int(slot)
        if 0 <= i < len(mods):
            self.log.append(f"你拆下了「{self.data.pets['puppet_mods'][mods[i]]['name']}」。")
            mods.pop(i)
            p["hp"] = min(p["hp"], self.puppet_maxhp(p))

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
            stage = self.pet_stage(h.pet)
            sk = self.pet_skill(h.pet)
            out.append({"type": "pet", "name": self.pet_name(h.pet), "kind": h.pet["kind"], "el": h.pet["el"], "level": h.pet["level"],
                        "atk": c["atk_base"] + c["atk_per_level"] * h.pet["level"], "hp": 1, "maxhp": 1, "absorb": 0,
                        "skill": sk, "cd": 0, "cd_max": c["skill_cd"][min(1, max(0, stage - 1))] if sk else 0})
        if h.puppet:
            sp = c["puppets"][h.puppet["kind"]]
            stt = self.puppet_stats(h.puppet)
            sk = self.puppet_skill(h.puppet)
            out.append({"type": "puppet", "name": sp["name"], "sprite": sp["sprite"], "level": h.puppet["level"], "atk": stt["atk"],
                        "absorb": stt["absorb"], "hp": h.puppet["hp"], "maxhp": stt["maxhp"], "absorb_frac": stt["absorb_frac"],
                        "mods": list(h.puppet.get("mods", [])), "skill": sk, "cd": 0, "cd_max": c["puppet_skill_cd"][sk["tier"]] if sk else 0, "boom_used": False})
        return out

    def sync_allies(self, st, won):
        h = self.hero
        for a in st.get("allies", []):
            if a["type"] == "puppet" and h.puppet:
                h.puppet["hp"] = max(0, round(a["hp"]))
        if won and h.pet:
            self.pet_gain_exp(1)

    def _puppet_skill_desc(self, base, sk):
        v = sk or {k: (x[0] if isinstance(x, list) else x) for k, x in base.items()}
        return base["desc"].format(hits=v.get("hits", ""), turns=v.get("turns", ""))

    def has_pet_book(self):
        return self.hero.count(self.data.codex["pet_book"]) > 0

    def _skill_view(self, pet):
        c = self.data.pets
        base = c["skills"][pet["kind"]]
        sk = self.pet_skill(pet)
        if not self.has_pet_book():
            return {"name": "？？？", "desc": "需要《靈寵圖鑑》才能得知牠的技能。", "unlocked": bool(sk), "unlock_level": c["stage_levels"][c["skill_unlock_stage"] - 1], "upgraded": False, "cd": 0, "hidden": True}
        v = sk["val"] if sk else base["val"][0]
        pct = round(v * 100) if base["type"] in ("howl", "shield", "drain", "web") else 0
        return {"name": base["name"], "desc": base["desc"].format(pct=pct), "unlocked": bool(sk), "unlock_level": c["stage_levels"][c["skill_unlock_stage"] - 1],
                "upgraded": bool(sk and sk["stage"] >= 2), "cd": c["skill_cd"][min(1, max(0, self.pet_stage(pet) - 1))] if sk else c["skill_cd"][0]}

    def allies_view(self):
        h, c = self.hero, self.data.pets
        pet = None
        if h.pet:
            pet = {"name": self.pet_name(h.pet), "kind": h.pet["kind"], "el": h.pet["el"], "level": h.pet["level"], "exp": h.pet["exp"], "need": self.pet_need(h.pet),
                   "max": c["max_level"], "stage": self.pet_stage(h.pet), "eggs": h.count(c["egg"]), "skill": self._skill_view(h.pet)}
        pup = None
        if h.puppet:
            sp = c["puppets"][h.puppet["kind"]]
            mh = self.puppet_maxhp(h.puppet)
            stt = self.puppet_stats(h.puppet)
            sk = self.puppet_skill(h.puppet)
            base_sk = c["puppet_skills"].get(h.puppet["kind"])
            mods = h.puppet.get("mods", [])
            pup = {"name": sp["name"], "level": h.puppet["level"], "hp": h.puppet["hp"], "maxhp": mh, "sprite": sp["sprite"], "atk": round(stt["atk"], 2), "absorb": sp["absorb"],
                   "skill": {"name": base_sk["name"], "desc": self._puppet_skill_desc(base_sk, sk), "unlocked": bool(sk), "unlock_level": c["puppet_skill_unlock"],
                             "cd": c["puppet_skill_cd"][sk["tier"]] if sk else c["puppet_skill_cd"][0]} if base_sk else None,
                   "slots": self.puppet_slots(h.puppet), "mods": [{"id": m, "name": c["puppet_mods"][m]["name"], "desc": c["puppet_mods"][m]["desc"]} for m in mods],
                   "mod_shop": {k: {"name": v["name"], "desc": v["desc"], "cost": round(v["cost"] * self.dcfg["price"]), "level": v["level"], "ok": h.puppet["level"] >= v["level"], "installed": k in mods} for k, v in c["puppet_mods"].items()},
                   "broken": h.puppet["hp"] <= 0, "upgrade": None if h.puppet["level"] >= c["puppet_max_level"] else round(c["upgrade_cost"][h.puppet["level"] - 1] * self.dcfg["price"]),
                   "repair": round(c["repair_per_level"] * h.puppet["level"] * self.dcfg["price"]) if h.puppet["hp"] < mh else 0}
        return {"pet": pet, "puppet": pup, "eggs": h.count(c["egg"]), "herbs": h.count("herb"),
                "build": {k: {"name": v["name"], "cost": round(v["cost"] * self.dcfg["price"]), "ok": h.realm >= v["realm"], "desc": v["desc"], "realm": v["realm"]} for k, v in c["puppets"].items()}}
