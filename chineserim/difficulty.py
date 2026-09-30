"""難度設定：遊戲開頭三選一（簡單／普通／困難）。所有倍率集中在這張表。"""

DIFFICULTY = {
    "easy": {
        "name": "簡單", "desc": "敵人較弱、獎勵豐厚、失敗懲罰輕，適合輕鬆體驗劇情。",
        "enemy_hp": 0.7, "enemy_atk": 0.6, "gold": 1.3, "chest": 1.3, "death_loss": 20,
        "start_lingshi": 800, "start_heal": 5, "start_mpill": 3, "breakthrough": 0.15, "flee": 0.15, "price": 0.8, "craft": 0.2,
    },
    "normal": {
        "name": "普通", "desc": "標準的修仙之路，需要適時補給與運用五行相剋。",
        "enemy_hp": 1.0, "enemy_atk": 1.0, "gold": 1.0, "chest": 1.0, "death_loss": 50,
        "start_lingshi": 500, "start_heal": 3, "start_mpill": 1, "breakthrough": 0.0, "flee": 0.0, "price": 1.0, "craft": 0.0,
    },
    "hard": {
        "name": "困難", "desc": "敵人強悍、資源吃緊、突破更難，失敗代價沉重。",
        "enemy_hp": 1.25, "enemy_atk": 1.25, "gold": 0.85, "chest": 0.85, "death_loss": 150,
        "start_lingshi": 300, "start_heal": 1, "start_mpill": 0, "breakthrough": -0.1, "flee": -0.15, "price": 1.25, "craft": -0.2,
    },
}
DEFAULT = "normal"


def get(name):
    return DIFFICULTY.get(name, DIFFICULTY[DEFAULT])
