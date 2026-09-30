"""社交與經濟：店舖與奸商、布告欄（交易會／宗門招募）、宗門福利、道侶。以 Mixin 併入 Session。"""
import random
from hashlib import md5

from . import items as itemdb
from .character import item_name

WEEK = 7
MAX_SECTS = 3


def _rng(*parts):
    return random.Random(int(md5("|".join(map(str, parts)).encode()).hexdigest()[:12], 16))


class SocialMixin:
    # ================= 宗門福利 =================
    def perk_of(self, sid):
        pk = self.data.sect_perks
        return pk["perks"].get(sid, pk["default"])

    def perk_totals(self):
        out = {"stipend": 0.0, "allDmg": 0.0, "slashDmg": 0.0, "critChance": 0.0, "loot": 0.0, "craft": 0.0, "discount": 0.0, "breakthrough": 0.0, "elemDmg": {}}
        for sid in self.hero.members:
            for k, v in self.perk_of(sid)["effects"].items():
                if k == "elemDmg":
                    for el, x in v.items():
                        out["elemDmg"][el] = out["elemDmg"].get(el, 0.0) + x
                else:
                    out[k] = out.get(k, 0.0) + v
        return out

    def refresh_perks(self):
        self.rs.chance_bonus = self.dcfg["breakthrough"] + self.perk_totals()["breakthrough"]

    def join_sect(self, sid, log=True):
        h = self.hero
        if sid in h.members or sid not in self.data.sects:
            return False
        if len(h.members) >= MAX_SECTS:
            if log:
                self.log.append(f"你已經加入了 {MAX_SECTS} 個宗門，無法再加入。")
            return False
        h.members.append(sid)
        h.sects[sid] = max(h.sects.get(sid, 0), 1)
        self.refresh_perks()
        if log:
            self.log.append(f"你加入了「{self.data.sects[sid]['name']}」！福利：{self.perk_of(sid)['desc']}")
        return True

    def pay_stipends(self):
        t = self.perk_totals()["stipend"]
        if t:
            n = int(t * (1 + self.hero.realm))
            self.hero.add("lingshi", n)
            self.log.append(f"宗門發放本月俸祿：靈石 +{n}")

    # ================= 店舖 =================
    def shops_today_shady(self, loc):
        """今天這個地點有沒有奸商？回傳 {kind, x, y} 或 None（決定性：每 period 日重新抽籤）。"""
        m = self.data.market["shady"]
        if self.mode != "loc" and loc is None:
            return None
        ltype = next((l["type"] for w in self.data.regions for g in w["regions"] for l in g["locations"] if l["id"] == loc), "")
        if ltype not in m["types_in"]:
            return None
        period = self.day // m["period_days"]
        r = _rng("shady", loc, period)
        if r.random() >= m["chance"]:
            return None
        kinds = list(m["kinds"])
        kind = r.choices(kinds, weights=[m["kinds"][k]["weight"] for k in kinds])[0]
        mp = self.get_map("loc:" + loc)
        spots = mp.get("spots") or [mp["npcSpot"]]
        x, y = r.choice(spots)
        return {"kind": kind, "x": x, "y": y, "period": period}

    def _open_shop(self, kind, loc=None):
        self.ui = {"shop": {"kind": kind, "loc": loc or self.cur_loc, "appraised": False}}

    def _shop_items(self, ctx):
        mk = self.data.market
        if ctx["kind"] == "shady":
            return mk["shady"]["items"]
        return mk["shops"][ctx["kind"]]["items"]

    def _price(self, ctx, item, base):
        pt = self.perk_totals()
        p = base * self.dcfg["price"] * (1 - min(0.3, pt["discount"])) * self.wev_mod(ctx["loc"], "price")
        if ctx["kind"] == "shady":
            sh = self.shady_now(ctx["loc"])
            p *= self.data.market["shady"]["kinds"][sh["kind"]]["price_mult"] if sh else 1
        return max(1, round(p))

    def shady_now(self, loc):
        return self.shops_today_shady(loc)

    def _bought_key(self, ctx, item):
        return f"{ctx['loc']}:{ctx['kind']}:{item}:{self.day if ctx['kind'] != 'shady' else self.day // self.data.market['shady']['period_days']}"

    def shop_view(self):
        ctx = (getattr(self, "ui", {}) or {}).get("shop")
        if not ctx or self.mode != "loc":
            return None
        mk = self.data.market
        items = []
        for iid, it in self._shop_items(ctx).items():
            left = None
            if it.get("daily") is not None:
                left = max(0, it["daily"] - self.hero.bought.get(self._bought_key(ctx, iid), 0))
            if itemdb.cat(iid) == "圖錄" and self.hero.count(iid) > 0:
                left = 0
            items.append({"id": iid, "name": item_name(iid), "price": self._price(ctx, iid, it["price"]), "left": left})
        sells = []
        if ctx["kind"] != "shady":
            for iid, price in mk["shops"][ctx["kind"]]["sell"].items():
                if self.hero.count(iid):
                    sells.append({"id": iid, "name": item_name(iid), "price": round(price * (1 + self.perk_totals()["discount"])), "have": self.hero.count(iid)})
        name = mk["shops"][ctx["kind"]]["name"] if ctx["kind"] != "shady" else "神秘商人"
        v = {"kind": ctx["kind"], "name": name, "items": items, "sells": sells, "lingshi": self.hero.count("lingshi")}
        if ctx["kind"] == "shady":
            v["appraise_cost"] = mk["shady"]["appraise_cost"]
            v["appraised"] = ctx.get("hint") or None
            v["greeting"] = _rng("greet", ctx["loc"], self.day // mk["shady"]["period_days"]).choice(mk["shady"]["greetings"])
        return v

    def _td_buy(self, item="heal", qty=1, **_):
        ctx = (getattr(self, "ui", {}) or {}).get("shop")
        if not ctx or self.mode != "loc":
            return
        h = self.hero
        items = self._shop_items(ctx)
        if item not in items:
            return
        it = items[item]
        if itemdb.cat(item) == "圖錄" and h.count(item) > 0:
            self.log.append("這本書你已經有了。")
            return
        key = self._bought_key(ctx, item)
        if it.get("daily") is not None and h.bought.get(key, 0) >= it["daily"]:
            self.log.append("這個貨賣完了，明天再來吧。")
            return
        price = self._price(ctx, item, it["price"])
        if not h.remove("lingshi", price):
            self.log.append("靈石不夠。")
            return
        h.bought[key] = h.bought.get(key, 0) + 1
        if len(h.bought) > 200:                      # 清掉舊的每日記錄
            h.bought = {k: v for k, v in h.bought.items() if k == key}
        if ctx["kind"] == "shady":
            sh = self.shady_now(ctx["loc"])
            fake = self.data.market["shady"]["kinds"][sh["kind"]]["fake_rate"] if sh else 0
            if self.rng.random() < fake:
                self.log.append(f"（-{price} 靈石）回頭一看，你買到的{item_name(item)}竟是麵粉搓的假貨！")
                return
        h.add(item)
        self.log.append(f"買下了{item_name(item)}（-{price} 靈石）")

    def _td_sell(self, item="herb", **_):
        ctx = (getattr(self, "ui", {}) or {}).get("shop")
        if not ctx or self.mode != "loc" or ctx["kind"] == "shady":
            return
        price = self.data.market["shops"][ctx["kind"]]["sell"].get(item)
        if price and self.hero.remove(item):
            gain = round(price * (1 + self.perk_totals()["discount"]))
            self.hero.add("lingshi", gain)
            self.log.append(f"賣出了{item_name(item)}（+{gain} 靈石）")

    def _td_appraise(self, **_):
        ctx = (getattr(self, "ui", {}) or {}).get("shop")
        if not ctx or ctx["kind"] != "shady":
            return
        sh = self.shady_now(ctx["loc"])
        cost = self.data.market["shady"]["appraise_cost"]
        if ctx.get("hint"):
            return
        if not self.hero.remove("lingshi", cost):
            self.log.append("靈石不夠付鑑定費。")
            return
        ctx["hint"] = self.data.market["shady"]["kinds"][sh["kind"]]["hint"] if sh else "……"
        self.log.append(f"你花 {cost} 靈石請人鑑定：" + ctx["hint"])

    # ================= 布告欄 =================
    def _gongfa_candidates(self):
        h = self.hero
        order = {r["id"]: i for i, r in enumerate(self.data.realms)}
        out = [g for g in self.data.gongfa.values() if g["id"] not in h.gongfa and g.get("combat") and order.get(g.get("minRealm", "mortal"), 0) <= h.realm + 1]
        return sorted(out, key=lambda g: g["id"])

    def fair_offers(self, loc):
        """本週交易會：依主角境界（與當前需要）量身打造的易物條件。決定性，同週內不變。"""
        h = self.hero
        r = _rng("fair", loc, self.day // WEEK, h.realm)
        V = self.data.market["fair"]["value"]
        scale = 1 + h.realm
        offers = []
        # 1 補給：靈石換丹藥（略優惠）
        it = r.choice(["heal", "mpill"])
        n = r.randint(2, 4)
        offers.append({"give": {"lingshi": round(V[it] * n * r.uniform(.72, .9))}, "get": {it: n}})
        # 2 易物：靈草換丹藥
        it2 = r.choice(["heal", "mpill"])
        n2 = r.randint(1, 3)
        need = max(2, round(V[it2] * n2 / V["herb"] * r.uniform(.7, .9)))
        offers.append({"give": {"herb": need}, "get": {it2: n2}})
        # 3 針對主角現況：卡在瓶頸沒丹藥 → 突破丹；否則以靈石換靈液
        bottleneck = h.level >= self.rs.realm(h)["levelRange"][1] - 1
        if (bottleneck or h.count("pill") == 0) and h.realm >= 1:
            offers.append({"give": {"lingshi": round(V["pill"] * r.uniform(.8, .95) * (1 + 0.15 * h.realm))}, "get": {"pill": 1}})
        else:
            offers.append({"give": {"lingshi": round(V["lingye"] * r.uniform(.8, .95))}, "get": {"lingye": 1}})
        # 4 功法殘卷：符合目前境界能學的功法
        cands = self._gongfa_candidates()
        if cands:
            g = r.choice(cands)
            offers.append({"give": {"lingye": 1, "lingshi": 150 * scale}, "get": {"gongfa": g["id"]}, "title": f"《{g['name']}》殘卷"})
        for i, o in enumerate(offers):
            o["id"] = i
            o["done"] = bool(h.flags.get(f"fair:{loc}:{self.day // WEEK}:{i}"))
            if "gongfa" in o["get"] and o["get"]["gongfa"] in h.gongfa:
                o["done"] = True
        return offers

    def recruit_offer(self, loc):
        """本週宗門招募：從境界足夠、尚未加入的宗門中抽一個。"""
        h = self.hero
        r = _rng("recruit", loc, self.day // WEEK)
        pool = sorted(sid for sid in self.data.sects
                      if sid in self.data.sect_perks["perks"] and sid not in h.members and self.data.sect_perks["perks"][sid]["minRealm"] <= h.realm)
        if not pool or len(h.members) >= MAX_SECTS:
            return None
        sid = r.choice(pool)
        pk = self.perk_of(sid)
        return {"sect": sid, "name": self.data.sects[sid]["name"], "align": self.data.sects[sid]["alignment"], "perk": pk["name"], "desc": pk["desc"],
                "fee": 30 * (1 + h.realm)}

    def board_view(self):
        b = (getattr(self, "ui", {}) or {}).get("board")
        if not b or self.mode != "loc":
            return None
        loc = b["loc"]
        r = _rng("theme", loc, self.day // WEEK)
        host = self.data.sects[r.choice(sorted(self.data.sects))]["name"]
        theme = r.choice(self.data.market["fair"]["themes"])
        offers = self.fair_offers(loc)
        for o in offers:
            o["give_txt"] = "、".join(f"{item_name(k)}×{v}" for k, v in o["give"].items())
            o["get_txt"] = o.get("title") or "、".join(f"{item_name(k)}×{v}" for k, v in o["get"].items())
            o["ok"] = all(self.hero.count(k) >= v for k, v in o["give"].items()) and not o["done"]
        return {"title": f"{host}主辦・{theme}交易會", "offers": offers, "recruit": self.recruit_offer(loc),
                "members": [{"id": s, "name": self.data.sects[s]["name"], "perk": self.perk_of(s)["desc"]} for s in self.hero.members]}

    def _td_barter(self, idx=0, **_):
        b = (getattr(self, "ui", {}) or {}).get("board")
        if not b or self.mode != "loc":
            return
        h = self.hero
        offers = self.fair_offers(b["loc"])
        i = int(idx)
        if not 0 <= i < len(offers):
            return
        o = offers[i]
        if o["done"]:
            self.log.append("這筆交易已經完成了。")
            return
        if not all(h.count(k) >= v for k, v in o["give"].items()):
            self.log.append("你的東西不夠，對方搖了搖頭。")
            return
        for k, v in o["give"].items():
            h.remove(k, v)
        for k, v in o["get"].items():
            if k == "gongfa":
                if v not in h.gongfa:
                    h.gongfa.append(v)
                    self.rs.apply_stats(h)
                    self.log.append(f"你研讀殘卷，習得功法：{self.data.gongfa[v]['name']}")
            else:
                h.add(k, v)
        h.flags[f"fair:{b['loc']}:{self.day // WEEK}:{i}"] = True
        self.log.append("交易達成！")

    def _td_join(self, sect="", **_):
        b = (getattr(self, "ui", {}) or {}).get("board")
        if not b or self.mode != "loc":
            return
        rec = self.recruit_offer(b["loc"])
        if not rec or rec["sect"] != sect:
            return
        if not self.hero.remove("lingshi", rec["fee"]):
            self.log.append(f"入門費 {rec['fee']} 靈石不夠。")
            return
        self.join_sect(sect)

    def _td_board_close(self, **_):
        self.ui = {}

    # ================= 道侶 =================
    def cand_of(self, cid):
        return self.data.companions["candidates"].get(cid)

    def partner_spec(self):
        cid = self.hero.companion
        c = self.cand_of(cid) if cid else None
        if not c:
            return None
        return {"id": cid, "name": c["name"], "el": c["element"], "role": c["role"], "atk": c["atk"], "sprite": c["sprite"]}

    def _talk_candidate(self, e):
        h = self.hero
        cid = e["cid"]
        c = self.cand_of(cid)
        if not c:
            return
        a = h.affinity.get(cid, 0)
        from . import dialogue
        if h.companion == cid:
            self.log.append(f"「{c['name']}」正陪在你身邊，對你微微一笑。")
            return
        if not h.flags.get(f"met:{cid}"):
            dialogue.start(self.data, h, f"cmp_{cid}_intro", self.log, self.rs)
            return
        if a >= 40 and not h.flags.get(f"event:{cid}"):
            dialogue.start(self.data, h, f"cmp_{cid}_event", self.log, self.rs)
            return
        if a >= 100 and not h.companion and h.realm >= c["minRealm"] and h.flags.get(f"decline:{cid}", -1) != self.day and not h.flags.get(f"partner:{cid}"):
            dialogue.start(self.data, h, f"cmp_{cid}_propose", self.log, self.rs)
            return
        self.ui = {"cand": {"cid": cid}}

    def cand_view(self):
        u = (getattr(self, "ui", {}) or {}).get("cand")
        if not u:
            return None
        cid = u["cid"]
        c = self.cand_of(cid)
        h = self.hero
        gv = self.data.companions["gifts"]
        gifts = [{"id": k, "name": item_name(k), "have": h.count(k), "gain": gv[k] * (2 if k in c["likes"] else 1), "like": k in c["likes"]} for k in gv]
        gifts.append({"id": "lingshi", "name": "靈石×50", "have": h.count("lingshi"), "gain": 2 * (2 if "lingshi" in c["likes"] else 1), "like": "lingshi" in c["likes"]})
        return {"cid": cid, "name": c["name"], "affinity": h.affinity.get(cid, 0), "gifts": gifts, "gifted": h.flags.get(f"gift:{cid}") == self.day,
                "chatted": h.flags.get(f"chat:{cid}") == self.day, "need_realm": c["minRealm"], "hasPartner": bool(h.companion)}

    def _add_affinity(self, cid, n):
        self.hero.affinity[cid] = min(150, self.hero.affinity.get(cid, 0) + n)

    def _td_gift(self, item="herb", **_):
        u = (getattr(self, "ui", {}) or {}).get("cand")
        if not u:
            return
        cid, h = u["cid"], self.hero
        c = self.cand_of(cid)
        if h.flags.get(f"gift:{cid}") == self.day:
            self.log.append(f"「{c['name']}」：今天已經收過你的禮物了，明天再說吧。")
            return
        gv = self.data.companions["gifts"]
        if item == "lingshi":
            if not h.remove("lingshi", 50):
                self.log.append("靈石不夠。")
                return
            gain = 2
        elif item in gv and h.remove(item):
            gain = gv[item]
        else:
            self.log.append("你沒有這樣東西。")
            return
        like = item in c["likes"]
        if like:
            gain *= 2
        h.flags[f"gift:{cid}"] = self.day
        self._add_affinity(cid, gain)
        self.log.append(f"「{c['name']}」收下了{item_name(item)}" + ("，眼睛一亮：「正是我想要的！」" if like else "，輕聲道謝。") + f"（好感 +{gain}）")

    def _td_chat(self, **_):
        u = (getattr(self, "ui", {}) or {}).get("cand")
        if not u:
            return
        cid, h = u["cid"], self.hero
        c = self.cand_of(cid)
        if h.flags.get(f"chat:{cid}") == self.day:
            self.log.append(f"「{c['name']}」：今天已經聊了很多了。")
            return
        h.flags[f"chat:{cid}"] = self.day
        self._add_affinity(cid, 3)
        self.log.append(f"你與{c['name']}閒聊了一陣，氣氛融洽。（好感 +3）")

    def _td_cand_close(self, **_):
        self.ui = {}
