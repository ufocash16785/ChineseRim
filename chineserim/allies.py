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

    def _pet_at(self, i):
        h = self.hero
        i = int(i) if i not in (None, "") else -1
        if i < 0:
            return h.pet or None
        return h.pet_bench[i] if i < len(h.pet_bench) else None

    def _puppet_at(self, i):
        h = self.hero
        i = int(i) if i not in (None, "") else -1
        if i < 0:
            return h.puppet or None
        return h.puppet_bench[i] if i < len(h.puppet_bench) else None

    def pet_gain_exp(self, n, log=None, pet=None):
        pet = pet or self.hero.pet
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
        if h.pet and len(h.pet_bench) >= self.data.pets["pet_bench_cap"]:
            self.log.append("你的靈寵欄已滿（出戰 1＋留守 %d）。請先放生一隻再孵化。" % self.data.pets["pet_bench_cap"])
            return False
        h.remove(self.data.pets["egg"])
        kind = self.rng.choice(list(self.data.pets["pets"]))
        pet = {"kind": kind, "el": self.rng.choice("金木水火土"), "level": 1, "exp": 0}
        self.codex_see_pet(kind)
        if not h.pet:
            h.pet = pet
        else:
            h.pet_bench.append(pet)
        self.log.append(f"蛋殼裂開，一隻{pet['el']}屬性的「{self.pet_name(pet)}」鑽了出來，親暱地蹭著你！" + ("" if pet is h.pet else "（先留守，可在夥伴面板換上出戰）"))
        return True

    def _td_pet_feed(self, i=-1, **_):
        h = self.hero
        pet = self._pet_at(i)
        if not pet:
            return
        if pet["level"] >= self.data.pets["max_level"]:
            self.log.append("牠已經長到最強了。")
            return
        if not h.remove("herb"):
            self.log.append("沒有靈草可以餵。")
            return
        self.log.append(f"{self.pet_name(pet)}開心地吃掉了靈草。")
        self.pet_gain_exp(self.data.pets["feed_exp"], pet=pet)

    def _td_pet_release(self, i=-1, **_):
        h = self.hero
        pet = self._pet_at(i)
        if not pet:
            return
        self.log.append(f"你把{self.pet_name(pet)}放歸山林，牠回頭望了你好幾眼。")
        if pet is h.pet:
            h.pet = {}
        else:
            h.pet_bench.remove(pet)

    def _td_pet_equip(self, i=0, **_):
        """把留守的靈寵換上出戰位（原本出戰的回到留守）。"""
        h = self.hero
        i = int(i)
        if not 0 <= i < len(h.pet_bench):
            return
        new = h.pet_bench.pop(i)
        if h.pet:
            h.pet_bench.insert(i, h.pet)
        h.pet = new
        self.log.append(f"{self.pet_name(new)}上前一步：這次由牠出戰！")

    def _td_pet_stow(self, **_):
        h = self.hero
        if not h.pet:
            return
        if len(h.pet_bench) >= self.data.pets["pet_bench_cap"]:
            self.log.append("留守欄已滿。")
            return
        self.log.append(f"{self.pet_name(h.pet)}退回留守，這次不出戰。")
        h.pet_bench.append(h.pet)
        h.pet = {}

    def _td_stance(self, mode="balanced", **_):
        if mode in self.data.pets["stances"]:
            self.hero.flags["stance"] = mode
            self.log.append(f"出戰戰術：{self.data.pets['stances'][mode]['name']}（{self.data.pets['stances'][mode]['desc']}）")

    def stance(self):
        s = self.hero.flags.get("stance")
        return s if s in self.data.pets["stances"] else "balanced"

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

    def _td_puppet_equip(self, i=0, **_):
        h = self.hero
        i = int(i)
        if not 0 <= i < len(h.puppet_bench):
            return
        new = h.puppet_bench.pop(i)
        if h.puppet:
            h.puppet_bench.insert(i, h.puppet)
        h.puppet = new
        self.log.append(f"{self.data.pets['puppets'][new['kind']]['name']}啟動了，這次由它出戰。")

    def _td_puppet_stow(self, **_):
        h = self.hero
        if not h.puppet:
            return
        if len(h.puppet_bench) >= self.data.pets["puppet_bench_cap"]:
            self.log.append("傀儡庫已滿。")
            return
        self.log.append(f"{self.data.pets['puppets'][h.puppet['kind']]['name']}收入傀儡庫，這次不出戰。")
        h.puppet_bench.append(h.puppet)
        h.puppet = {}

    def _td_puppet_scrap(self, i=-1, **_):
        h = self.hero
        p = self._puppet_at(i)
        if not p:
            return
        back = round(self.data.pets["puppets"][p["kind"]]["cost"] * 0.3 * self.dcfg["price"])
        h.add("lingshi", back)
        self.log.append(f"你拆解了{self.data.pets['puppets'][p['kind']]['name']}，回收靈石 {back}。")
        if p is h.puppet:
            h.puppet = {}
        else:
            h.puppet_bench.remove(p)

    def puppet_slots(self, p):
        return self.data.pets["puppet_slots"][p["level"] - 1]

    def _td_puppet_mod(self, mod="", slot=None, i=-1, **_):
        h, c = self.hero, self.data.pets
        p = self._puppet_at(i)
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

    def _td_puppet_unmod(self, slot=0, i=-1, **_):
        p = self._puppet_at(i)
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
        if h.puppet and len(h.puppet_bench) >= c["puppet_bench_cap"]:
            self.log.append("傀儡庫已滿，請先拆解一具。")
            return
        if not h.remove("lingshi", cost):
            self.log.append(f"煉製{spec['name']}需要靈石 {cost}。")
            return
        pup = {"kind": ptype, "level": 1, "hp": 0}
        pup["hp"] = self.puppet_maxhp(pup)
        if not h.puppet:
            h.puppet = pup
        else:
            h.puppet_bench.append(pup)
        self.log.append(f"你煉成了一具{spec['name']}，它僵硬地朝你點了點頭。" + ("" if pup is h.puppet else "（先留守，可在夥伴面板換上出戰）"))

    def _td_puppet_upgrade(self, i=-1, **_):
        h, c = self.hero, self.data.pets
        p = self._puppet_at(i)
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

    def _td_puppet_repair(self, i=-1, **_):
        h, c = self.hero, self.data.pets
        p = self._puppet_at(i)
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
        stn = c["stances"][self.stance()]
        out = []
        if h.pet:
            stage = self.pet_stage(h.pet)
            sk = self.pet_skill(h.pet)
            out.append({"type": "pet", "name": self.pet_name(h.pet), "kind": h.pet["kind"], "el": h.pet["el"], "level": h.pet["level"],
                        "atk": (c["atk_base"] + c["atk_per_level"] * h.pet["level"]) * stn["atk"], "hp": 1, "maxhp": 1, "absorb": 0,
                        "skill": sk, "cd": 0, "cd_max": c["skill_cd"][min(1, max(0, stage - 1))] if sk else 0})
        if h.puppet:
            sp = c["puppets"][h.puppet["kind"]]
            stt = self.puppet_stats(h.puppet)
            sk = self.puppet_skill(h.puppet)
            out.append({"type": "puppet", "name": sp["name"], "sprite": sp["sprite"], "level": h.puppet["level"], "atk": stt["atk"] * stn["atk"],
                        "absorb": min(0.95, stt["absorb"] * stn["absorb"]), "hp": h.puppet["hp"], "maxhp": stt["maxhp"], "absorb_frac": stt["absorb_frac"] * stn["frac"],
                        "mods": list(h.puppet.get("mods", [])), "skill": sk, "cd": 0, "cd_max": c["puppet_skill_cd"][sk["tier"]] if sk else 0, "boom_used": False})
        return out

    def sync_allies(self, st, won):
        h = self.hero
        for a in st.get("allies", []):
            if a["type"] == "puppet" and h.puppet:
                h.puppet["hp"] = max(0, round(a["hp"]))
        if won:
            if h.pet:
                self.pet_gain_exp(1)
            if h.pet_bench:                                    # 留守的靈寵也會慢慢成長
                h.counters["bench_wins"] = h.counters.get("bench_wins", 0) + 1
                if h.counters["bench_wins"] % self.data.pets["bench_exp_every"] == 0:
                    for pet in h.pet_bench:
                        self.pet_gain_exp(1, pet=pet)

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

    def _puppet_view(self, p):
        c = self.data.pets
        h = self.hero
        sp = c["puppets"][p["kind"]]
        mh = self.puppet_maxhp(p)
        stt = self.puppet_stats(p)
        sk = self.puppet_skill(p)
        base_sk = c["puppet_skills"].get(p["kind"])
        mods = p.get("mods", [])
        return {"name": sp["name"], "kind": p["kind"], "level": p["level"], "hp": p["hp"], "maxhp": mh, "sprite": sp["sprite"], "atk": round(stt["atk"], 2), "absorb": sp["absorb"],
                "skill": {"name": base_sk["name"], "desc": self._puppet_skill_desc(base_sk, sk), "unlocked": bool(sk), "unlock_level": c["puppet_skill_unlock"],
                          "cd": c["puppet_skill_cd"][sk["tier"]] if sk else c["puppet_skill_cd"][0]} if base_sk else None,
                "slots": self.puppet_slots(p), "mods": [{"id": m, "name": c["puppet_mods"][m]["name"], "desc": c["puppet_mods"][m]["desc"]} for m in mods],
                "mod_shop": {k: {"name": v["name"], "desc": v["desc"], "cost": round(v["cost"] * self.dcfg["price"]), "level": v["level"], "ok": p["level"] >= v["level"], "installed": k in mods} for k, v in c["puppet_mods"].items()},
                "broken": p["hp"] <= 0, "upgrade": None if p["level"] >= c["puppet_max_level"] else round(c["upgrade_cost"][p["level"] - 1] * self.dcfg["price"]),
                "repair": round(c["repair_per_level"] * p["level"] * self.dcfg["price"]) if p["hp"] < mh else 0}

    def _pet_view(self, pet):
        c = self.data.pets
        return {"name": self.pet_name(pet), "kind": pet["kind"], "el": pet["el"], "level": pet["level"], "exp": pet["exp"], "need": self.pet_need(pet),
                "max": c["max_level"], "stage": self.pet_stage(pet), "eggs": self.hero.count(c["egg"]), "skill": self._skill_view(pet)}

    def allies_view(self):
        h, c = self.hero, self.data.pets
        pet = self._pet_view(h.pet) if h.pet else None
        pup = self._puppet_view(h.puppet) if h.puppet else None
        return {"pet": pet, "puppet": pup, "eggs": h.count(c["egg"]), "herbs": h.count("herb"),
                "pet_bench": [dict(self._pet_view(x), i=i) for i, x in enumerate(h.pet_bench)], "puppet_bench": [dict(self._puppet_view(x), i=i) for i, x in enumerate(h.puppet_bench)],
                "pet_cap": c["pet_bench_cap"], "puppet_cap": c["puppet_bench_cap"], "stance": self.stance(),
                "stances": {k: {"name": v["name"], "desc": v["desc"]} for k, v in c["stances"].items()},
                "build": {k: {"name": v["name"], "cost": round(v["cost"] * self.dcfg["price"]), "ok": h.realm >= v["realm"], "desc": v["desc"], "realm": v["realm"]} for k, v in c["puppets"].items()}}
