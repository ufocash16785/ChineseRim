"""劇情對話：觸發、分支、效果。進行中的對話存在 Character.dialogue（隨存檔保存）。"""


def _quest_at(ch):
    q = ch.quest
    return q.get("q"), q.get("o"), q.get("done")


from .character import item_name


def starts_with_npc(d):
    return d["nodes"]["start"]["speaker"] != "旁白"


def find_trigger(data, ch, loc=None, arrive=None, only=None):
    """only: None＝全部；"narration"＝只旁白開場；"npc"＝只 NPC 開場（需要和 NPC 對話才觸發）。"""
    """回傳第一個符合條件且尚未看過的對話 id。"""
    completed = set(ch.quest.get("completed", []))
    quest_ids = None
    for did, d in data.dialogues.items():
        if ch.flags.get("seen:" + did):
            continue
        t = d["trigger"]
        if only == "narration" and starts_with_npc(d):
            continue
        if only == "npc" and not starts_with_npc(d):
            continue
        if "onQuestDone" in t:
            if loc is None and arrive is None and t["onQuestDone"] in completed:
                return did
        elif (loc is not None and t.get("loc") == loc) or (arrive is not None and t.get("arrive") == arrive):
            if quest_ids is None:
                arc = next(a for a in data.arcs if a["id"] == ch.quest["arc"])
                quest_ids = [x["id"] for x in arc["quests"]]
            qi, oi, done = _quest_at(ch)
            if not done and qi < len(quest_ids) and quest_ids[qi] == t["quest"] and oi == t["obj"]:
                return did
    return None


def _apply(ch, effects, data, log, realms=None):
    for e in effects or []:
        if "flag" in e:
            ch.flags[e["flag"]] = True
        elif "item" in e:
            n = e.get("n", 1)
            if n >= 0:
                ch.add(e["item"], n)
                log.append(f"  獲得 {item_name(e['item'])} ×{n}")
            else:
                ch.remove(e["item"], min(-n, ch.count(e["item"])))
                log.append(f"  消耗 {item_name(e['item'])} ×{-n}")
        elif "affinity" in e and realms is not None:
            sess = realms.session
            sess._add_affinity(e["affinity"], e["n"])
            log.append(f"  好感 +{e['n']}")
        elif "companion" in e and realms is not None:
            if not ch.companion:
                ch.companion = e["companion"]
                log.append(f"  ♥ {realms.session.cand_of(e['companion'])['name']}成為了你的道侶，從此與你並肩作戰！")
        elif "join" in e and realms is not None:
            realms.session.join_sect(e["join"])
        elif "karma" in e:
            from . import karma
            for kk, nn in e["karma"].items():
                karma.add(ch, kk, nn, log)
        elif "boss" in e and realms is not None:
            realms.session.pending_boss = {"id": e["boss"], "did": ch.dialogue.get("id")}
        elif "learn" in e:
            if e["learn"] not in ch.gongfa:
                ch.gongfa.append(e["learn"])
                log.append(f"  習得功法：{data.gongfa[e['learn']]['name']}")
                if realms:
                    hp = ch.hp
                    realms.apply_stats(ch)          # 重算 maxHp 加成
                    ch.hp = min(hp, ch.max_hp)
        elif "setRealm" in e and realms:
            realms.set_realm(ch, e["setRealm"])
            ch.level = max(ch.level, realms.realm(ch)["levelRange"][0])
            log.append(f"  你突破至{realms.realm(ch)['name']}！")
        elif "rep" in e:
            ch.sects[e["rep"]] = max(-4, min(4, ch.sects.get(e["rep"], 0) + e.get("n", 1)))
            log.append(f"  {data.sects[e['rep']]['name']}聲望 {ch.sects[e['rep']]}/4")
        elif "hpFrac" in e:
            ch.hp = max(1, ch.hp + ch.max_hp * e["hpFrac"])
            log.append("  你受了傷")
        elif "level" in e:
            ch.level += e["level"]     # 對話獎勵可能略超上限；突破前 gain_level 仍會夾回


def _enter(data, ch, did, node_id, log, realms=None):
    node = data.dialogues[did]["nodes"][node_id]
    ch.dialogue = {"id": did, "node": node_id}
    log.append(f"「{node['speaker']}」{node['text']}")
    _apply(ch, node.get("effects"), data, log, realms)


def start(data, ch, did, log, realms=None):
    ch.flags["seen:" + did] = True
    _enter(data, ch, did, "start", log, realms)


def _ok(ch, req):
    if not req:
        return True
    if "flag" in req and not ch.flags.get(req["flag"]):
        return False
    if "item" in req and ch.count(req["item"]) < req.get("n", 1):
        return False
    return True


def view(data, ch):
    if not ch.dialogue:
        return None
    node = data.dialogues[ch.dialogue["id"]]["nodes"][ch.dialogue["node"]]
    choices = [{"i": i, "text": c["text"]} for i, c in enumerate(node.get("choices", [])) if _ok(ch, c.get("require"))]
    return {"speaker": node["speaker"], "text": node["text"], "choices": choices, "cont": not node.get("choices")}


def choose(data, ch, idx, log, realms=None):
    """idx=None 表示『繼續』。回傳對話是否仍在進行。"""
    did = ch.dialogue["id"]
    node = data.dialogues[did]["nodes"][ch.dialogue["node"]]
    if node.get("choices"):
        if idx is None or not 0 <= idx < len(node["choices"]) or not _ok(ch, node["choices"][idx].get("require")):
            return True
        c = node["choices"][idx]
        log.append(f"▷ {c['text']}")
        _apply(ch, c.get("effects"), data, log, realms)
        nxt = c.get("next")
    else:
        nxt = node.get("next")
    if nxt:
        _enter(data, ch, did, nxt, log, realms)
        return True
    ch.dialogue = {}
    return False


def gating(data, ch, quest_id, obj):
    """該任務目標是否有尚未播放的簡報對話（有的話，目標先不推進，播完才開始累計）。"""
    return any(not ch.flags.get("seen:" + did) and d["trigger"].get("quest") == quest_id and d["trigger"].get("obj") == obj
               for did, d in data.dialogues.items())


def gating_hint(data, ch, quest_id, obj):
    for did, d in data.dialogues.items():
        t = d["trigger"]
        if not ch.flags.get("seen:" + did) and t.get("quest") == quest_id and t.get("obj") == obj:
            names = {l["id"]: l["name"] for w in data.regions for g in w["regions"] for l in g["locations"]}
            if "arrive" in t:
                rn = {g["id"]: g["name"] for w in data.regions for g in w["regions"]}
                return f"劇情：前往「{rn.get(t['arrive'], t['arrive'])}」"
            return f"劇情：前往「{names.get(t['loc'], t['loc'])}」"
    return ""


def pending_npc(data, ch, loc):
    """目前該地點有沒有「要找 NPC 說話」的劇情？回傳說話者名字或 None。"""
    if not ch.quest or ch.quest.get("done"):
        return None
    did = find_trigger(data, ch, loc, None, only="npc")
    return data.dialogues[did]["nodes"]["start"]["speaker"] if did else None
