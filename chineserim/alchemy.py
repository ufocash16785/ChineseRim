"""煉丹小遊戲（火候）：五個回合調整火候，盡量讓爐溫落在 50 附近。品質決定產量與額外收穫；熟練度會讓火勢更好控制。"""
import math

from .character import item_name

TIER_NAME = {3: "極品", 2: "上品", 1: "普通", 0: "失敗"}


class AlchemyMixin:
    alch = None

    def _alch_cfg(self):
        return self.data.farming["alchemy"]

    def _alch_needs(self, r):
        needs = dict(r["needs"])
        if "lingshi" in needs:
            needs["lingshi"] = round(needs["lingshi"] * self.dcfg["price"])
        return needs

    def _alch_drift(self, heat_lv):
        mastery = min(self._alch_cfg()["mastery_max"], self.hero.counters.get("alch:n", 0) // self._alch_cfg()["mastery_per"])
        rng_max = max(4, heat_lv - mastery)
        return self.rng.randint(-rng_max, rng_max)

    def _td_alch_start(self, recipe="", **_):
        h = self.hero
        r = self.data.farming["recipes"].get(recipe)
        if self.mode != "loc" or not r or self.alch or not any(e["k"] == "furnace" for e in self.get_map(self.map_id)["entities"]):
            return
        needs = self._alch_needs(r)
        lack = [f"{item_name(k)}×{v}" for k, v in needs.items() if h.count(k) < v]
        if lack:
            self.log.append("材料不足：" + "、".join(lack))
            return
        for k, v in needs.items():
            h.remove(k, v)
        self.alch = {"recipe": recipe, "round": 0, "heat": 50, "score": 0, "hist": [], "over": False, "result": None, "needs": needs,
                     "drift": self._alch_drift(r["heat"]), "lv": r["heat"]}
        self.log.append(f"你點燃丹火，開始煉製{r['name']}……（火候要穩，目標是爐溫維持在中間）")

    def _td_alch_act(self, a="hold", **_):
        st = self.alch
        cfg = self._alch_cfg()
        if not st or st["over"] or a not in cfg["actions"]:
            return
        delta = cfg["actions"][a]
        new = st["heat"] + delta + st["drift"]
        score = 0
        for lim, sc in cfg["zones"]:
            if abs(new - 50) <= lim:
                score = sc
                break
        boom = new >= 100 or new <= 0
        st["hist"].append({"from": st["heat"], "act": a, "drift": st["drift"], "heat": max(0, min(100, new)), "score": 0 if boom else score})
        st["heat"] = max(0, min(100, new))
        st["round"] += 1
        if boom:
            st["boom"] = True
            st["score"] = 0
            self._alch_finish()
            return
        st["score"] += score
        if st["round"] >= cfg["rounds"]:
            self._alch_finish()
        else:
            st["drift"] = self._alch_drift(st["lv"])

    def _alch_finish(self):
        st, h = self.alch, self.hero
        cfg = self._alch_cfg()
        r = self.data.farming["recipes"][st["recipe"]]
        tier = next(t for lim, t, _ in cfg["tiers"] if st["score"] >= lim)
        st["over"], st["tier"] = True, tier
        self.advance(1)
        h.counters["alch:n"] = h.counters.get("alch:n", 0) + 1
        if st.get("boom"):
            tier = 0
            st["tier"] = 0
        if tier == 0:
            for k, v in st["needs"].items():
                h.add(k, (v + 1) // 2 if k != "lingye" else v)
            if st.get("boom"):
                h.hp = max(1, h.hp - h.max_hp * 0.1)
                st["result"] = "炸爐！丹爐轟然炸裂，你受了點輕傷，只搶回一半材料。"
            else:
                st["result"] = "火候失控，丹藥成了廢渣……搶回了一半材料。"
        else:
            mult = {1: 1.0, 2: 1.5, 3: 2.0}[tier]
            got = {k: max(v, math.ceil(v * mult)) for k, v in r["gives"].items()}
            for k, v in got.items():
                h.add(k, v)
            txt = "、".join(f"{item_name(k)}×{v}" for k, v in got.items())
            st["result"] = f"{TIER_NAME[tier]}丹成！獲得 {txt}。"
            if tier == 3 and "lingye" in st["needs"] and self.rng.random() < 0.5:
                h.add("lingye")
                st["result"] += " 爐底還凝出一滴靈液！"
        self.log.append(st["result"])

    def _td_alch_close(self, **_):
        if self.alch and self.alch["over"]:
            self.alch = None
            self._after_td()

    def alch_view(self):
        st = self.alch
        if not st:
            return None
        cfg = self._alch_cfg()
        r = self.data.farming["recipes"][st["recipe"]]
        d = abs(st["drift"])
        return {"recipe": st["recipe"], "name": r["name"], "round": st["round"], "rounds": cfg["rounds"], "heat": st["heat"], "score": st["score"],
                "maxScore": cfg["rounds"] * 3, "hist": st["hist"], "over": st["over"], "result": st["result"], "tier": st.get("tier"),
                "trend": None if st["over"] else {"dir": 1 if st["drift"] > 0 else -1 if st["drift"] < 0 else 0, "size": "弱" if d < 5 else "中" if d < 10 else "強"},
                "mastery": self.hero.counters.get("alch:n", 0)}
