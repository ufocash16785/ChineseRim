"""物品總表（讀 data/items.json）。儲物袋容量無限，這裡只負責名稱、分類與戰鬥道具效果。"""
import json
import pathlib

_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "items.json"
_REG = None


def registry():
    global _REG
    if _REG is None:
        _REG = json.loads(_PATH.read_text(encoding="utf-8"))
    return _REG


def info(item_id):
    return registry()["items"].get(item_id)


def name(item_id):
    i = info(item_id)
    return i["name"] if i else item_id


def cat(item_id):
    i = info(item_id)
    return i["cat"] if i else "材料"
