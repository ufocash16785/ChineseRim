"""ChineseRim 獨立引擎：不依賴 Skyrim / SKSE / Papyrus，直接讀 data/*.json 執行遊戲規則。"""
from .data import GameData
from .character import Character
from .elements import element_multiplier, overcomes, parent_element
from .realms import RealmSystem

__all__ = ["GameData", "Character", "RealmSystem", "element_multiplier", "overcomes", "parent_element"]
