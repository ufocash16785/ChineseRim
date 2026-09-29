from dataclasses import dataclass, field


@dataclass
class Character:
    name: str
    elements: list = field(default_factory=lambda: ["木"])
    root_type: str = "quad"
    realm: int = 0          # realms.json 的 order
    sub: int = 0
    level: int = 1
    hp: float = 100
    mp: float = 20
    stamina: float = 120
    max_hp: float = 100
    inventory: dict = field(default_factory=dict)   # 物品 id -> 數量（含 lingshi）
    sects: dict = field(default_factory=dict)       # 門派 id -> 聲望 -4..4
    treasures: dict = field(default_factory=dict)   # 法寶 id -> 祭煉階數
    gongfa: list = field(default_factory=list)

    @property
    def primary_element(self) -> str:
        return self.elements[0] if self.elements else ""

    def count(self, item: str) -> int:
        return self.inventory.get(item, 0)

    def add(self, item: str, n: int = 1):
        self.inventory[item] = self.count(item) + n

    def remove(self, item: str, n: int = 1) -> bool:
        if self.count(item) < n:
            return False
        self.inventory[item] -= n
        return True
    counters: dict = field(default_factory=dict)    # visit:<loc> / kill:<loc> / kill:total
    quest: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    dialogue: dict = field(default_factory=dict)   # 進行中的對話 {"id","node"}
