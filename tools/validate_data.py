#!/usr/bin/env python3
"""驗證 data/*.json：結構、ID 唯一、跨檔參照（門派→地區、角色→門派、功法→境界）、EditorID 前綴。

用法：python tools/validate_data.py   （回傳非 0 表示有錯誤；警告不影響回傳值）
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EDITOR_ID = re.compile(r"^CR_[A-Za-z0-9_]+$")

errors: list[str] = []
warnings: list[str] = []


def load(name: str):
    with (DATA / f"{name}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def unique_ids(items, label):
    seen = set()
    for it in items:
        i = it.get("id")
        if not i:
            errors.append(f"{label}: 缺少 id → {it.get('name')}")
        elif i in seen:
            errors.append(f"{label}: 重複 id {i}")
        seen.add(i)
    return seen


def main() -> int:
    realms = load("realms")
    regions = load("regions")
    sects = load("sects")
    chars = load("characters")
    tech = load("techniques")
    treasures = load("treasures")
    arcs = load("story_arcs")

    realm_ids = unique_ids(realms["realms"], "realms")
    region_ids = set()
    for w in regions["worlds"]:
        for r in w["regions"]:
            region_ids.add(r["id"])
            unique_ids(r["locations"], f"regions/{r['id']}")
    sect_ids = unique_ids(sects["sects"], "sects")
    char_ids = unique_ids(chars["characters"], "characters")
    gongfa_ids = unique_ids(tech["gongfa"], "techniques.gongfa")
    unique_ids(tech["spells"], "techniques.spells")
    unique_ids(treasures["treasures"], "treasures")
    unique_ids(treasures["pills"], "pills")

    # 境界順序連續
    for i, r in enumerate(realms["realms"]):
        if r["order"] != i:
            errors.append(f"realms: {r['id']} order={r['order']} 應為 {i}")

    # 門派 → 地區、EditorID
    for s in sects["sects"]:
        if s["region"] not in region_ids:
            errors.append(f"sects/{s['id']}: 未知地區 {s['region']}")
        if not EDITOR_ID.match(s.get("editorId", "")):
            errors.append(f"sects/{s['id']}: EditorID 需以 CR_ 開頭 → {s.get('editorId')}")
    for a, b, _v in sects["relations"]["pairs"]:
        for x in (a, b):
            if x not in sect_ids:
                errors.append(f"relations: 未知門派 {x}")

    # 角色 → 門派（允許附註，如 "luoyunzong(客卿)"）
    for c in chars["characters"]:
        if not EDITOR_ID.match(c.get("editorId", "")):
            errors.append(f"characters/{c['id']}: EditorID → {c.get('editorId')}")
        for s in c.get("sect", []):
            base = re.split(r"[(（→]", s)[0]
            if base and base not in sect_ids and not re.search(r"[一-鿿]", base):
                warnings.append(f"characters/{c['id']}: 門派 {s} 不在 sects.json")

    # 功法/法術 → 境界
    for g in tech["gongfa"] + tech["spells"] + tech["abilities"]:
        if g["minRealm"] not in realm_ids:
            errors.append(f"techniques/{g['id']}: 未知境界 {g['minRealm']}")

    # 法寶 → 擁有者
    for t in treasures["treasures"]:
        o = t.get("owner")
        if o and o not in char_ids and o != "劇情":
            warnings.append(f"treasures/{t['id']}: owner {o} 不在 characters.json")

    # 主線 → 地區、Quest EditorID
    qr = load("quests")["arcs"]
    all_locs = {l["id"] for w in load("regions")["worlds"] for g in w["regions"] for l in g["locations"]}
    for arc_id, rules in qr.items():
        arc = next((a for a in arcs["arcs"] if a["id"] == arc_id), None)
        if not arc:
            errors.append(f"quests/{arc_id}: story_arcs 無此卷")
            continue
        qmap = {q["id"]: q for q in arc["quests"]}
        for qid, rule in rules.items():
            if qid not in qmap:
                errors.append(f"quests/{qid}: story_arcs 無此任務")
            elif len(rule["objectives"]) != len(qmap[qid]["objectives"]):
                errors.append(f"quests/{qid}: 目標數 {len(rule['objectives'])} != story_arcs {len(qmap[qid]['objectives'])}")
            for o in rule["objectives"]:
                if o["type"] in ("visit", "kill") and o["loc"] != "total" and o["loc"] not in all_locs:
                    errors.append(f"quests/{qid}: 未知地點 {o['loc']}")
    all_q = {q["id"] for a in arcs["arcs"] for q in a["quests"]}
    for did, d in load("dialogues")["dialogues"].items():
        t = d["trigger"]
        if "quest" in t and t["quest"] not in all_q:
            errors.append(f"dialogues/{did}: 未知任務 {t['quest']}")
        if "onQuestDone" in t and t["onQuestDone"] not in all_q:
            errors.append(f"dialogues/{did}: 未知任務 {t['onQuestDone']}")
        if "loc" in t and t["loc"] not in all_locs:
            errors.append(f"dialogues/{did}: 未知地點 {t['loc']}")
        nodes = d["nodes"]
        if "start" not in nodes:
            errors.append(f"dialogues/{did}: 缺 start 節點")
        for nid, n in nodes.items():
            nexts = [n.get("next")] + [c.get("next") for c in n.get("choices", [])]
            for x in nexts:
                if x and x not in nodes:
                    errors.append(f"dialogues/{did}/{nid}: next 指向不存在的節點 {x}")
            effs = list(n.get("effects", [])) + [e for c in n.get("choices", []) for e in c.get("effects", [])]
            for e in effs:
                if "rep" in e and e["rep"] not in sect_ids:
                    errors.append(f"dialogues/{did}/{nid}: 未知門派 {e['rep']}")
    for a in arcs["arcs"]:
        for reg in a["region"].split("/"):
            if reg not in region_ids:
                errors.append(f"story_arcs/{a['id']}: 未知地區 {reg}")
        for q in a["quests"]:
            if not EDITOR_ID.match(q["id"]):
                errors.append(f"story_arcs/{a['id']}: Quest EditorID → {q['id']}")

    # 待核實統計
    def count_unverified(items):
        return sum(1 for it in items if it.get("verified") is False)
    unverified = (
        count_unverified(sects["sects"]) + count_unverified(chars["characters"]) +
        count_unverified(tech["gongfa"]) + count_unverified(tech["spells"]) +
        count_unverified(treasures["treasures"]) + count_unverified(treasures["pills"]) +
        sum(count_unverified(r["locations"]) for w in regions["worlds"] for r in w["regions"])
    )

    for w in warnings:
        print("警告:", w)
    for e in errors:
        print("錯誤:", e)
    print(f"門派 {len(sect_ids)}、角色 {len(char_ids)}、功法 {len(gongfa_ids)}、地區 {len(region_ids)}、待核實條目 {unverified}")
    print("通過" if not errors else f"失敗（{len(errors)} 個錯誤）")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
