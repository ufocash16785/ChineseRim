"""五行相生相剋（原 CR_ElementResolver / ElementHook.cpp）。"""
ADV_MULT = 1.5
DIS_MULT = 0.75

# 變異屬性映射父五行
PARENT = {"雷": "木", "風": "木", "冰": "水", "暗": "水"}
_OVERCOMES = {("木", "土"), ("土", "水"), ("水", "火"), ("火", "金"), ("金", "木")}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}


def parent_element(e: str) -> str:
    return PARENT.get(e, e)


def overcomes(a: str, b: str) -> bool:
    return (parent_element(a), parent_element(b)) in _OVERCOMES


def element_multiplier(attacker: str, defender: str, adv: float = ADV_MULT, dis: float = DIS_MULT) -> float:
    if not attacker or not defender:
        return 1.0
    if overcomes(attacker, defender):
        return adv
    if overcomes(defender, attacker):
        return dis
    return 1.0
