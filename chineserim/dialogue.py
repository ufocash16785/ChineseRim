"""劇情對話：觸發、分支、效果。進行中的對話存在 Character.dialogue（隨存檔保存）。"""


def _quest_at(ch):
    q = ch.quest
    return q.get("q"), q.get("o"), q.get("done")


def find_trigger(data, ch, loc=None):
    """回傳第一個符合條件且尚未看過的對話 id。"""
    completed = set(ch.quest.get("completed", []))
    quest_ids = None
    for did, d in data.dialogues.items():
        if ch.flags.get("seen:" + did):
            continue
        t = d["trigger"]
        if "onQuestDone" in t:
            if loc is None and t["onQuestDone"] in completed:
                return did
        elif loc is not None and t["loc"] == loc:
            if quest_ids is None:
                arc = next(a for a in data.arcs if a["id"] == ch.quest["arc"])
                quest_ids = [x["id"] for x in arc["quests"]]
            qi, oi, done = _quest_at(ch)
            if not done and qi < len(quest_ids) and quest_ids[qi] == t["quest"] and oi == t["obj"]:
                return did
    return None


def _apply(ch, effects, data, log):
    for e in effects or []:
        if "flag" in e:
            ch.flags[e["flag"]] = True
        elif "item" in e:
            ch.add(e["item"], e.get("n", 1))
            log.append(f"  獲得 {e['item']} ×{e.get('n', 1)}")
        elif "rep" in e:
            ch.sects[e["rep"]] = max(-4, min(4, ch.sects.get(e["rep"], 0) + e.get("n", 1)))
            log.append(f"  {data.sects[e['rep']]['name']}聲望 {ch.sects[e['rep']]}/4")
        elif "hpFrac" in e:
            ch.hp = max(1, ch.hp + ch.max_hp * e["hpFrac"])
            log.append("  你受了傷")
        elif "level" in e:
            ch.level += e["level"]     # 對話獎勵可能略超上限；突破前 gain_level 仍會夾回


def _enter(data, ch, did, node_id, log):
    node = data.dialogues[did]["nodes"][node_id]
    ch.dialogue = {"id": did, "node": node_id}
    log.append(f"「{node['speaker']}」{node['text']}")
    _apply(ch, node.get("effects"), data, log)


def start(data, ch, did, log):
    ch.flags["seen:" + did] = True
    _enter(data, ch, did, "start", log)


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


def choose(data, ch, idx, log):
    """idx=None 表示『繼續』。回傳對話是否仍在進行。"""
    did = ch.dialogue["id"]
    node = data.dialogues[did]["nodes"][ch.dialogue["node"]]
    if node.get("choices"):
        if idx is None or not 0 <= idx < len(node["choices"]) or not _ok(ch, node["choices"][idx].get("require")):
            return True
        c = node["choices"][idx]
        log.append(f"▷ {c['text']}")
        _apply(ch, c.get("effects"), data, log)
        nxt = c.get("next")
    else:
        nxt = node.get("next")
    if nxt:
        _enter(data, ch, did, nxt, log)
        return True
    ch.dialogue = {}
    return False


def gating(data, ch, quest_id, obj):
    """該任務目標是否有尚未播放的簡報對話（有的話，目標先不推進，播完才開始累計）。"""
    return any(not ch.flags.get("seen:" + did) and d["trigger"].get("quest") == quest_id and d["trigger"].get("obj") == obj
               for did, d in data.dialogues.items())
