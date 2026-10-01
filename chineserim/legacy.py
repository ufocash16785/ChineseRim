"""跨劇本傳承：通關結局記在 legacy.json（與存檔分開），開新遊戲時依傳承給予起手獎勵。以 Mixin 併入 Session。"""
import json
import pathlib

from . import karma
from .character import item_name


class LegacyStore:
    def __init__(self, path=None):
        self.path = pathlib.Path(path) if path else None
        self.endings = {}          # ending_id -> {"campaign","day","dao","companion"}
        self.load()

    def load(self):
        if self.path and self.path.exists():
            try:
                self.endings = json.loads(self.path.read_text(encoding="utf-8")).get("endings", {})
            except (ValueError, OSError):
                self.endings = {}

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"endings": self.endings}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, campaign, ending_id, info):
        new = ending_id not in self.endings
        self.endings[ending_id] = dict(info, campaign=campaign)
        self.save()
        return new

    def completed(self):
        return {e["campaign"] for e in self.endings.values()}


class LegacyMixin:
    def legacy_sync(self):
        """把已決定的結局寫進傳承檔（只寫一次）。"""
        h = self.hero
        info = h.flags.get("ending")
        if info and not h.flags.get("legacy_recorded"):
            st = info.get("stats", {})
            self.legacy.record(h.campaign, info["id"], {"day": st.get("day"), "dao": st.get("dao"), "companion": st.get("companion")})
            h.flags["legacy_recorded"] = True

    def legacy_bonuses(self, campaign):
        """開始 campaign 時會得到的傳承獎勵：[{title,text,items,karma}]。"""
        cfg = self.data.legacy
        done = self.legacy.completed()
        out = []
        for src, b in cfg["from_campaign"].items():
            if src in done and b["to"] == campaign:
                out.append({"title": b["title"], "text": b["text"], "items": dict(b.get("items", {})), "karma": {}})
        if {"fanren", "xianni"} <= done:
            b = cfg["both"]
            out.append({"title": b["title"], "text": b["text"], "items": dict(b.get("items", {})), "karma": {}})
        for eid in self.legacy.endings:
            b = cfg["by_ending"].get(eid)
            if b:
                out.append({"title": b["title"], "text": b["text"], "items": dict(b.get("items", {})), "karma": dict(b.get("karma", {}))})
        return out

    def apply_legacy(self, campaign):
        h = self.hero
        total = {}
        for b in self.legacy_bonuses(campaign):
            for k, n in b["items"].items():
                h.add(k, n)
            for k, n in b["karma"].items():
                total[k] = total.get(k, 0) + n
            self.log.append(f"【傳承·{b['title']}】{b['text']}" + ("（獲得 " + "、".join(f"{item_name(k)}×{n}" for k, n in b["items"].items()) + "）" if b["items"] else ""))
        cap = self.data.legacy["cap_karma"]
        for k, n in total.items():
            karma.add(h, k, min(cap, n))
        if total:
            self.log.append("【傳承】舊日的因果，仍在你身上留下了痕跡。")

    def legacy_view(self):
        cfg_end = []
        for camp, lst in [("fanren", self.data.endings["endings"])] + [(c, l) for c, l in self.data.endings.get("campaign_endings", {}).items()]:
            for e in lst:
                cfg_end.append({"id": e["id"], "title": e["title"], "campaign": camp, "got": e["id"] in self.legacy.endings})
        prev = {c: [{"title": b["title"], "text": b["text"], "items": {item_name(k): n for k, n in b["items"].items()}, "karma": b["karma"]} for b in self.legacy_bonuses(c)] for c in self.data.campaigns}
        return {"endings": cfg_end, "got": sum(1 for e in cfg_end if e["got"]), "total": len(cfg_end), "completed": sorted(self.legacy.completed()), "preview": prev}
