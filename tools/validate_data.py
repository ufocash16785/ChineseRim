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
EDITOR_ID = re.compile(r"^(CR|XN)_[A-Za-z0-9]+(_[A-Za-z0-9]+)*$")

errors: list[str] = []
warnings: list[str] = []


def load(name: str):
    with (DATA / f"{name}.json").open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if name in ("regions", "story_arcs"):                   # 多劇本：合併 <name>_*.json
        key = "worlds" if name == "regions" else "arcs"
        for f in sorted(DATA.glob(f"{name}_*.json")):
            with f.open(encoding="utf-8") as fh:
                doc[key] = doc[key] + json.load(fh)[key]
    return doc


def load_merged(pattern: str, key: str):
    out = {}
    for f in sorted(DATA.glob(pattern)):
        with f.open(encoding="utf-8") as fh:
            out.update(json.load(fh).get(key, {}))
    return out


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
    qr = load_merged("quests*.json", "arcs")
    all_regions = {g["id"] for w in load("regions")["worlds"] for g in w["regions"]}
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
                if o["type"] == "arrive" and o["loc"] not in all_regions:
                    errors.append(f"quests/{qid}: 未知區域 {o['loc']}")
                if o["type"] not in ("visit", "kill", "arrive", "level", "realm", "item", "flag", "treasure"):
                    errors.append(f"quests/{qid}: 未知條件類型 {o['type']}")
    all_q = {q["id"] for a in arcs["arcs"] for q in a["quests"]}
    for did, d in load_merged("dialogues*.json", "dialogues").items():
        t = d["trigger"]
        if "quest" in t and t["quest"] not in all_q:
            errors.append(f"dialogues/{did}: 未知任務 {t['quest']}")
        if "onQuestDone" in t and t["onQuestDone"] not in all_q:
            errors.append(f"dialogues/{did}: 未知任務 {t['onQuestDone']}")
        if "loc" in t and t["loc"] not in all_locs:
            errors.append(f"dialogues/{did}: 未知地點 {t['loc']}")
        if "arrive" in t and t["arrive"] not in all_regions:
            errors.append(f"dialogues/{did}: 未知區域 {t['arrive']}")
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
                if "learn" in e and e["learn"] not in {g["id"] for g in load("techniques")["gongfa"]}:
                    errors.append(f"dialogues/{did}/{nid}: 未知功法 {e['learn']}")
                if "setRealm" in e and e["setRealm"] not in {r["id"] for r in load("realms")["realms"]}:
                    errors.append(f"dialogues/{did}/{nid}: 未知境界 {e['setRealm']}")
                if "rep" in e and e["rep"] not in sect_ids:
                    errors.append(f"dialogues/{did}/{nid}: 未知門派 {e['rep']}")
    dlg = load_merged("dialogues*.json", "dialogues")
    set_flags = {e["flag"] for d in dlg.values() for n in d["nodes"].values()
                 for e in list(n.get("effects", [])) + [x for c in n.get("choices", []) for x in c.get("effects", [])] if "flag" in e}
    bosses = load("bosses")
    boss_ids = set(bosses["bosses"])
    for did, d in dlg.items():
        for nid, n in d["nodes"].items():
            for e in list(n.get("effects", [])) + [x for c in n.get("choices", []) for x in c.get("effects", [])]:
                if "boss" in e:
                    if e["boss"] not in boss_ids:
                        errors.append(f"dialogues/{did}/{nid}: 未知主要對手 {e['boss']}")
                    else:
                        set_flags |= {x["flag"] for x in bosses["bosses"][e["boss"]].get("on_win", []) if "flag" in x}
    drops, item_ids = load("drops"), set(load("items")["items"])
    for bid, b in bosses["bosses"].items():
        if b.get("drops") not in drops["tables"]:
            errors.append(f"bosses/{bid}: 掉落表 {b.get('drops')} 不存在")
    for tname, rows in drops["tables"].items():
        for r in rows:
            if r["item"] not in item_ids:
                errors.append(f"drops/{tname}: 未知物品 {r['item']}")
    cxd = load("codex")
    for kind in ("wolf", "spider", "bear", "snake", "python", "ape", "bat"):
        if kind not in cxd["beasts"]:
            errors.append(f"codex/beasts: 缺少 {kind}")
    for bid in load("bosses")["bosses"]:
        if bid not in cxd["bosses"]:
            errors.append(f"codex/bosses: 缺少 {bid}")
    for b in (cxd["beast_book"], cxd["pet_book"]):
        if b not in item_ids:
            errors.append(f"codex: 未知物品 {b}")
    for kind in load("pets")["pets"]:
        if kind not in cxd["pet_tips"]:
            errors.append(f"codex/pet_tips: 缺少 {kind}")
    lg = load("legacy")
    all_ends = {e["id"] for e in load("endings")["endings"]} | {e["id"] for l in load("endings").get("campaign_endings", {}).values() for e in l}
    for eid in all_ends - set(lg["by_ending"]):
        errors.append(f"legacy/by_ending: 缺少結局 {eid}")
    for eid in set(lg["by_ending"]) - all_ends:
        errors.append(f"legacy/by_ending: 未知結局 {eid}")
    for grp in list(lg["by_ending"].values()) + list(lg["from_campaign"].values()) + [lg["both"]]:
        for it in grp.get("items", {}):
            if it not in item_ids:
                errors.append(f"legacy: 未知物品 {it}")
    camps = load("campaigns")["campaigns"]
    all_arcs = {a["id"]: a for a in arcs["arcs"]}
    for cid, c in camps.items():
        if c["start_region"] not in all_regions:
            errors.append(f"campaigns/{cid}: 未知起始區域 {c['start_region']}")
        if c.get("start_loc") and c["start_loc"] not in all_locs:
            errors.append(f"campaigns/{cid}: 未知起始地點 {c['start_loc']}")
        if not [a for a in arcs["arcs"] if a.get("campaign", "fanren") == cid]:
            errors.append(f"campaigns/{cid}: 沒有任何故事卷")
    for a in arcs["arcs"]:
        if a.get("campaign", "fanren") not in camps:
            errors.append(f"story_arcs/{a['id']}: 未知劇本 {a.get('campaign')}")
    en = load("endings")
    for cid in en.get("campaign_endings", {}):
        lst = en["campaign_endings"][cid]
        if cid not in camps or lst[-1]["when"]:
            errors.append(f"endings/{cid}: 劇本不存在或最後一個不是保底")
    ids = [e["id"] for e in en["endings"]]
    if len(ids) != len(set(ids)):
        errors.append("endings: id 重複")
    if en["endings"][-1]["when"]:
        errors.append("endings: 最後一個必須是保底（when 為空）")
    for e in en["endings"]:
        if len(e["paras"]) < 3:
            errors.append(f"endings/{e['id']}: 段落太少")
    pets = load("pets")
    for kind in pets["pets"]:
        if kind not in pets["skills"]:
            errors.append(f"pets/{kind}: 缺少專屬技能")
    for kind, sk in pets["skills"].items():
        if kind not in pets["pets"] or len(sk["val"]) != 2:
            errors.append(f"pets/skills/{kind}: 設定不合法")
    for k in pets["puppets"]:
        if k not in pets["puppet_skills"]:
            errors.append(f"pets/puppet_skills: 缺少 {k}")
    if len(pets["puppet_slots"]) != pets["puppet_max_level"]:
        errors.append("pets/puppet_slots: 長度需等於 puppet_max_level")
    ev = load("events")
    for t, tc in ev["types"].items():
        for k in ("drops", "table"):
            if k in tc and tc[k] not in drops["tables"]:
                errors.append(f"events/{t}: 掉落表 {tc[k]} 不存在")
        for x in tc.get("gifts", []):
            if x["item"] not in item_ids:
                errors.append(f"events/{t}: 未知物品 {x['item']}")
    w = ev["types"]["war"]
    for side in ("defend", "attack"):
        if w[side]["drops"] not in drops["tables"]:
            errors.append(f"events/war/{side}: 掉落表不存在")
    for k in w["trade"]["need"]:
        if k not in item_ids:
            errors.append(f"events/war/trade: 未知物品 {k}")
    for kk in ("avenger", "benefactor"):
        for x in load("karma")[kk].get("gifts", []):
            if x["item"] not in item_ids:
                errors.append(f"karma/{kk}: 未知物品 {x['item']}")
    for arc_id, rules in qr.items():
        arc = next((a for a in arcs["arcs"] if a["id"] == arc_id), None)
        for qid, rule in rules.items():
            for i, o in enumerate(rule["objectives"]):
                if o["type"] == "flag" and o["flag"] not in set_flags:
                    errors.append(f"quests/{qid}: 目標 {i} 的旗標 {o['flag']} 沒有任何對話會設定")
    for did, d in dlg.items():
        t = d["trigger"]
        if "quest" in t:
            n_obj = next((len(q["objectives"]) for a in arcs["arcs"] for q in a["quests"] if q["id"] == t["quest"]), 0)
            if not 0 <= t["obj"] < n_obj:
                errors.append(f"dialogues/{did}: obj {t['obj']} 超出範圍")
    fm = load("farming")
    known_items = {"herb", "lingshi", "lingye", "heal", "mpill", "pill"}
    for rid, rc in fm["recipes"].items():
        for k in list(rc["needs"]) + list(rc["gives"]):
            if k not in known_items:
                errors.append(f"farming/{rid}: 未知物品 {k}")
    for w in load("regions")["worlds"]:
        for g in w["regions"]:
            for l in g["locations"]:
                if l.get("profile", "normal") not in ("normal", "rich", "poor", "mixed", "trap"):
                    errors.append(f"regions/{l['id']}: 未知 profile {l['profile']}")
                if "minRealm" in l and not isinstance(l["minRealm"], int):
                    errors.append(f"regions/{l['id']}: minRealm 需為整數")
    perks, comp, mk = load("sect_perks"), load("companions"), load("market")
    for sid in perks["perks"]:
        if sid not in sect_ids:
            errors.append(f"sect_perks/{sid}: 不在 sects.json")
    dlg_all = load_merged("dialogues*.json", "dialogues")
    for cid, c in comp["candidates"].items():
        if c["loc"] not in all_locs:
            errors.append(f"companions/{cid}: 未知地點 {c['loc']}")
        for st in ("intro", "event", "propose"):
            if f"cmp_{cid}_{st}" not in dlg_all:
                errors.append(f"companions/{cid}: 缺少對話 cmp_{cid}_{st}")
    for kind, sh in mk["shops"].items():
        for it in list(sh["items"]) + list(sh["sell"]):
            if it not in known_items and it not in set(load("items")["items"]):
                errors.append(f"market/{kind}: 未知物品 {it}")
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
