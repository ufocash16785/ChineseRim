"""載入 data/*.json（唯一資料來源）。第三方可在 mods/<類別>/*.json 追加，同 id 後者覆蓋。"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def _merge(d, pattern, key):
    """依檔名順序合併 data/<pattern> 中的 key（同 id 後者覆蓋）。"""
    out = {}
    for f in sorted(pathlib.Path(d).glob(pattern)):
        out.update(_load(f).get(key, {}))
    return out


class GameData:
    def __init__(self, data_dir=None, mod_dir=None):
        d = pathlib.Path(data_dir or ROOT / "data")
        self.realms_doc = _load(d / "realms.json")
        self.realms = self.realms_doc["realms"]
        self.spirit_roots = self.realms_doc["spiritRoots"]
        self.sects = {s["id"]: s for s in _load(d / "sects.json")["sects"]}
        tech = _load(d / "techniques.json")
        self.gongfa = {g["id"]: g for g in tech.get("gongfa", [])}
        self.spells = {g["id"]: g for g in tech.get("spells", [])}
        tr = _load(d / "treasures.json")
        self.treasures = {t["id"]: t for t in tr.get("treasures", [])}
        self.pills = {t["id"]: t for t in tr.get("pills", [])}
        self.characters = {c["id"]: c for c in _load(d / "characters.json")["characters"]}
        self.arcs = _load(d / "story_arcs.json")["arcs"]
        self.dialogues = _merge(d, "dialogues*.json", "dialogues")
        self.ambient = _load(d / "ambient.json")
        self.farming = _load(d / "farming.json")
        self.quest_rules = _merge(d, "quests*.json", "arcs")
        self.regions = _load(d / "regions.json")["worlds"]
        self.config = {"elemAdvMult": 1.5, "elemDisMult": 0.75}
        if mod_dir:
            self._merge_mods(pathlib.Path(mod_dir))

    def _merge_mods(self, m):
        for sub, target, key in (("techniques", self.gongfa, "gongfa"), ("techniques", self.spells, "spells"),
                                 ("sects", self.sects, "sects"), ("pills", self.pills, "pills")):
            for f in sorted((m / sub).glob("*.json")) if (m / sub).is_dir() else []:
                for e in _load(f).get(key, []):
                    target[e["id"]] = e

    def realm_index(self, realm_id: str) -> int:
        for i, r in enumerate(self.realms):
            if r["id"] == realm_id:
                return i
        raise KeyError(realm_id)

    def root_type(self, root_id: str) -> dict:
        for t in self.spirit_roots["types"]:
            if t["id"] == root_id:
                return t
        raise KeyError(root_id)
