"""俯視地圖產生器：大地圖（人界／靈界）與各地點內部地圖。決定性（同一資料 → 同一地圖）。

地圖格式（可直接轉 JSON 給前端）：
  {id, w, h, kind:"world"|"loc", biome, ground:[字串列], solid:[0/1 字串列], objects:[…], entities:[…], spawn:[x,y], …}
座標單位為「格」(tile，前端一格 32px)。"""
import heapq
import math
import random

from .explore import DEEP, DWELLING, GARDEN, SAFE, SECT, is_wild

# ---- 地形代碼 ----
# 大地圖：~ 深海  , 淺水  g 草  t 森林  m 山  s 沙  r 路  R 河  b/B 橋(橫/直)  d 泥地
# 地點內：g 草  d 泥  p 石路  c 庭院  o 木地板  w 水  k 洞穴地  W 洞壁  h 樹籬/圍牆  s 沙  e 出口墊
BLOCK_WORLD = set("~,tmR")
BLOCK_LOC = set("wWh")

# 物件：(顯示縮放, 足印寬(格), 足印高(格))；足印為圖底部、水平置中。圖檔原始像素尺寸見 tools/art。
OBJ = {
    "house0": (2, 3, 2), "house1": (2, 3, 2), "pagoda": (2, 3, 2), "gate": (2, 0, 0),
    "cave": (2, 3, 2), "tree": (2, 1, 1), "pine": (2, 1, 1), "bamboo": (2, 1, 1),
    "rock": (1, 1, 1), "lantern": (1, 1, 1), "well": (1, 1, 1), "stall": (2, 3, 1),
    "chest_c": (1, 1, 1), "chest_o": (1, 1, 1), "statue": (1, 1, 1), "sign": (1, 1, 1),
    "banner": (1, 1, 1), "tent": (2, 3, 2), "campfire0": (1, 1, 1), "dock": (1, 0, 0),
    "crystal": (1, 1, 1), "altar": (1, 2, 1), "tomb": (1, 1, 1), "dummy": (1, 1, 1),
    "bush": (1, 1, 1), "flowers": (1, 0, 0), "boulder": (1, 1, 1),
    "furnace": (1, 1, 1), "plot0": (1, 0, 0), "plot1": (1, 0, 0), "plot2": (1, 0, 0), "plot3": (1, 0, 0),
    "scarecrow": (1, 1, 1), "bed": (1, 2, 1),
}
OBJ_SCALE = {k: v[0] for k, v in OBJ.items()}

PROFILE_LOOT = {"rich": 2.2, "mixed": 1.0, "normal": 1.0, "trap": 0.6, "poor": 0.15}   # 妖獸戰利品倍率
LOC_SIZE = {"town": (30, 24), "sect": (34, 28), "wild": (36, 28), "deep": (36, 30), "garden": (32, 26), "dwelling": (22, 18)}


def loc_category(loc_type):
    if loc_type in GARDEN:
        return "garden"
    if loc_type in DWELLING:
        return "dwelling"
    if loc_type in DEEP:
        return "deep"
    if loc_type in SECT:
        return "sect"
    if loc_type in SAFE:
        return "town"
    return "wild"


# ============================ 雜訊 ============================
def _hash(x, y, seed):
    n = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def _vnoise(x, y, seed):
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(x0, y0, seed), _hash(x0 + 1, y0, seed)
    c, d = _hash(x0, y0 + 1, seed), _hash(x0 + 1, y0 + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def fbm(x, y, seed):
    return (_vnoise(x / 8, y / 8, seed) * .5 + _vnoise(x / 4, y / 4, seed + 1) * .3 + _vnoise(x / 2, y / 2, seed + 2) * .2)


def _seed_of(s):
    return sum((i + 1) * ord(c) for i, c in enumerate(s)) & 0xFFFF


# ============================ 通用工具 ============================
class Grid:
    def __init__(self, w, h, fill):
        self.w, self.h = w, h
        self.g = [[fill] * w for _ in range(h)]

    def inb(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        return self.g[y][x] if self.inb(x, y) else None

    def set(self, x, y, c):
        if self.inb(x, y):
            self.g[y][x] = c

    def rows(self):
        return ["".join(r) for r in self.g]

    def fill_rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)


def footprint(name, x, y):
    """物件 (x,y)=底部中心格；回傳其實心格集合。"""
    _, fw, fh = OBJ[name]
    if name == "gate":
        return {(x - 2, y), (x + 2, y)}
    cells = set()
    x0 = x - (fw - 1) // 2 if fw > 1 else x
    for dy in range(fh):
        for dx in range(fw):
            cells.add((x0 + dx, y - dy))
    return cells if fw and fh else set()


def bfs(solid, w, h, start):
    seen = {start}
    q = [start]
    for cx, cy in q:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not solid[ny][nx]:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def _solid_grid(ground, w, h, block, objects):
    s = [[1 if ground[y][x] in block else 0 for x in range(w)] for y in range(h)]
    for o in objects:
        for (cx, cy) in footprint(o["t"], o["x"], o["y"]):
            if 0 <= cx < w and 0 <= cy < h:
                s[cy][cx] = 1
    return s


# ============================ 大地圖 ============================
WORLD_SIZES = {"renjie": (176, 176), "lingjie": (110, 90)}
REGION_RADIUS = {"tiannan": 34, "mulan": 19, "dajin": 22, "luanxinghai": 27, "tianyuan": 34}
ICON = {"town": "icon_town", "sect": "icon_sect", "deep": "icon_cave", "garden": "icon_garden", "dwelling": "icon_hut"}
BIOME_OF = {"tiannan": "tiannan", "mulan": "mulan", "luanxinghai": "luanxinghai", "dajin": "dajin", "tianyuan": "tianyuan"}


def _wild_icon(loc):
    t = loc["type"]
    if "營" in t:
        return "icon_camp"
    if "戰" in t:
        return "icon_battle"
    if "海" in t or "岸" in t or "島" in t:
        return "icon_port" if "岸" in t else "icon_ruin"
    return "icon_ruin"


def _astar(cost, w, h, start, goal):
    open_ = [(0, start)]
    came, g = {start: None}, {start: 0}
    while open_:
        _, cur = heapq.heappop(open_)
        if cur == goal:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cur[0] + dx, cur[1] + dy)
            if not (0 <= n[0] < w and 0 <= n[1] < h):
                continue
            c = cost(n)
            if c is None:
                continue
            ng = g[cur] + c
            if n not in g or ng < g[n]:
                g[n] = ng
                came[n] = cur
                heapq.heappush(open_, (ng + abs(n[0] - goal[0]) + abs(n[1] - goal[1]), n))
    if goal not in came:
        return []
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = came[cur]
    return path[::-1]


def build_world(data, world_id="renjie"):
    W, H = WORLD_SIZES[world_id]
    world = next(w for w in data.regions if w["id"] == world_id)
    regions = world["regions"]
    seed = _seed_of("world:" + world_id)
    rng = random.Random(seed)

    centers = {}
    for g in regions:
        cx, cy = g["coords"]
        if world_id == "renjie":
            centers[g["id"]] = (12 + cx * 1.7, 10 + (100 - cy) * 1.6)
        else:
            centers[g["id"]] = (W / 2, H / 2)

    land = [[False] * W for _ in range(H)]
    fval = [[0.0] * W for _ in range(H)]
    zone = [[None] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            best, bz = -9, None
            for rid, (cx, cy) in centers.items():
                r = REGION_RADIUS[rid]
                v = 1 - math.hypot(x - cx, (y - cy) * 1.1) / r
                if v > best:
                    best, bz = v, rid
            f = best + .34 * (fbm(x, y, seed) - .5)
            fval[y][x] = f
            if f > .1:
                land[y][x] = True
                zone[y][x] = bz
    ground = Grid(W, H, "~")
    for y in range(H):
        for x in range(W):
            if land[y][x]:
                ground.set(x, y, "g")
            else:
                near = any(0 <= x + dx < W and 0 <= y + dy < H and land[y + dy][x + dx] for dx in range(-2, 3) for dy in range(-2, 3))
                ground.set(x, y, "," if near else "~")
    # 沙灘、山、森林
    for y in range(H):
        for x in range(W):
            if not land[y][x]:
                continue
            coast = fval[y][x] < .2
            n2, n3 = fbm(x + 300, y, seed + 7), fbm(x, y + 500, seed + 11)
            if coast:
                ground.set(x, y, "s")
            elif n2 > .66 and fval[y][x] > .3:
                ground.set(x, y, "m")
            elif n3 > .6 and fval[y][x] > .25:
                ground.set(x, y, "t")
            elif fbm(x, y + 900, seed + 13) > .7:
                ground.set(x, y, "d")
    # 界河（僅人界：天南與慕蘭之間）
    river_y = None
    if world_id == "renjie" and "tiannan" in centers and "mulan" in centers:
        river_y = int((centers["tiannan"][1] + centers["mulan"][1]) / 2 + 2)
        for x in range(int(centers["tiannan"][0] - 30), int(centers["tiannan"][0] + 26)):
            yy = river_y + int(2 * math.sin(x / 7.0))
            for dy in (0, 1):
                if ground.get(x, yy + dy) in ("g", "t", "m", "d", "s"):
                    ground.set(x, yy + dy, "R")

    # ---- 地點放置 ----
    ents, taken = [], []
    entrance = {}

    def free(x, y, region, margin=2):
        if not (3 <= x < W - 3 and 3 <= y < H - 3) or zone[y][x] != region:
            return False
        if ground.get(x, y) in ("~", ",", "R"):
            return False
        return all(ground.get(x + dx, y + dy) not in ("~", ",") for dx in range(-margin, margin + 1) for dy in range(-margin, margin + 1))

    special_done = set()
    for g in regions:
        rid = g["id"]
        cx, cy = centers[rid]
        locs = list(g["locations"])
        rng.shuffle(locs)
        # 特別位置
        pos = {}
        cand = [(x, y) for y in range(H) for x in range(W) if zone[y][x] == rid and free(x, y, rid, 1)]
        if rid == "tiannan" and world_id == "renjie":
            east = [(x, y) for (x, y) in cand if any(ground.get(x + dx, y) == "," for dx in range(2, 6))]
            if east:
                pos["wubian"] = max(east, key=lambda p: p[0] - abs(p[1] - cy) * .1)
            west = [p for p in cand if p[0] < cx]
            if west:
                pos["jixi"] = min(west, key=lambda p: p[0])
            if river_y is not None:
                mid = [p for p in cand if abs(p[1] - river_y) < 8 and abs(p[0] - cx) < 12]
                if mid:
                    pos["jihe"] = min(mid, key=lambda p: abs(p[1] - river_y))
        gap = max(6, min(10, int(.9 * math.sqrt(math.pi * (REGION_RADIUS[rid] * .85) ** 2 / max(1, len(locs))))))
        for loc in locs:
            if loc["id"] in pos:
                p = pos[loc["id"]]
            else:
                spots = [(x, y) for (x, y) in cand if all(math.hypot(x - tx, y - ty) >= gap for tx, ty in taken) and math.hypot(x - cx, y - cy) < REGION_RADIUS[rid] * .9]
                if not spots:
                    spots = [(x, y) for (x, y) in cand if all(math.hypot(x - tx, y - ty) >= gap - 2 for tx, ty in taken)]
                if not spots:
                    spots = [(x, y) for (x, y) in cand if all(math.hypot(x - tx, y - ty) >= 4 for tx, ty in taken)] or cand
                p = rng.choice(spots)
            taken.append(p)
            entrance[loc["id"]] = p
    # 清出入口周圍空地
    for lid, (x, y) in entrance.items():
        for dx in range(-1, 2):
            for dy in range(-1, 3):
                if ground.get(x + dx, y + dy) in ("t", "m", "R", ","):
                    ground.set(x + dx, y + dy, "g")
        ground.set(x, y, "d")

    # 入口周圍幾格一律歸屬該地點所在區域（避免在門口來回跨區）
    for lid, (x, y) in entrance.items():
        rid = next(g["id"] for g in regions if any(l["id"] == lid for l in g["locations"]))
        for dx in range(-4, 5):
            for dy in range(-4, 6):
                if 0 <= x + dx < W and 0 <= y + dy < H and land[y + dy][x + dx]:
                    zone[y + dy][x + dx] = rid

    # ---- 道路 ----
    def cost(p):
        c = ground.get(*p)
        return {"~": None, ",": None, "g": 1, "d": 1, "s": 1.2, "r": .4, "b": .5, "B": .5, "t": 3, "m": 8, "R": 6}.get(c, 2)

    def carve(a, b_):
        path = _astar(cost, W, H, a, b_)
        for i, (x, y) in enumerate(path):
            c = ground.get(x, y)
            if c == "R":
                nxt = path[min(i + 1, len(path) - 1)]
                ground.set(x, y, "B" if nxt[0] == x else "b")
            elif c not in ("b", "B"):
                ground.set(x, y, "r")
        return path

    by_region = {}
    for g in regions:
        by_region[g["id"]] = [l["id"] for l in g["locations"]]
    for rid, ids in by_region.items():
        if not ids:
            continue
        done = [ids[0]]
        for lid in ids[1:]:
            near = min(done, key=lambda o: math.hypot(entrance[o][0] - entrance[lid][0], entrance[o][1] - entrance[lid][1]))
            carve(entrance[lid], entrance[near])
            done.append(lid)
    rids = list(by_region)
    hubs = {rid: by_region[rid][0] for rid in rids if by_region[rid]}
    for i in range(len(rids) - 1):
        a, b_ = rids[i], rids[i + 1]
        if a in hubs and b_ in hubs:
            # 只連陸地相鄰的區域（有海隔開的由渡口連結）
            path = _astar(lambda p: None if ground.get(*p) in ("~", ",") else cost(p), W, H, entrance[hubs[a]], entrance[hubs[b_]])
            for j, (x, y) in enumerate(path):
                c = ground.get(x, y)
                if c == "R":
                    nxt = path[min(j + 1, len(path) - 1)]
                    ground.set(x, y, "B" if nxt[0] == x else "b")
                elif c not in ("b", "B"):
                    ground.set(x, y, "r")

    # ---- 渡口（人界：天南東岸 ↔ 亂星海西岸）----
    docks = {}
    if world_id == "renjie" and "wubian" in entrance and "luanxinghai" in centers:
        wx, wy = entrance["wubian"]
        cand = [(x, y) for y in range(H) for x in range(W) if zone[y][x] == "tiannan" and ground.get(x, y) in ("s", "g", "d", "r")
                and any(ground.get(x + dx, y) == "," for dx in (1, 2))]
        docks["tiannan"] = min(cand, key=lambda p: math.hypot(p[0] - wx, p[1] - wy)) if cand else (wx + 1, wy)
        lc = [(x, y) for y in range(H) for x in range(W) if zone[y][x] == "luanxinghai" and ground.get(x, y) in ("s", "g", "d", "r")
              and any(ground.get(x + dx, y) == "," for dx in (-1, -2))]
        cxl, cyl = centers["luanxinghai"]
        docks["luanxinghai"] = min(lc, key=lambda p: p[0] + abs(p[1] - cyl) * .3) if lc else (int(cxl) - 12, int(cyl))
        for rid, (x, y) in docks.items():
            ground.set(x, y, "s")
            near = min(by_region[rid], key=lambda l: math.hypot(entrance[l][0] - x, entrance[l][1] - y))
            carve((x, y), entrance[near])

    # ---- 起點與連通性保證 ----
    start_loc = "qingniu" if "qingniu" in entrance else next(iter(entrance))
    sx, sy = entrance[start_loc]
    spawn = (sx, sy + 2)
    ground.set(*spawn, "r" if ground.get(*spawn) in ("t", "m", "R", ",", "~") else ground.get(*spawn))

    def solid_now():
        return [[1 if ground.get(x, y) in BLOCK_WORLD else 0 for x in range(W)] for y in range(H)]

    targets = [(p[0], p[1] + 1) for p in entrance.values()]
    for rid, dk in docks.items():
        pass
    reach = bfs(solid_now(), W, H, spawn)
    same_land = [t for t in targets if t not in reach]
    dock_first = docks.get("luanxinghai")
    for t in same_land:
        # 只修補「同一片大陸」內因地形阻擋而斷開的點；跨海的區域（亂星海）由渡口連結
        z = zone[t[1]][t[0]] if 0 <= t[1] < H else None
        if z == "luanxinghai" and world_id == "renjie":
            continue
        path = _astar(lambda p: None if ground.get(*p) in ("~", ",") else 1, W, H, t, spawn)
        for (x, y) in path:
            if ground.get(x, y) in ("t", "m", "R"):
                ground.set(x, y, "b" if ground.get(x, y) == "R" else "r")
    # 亂星海內部連通（以島內最近的地點為起點）
    if world_id == "renjie" and docks.get("luanxinghai"):
        d2 = docks["luanxinghai"]
        r2 = bfs(solid_now(), W, H, d2)
        for lid in by_region.get("luanxinghai", []):
            t = (entrance[lid][0], entrance[lid][1] + 1)
            if t not in r2:
                path = _astar(lambda p: None if ground.get(*p) in ("~", ",") else 1, W, H, t, d2)
                for (x, y) in path:
                    if ground.get(x, y) in ("t", "m", "R"):
                        ground.set(x, y, "b" if ground.get(x, y) == "R" else "r")
                r2 = bfs(solid_now(), W, H, d2)

    # ---- 實體 ----
    entities = []
    loc_index = {l["id"]: (l, g["id"]) for g in regions for l in g["locations"]}
    for lid, (x, y) in entrance.items():
        loc, rid = loc_index[lid]
        cat = loc_category(loc["type"])
        icon = ICON.get(cat) or _wild_icon(loc)
        entities.append({"id": "enter:" + lid, "k": "enter", "loc": lid, "name": loc["name"].split("（")[0], "icon": icon, "x": x, "y": y, "region": rid, "type": loc["type"]})
    for rid, (x, y) in docks.items():
        entities.append({"id": "dock:" + rid, "k": "dock", "region": rid, "x": x, "y": y, "name": "渡口"})
    solid = _solid_grid(ground.rows(), W, H, BLOCK_WORLD, [])
    zones_rows = ["".join(str(list(centers).index(zone[y][x])) if zone[y][x] else "." for x in range(W)) for y in range(H)]
    return {
        "id": f"world:{world_id}", "kind": "world", "w": W, "h": H, "biome": "tiannan" if world_id == "renjie" else "tianyuan",
        "ground": ground.rows(), "solid": ["".join(map(str, r)) for r in solid], "objects": [], "entities": entities,
        "spawn": list(spawn), "zones": zones_rows, "zoneIds": list(centers), "docks": {k: list(v) for k, v in docks.items()},
        "start": start_loc, "centers": {k: [round(v[0], 1), round(v[1], 1)] for k, v in centers.items()},
    }


# ============================ 地點內部地圖 ============================
FLAVOR = {  # 野外地點的風味：地面、額外物件
    "山": "mountain", "山脈": "mountain", "荒野": "desert", "海岸": "coast", "海域": "sea", "島": "island",
    "戰場": "battle", "戰區": "battle", "營地": "camp", "地標": "river", "妖修聚地": "forest", "異族領地": "forest",
}


class LocBuilder:
    def __init__(self, data, region_id, loc):
        self.data, self.region, self.loc = data, region_id, loc
        self.cat = loc_category(loc["type"])
        self.W, self.H = LOC_SIZE[self.cat]
        self.rng = random.Random(_seed_of("loc:" + loc["id"]))
        self.grid = Grid(self.W, self.H, "g")
        self.objects, self.entities = [], []
        self.occ = set()             # 已被物件或設計占用的格（含緩衝）
        self.n = 0
        self.profile = loc.get("profile", "normal")

    # ---- 工具 ----
    def eid(self, prefix):
        self.n += 1
        return f"{prefix}{self.n}"

    def solid_at(self, x, y):
        return self.grid.get(x, y) in BLOCK_LOC or (x, y) in self._solid_cells

    @property
    def _solid_cells(self):
        cells = set()
        for o in self.objects:
            cells |= footprint(o["t"], o["x"], o["y"])
        return cells

    def place(self, name, x, y, margin=1, force=False):
        cells = footprint(name, x, y)
        pad = {(cx + dx, cy + dy) for cx, cy in cells for dx in range(-margin, margin + 1) for dy in range(-margin, margin + 1)}
        if not force and (pad & self.occ or any(self.grid.get(cx, cy) in BLOCK_LOC or not self.grid.inb(cx, cy) for cx, cy in cells)):
            return False
        if not force and not (1 <= x < self.W - 1 and 1 <= y < self.H - 1):
            return False
        self.occ |= pad
        self.objects.append({"t": name, "x": x, "y": y})
        return True

    def reserve(self, x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.occ.add((x, y))

    def border(self, c="h"):
        for x in range(self.W):
            self.grid.set(x, 0, c)
            self.grid.set(x, self.H - 1, c)
        for y in range(self.H):
            self.grid.set(0, y, c)
            self.grid.set(self.W - 1, y, c)

    def exit_gap(self, ground_c="e", width=3, floor="p"):
        cx = self.W // 2
        x0 = cx - width // 2
        for x in range(x0, x0 + width):
            self.grid.set(x, self.H - 1, ground_c)
            self.grid.set(x, self.H - 2, floor)
        self.exit_cells = [(x, self.H - 1) for x in range(x0, x0 + width)]
        self.spawn = (cx, self.H - 3)
        self.reserve(x0 - 1, self.H - 5, x0 + width, self.H - 1)

    def scatter(self, names, count, margin=1, tries=400, avoid_spawn=4):
        placed = 0
        for _ in range(tries):
            if placed >= count:
                break
            x, y = self.rng.randrange(2, self.W - 2), self.rng.randrange(3, self.H - 2)
            if math.hypot(x - self.spawn[0], y - self.spawn[1]) < avoid_spawn:
                continue
            if self.place(self.rng.choice(names), x, y, margin):
                placed += 1
        return placed

    def free_cells(self, min_dist_spawn=0):
        s = self._solid_cells
        return [(x, y) for y in range(2, self.H - 2) for x in range(2, self.W - 2)
                if self.grid.get(x, y) not in BLOCK_LOC and (x, y) not in s and (x, y) not in self.occ
                and math.hypot(x - self.spawn[0], y - self.spawn[1]) >= min_dist_spawn]

    def path_line(self, x0, y0, x1, y1, c="p", w=1, thru=False):
        x, y = x0, y0
        while (x, y) != (x1, y1):
            for dx in range(w):
                for dy in range(w):
                    if thru or self.grid.get(x + dx, y + dy) not in ("h", "W", "e", "w"):
                        self.grid.set(x + dx, y + dy, c)
            if x != x1 and (abs(x1 - x) >= abs(y1 - y) or y == y1):
                x += 1 if x1 > x else -1
            elif y != y1:
                y += 1 if y1 > y else -1
        self.grid.set(x1, y1, c)

    def add_enemies(self, n, deep=False, min_dist=9):
        kinds = ["wolf", "spider", "bear", "snake", "python", "ape", "bat"]
        els = ["金", "木", "水", "火", "土", "雷", "冰", "風"]
        cells = self.free_cells(min_dist)
        self.rng.shuffle(cells)
        chosen = []
        for c in cells:
            if all(math.hypot(c[0] - o[0], c[1] - o[1]) >= 4 for o in chosen):
                chosen.append(c)
            if len(chosen) >= n:
                break
        for i, (x, y) in enumerate(chosen):
            self.entities.append({"id": f"m{i}", "k": "enemy", "kind": self.rng.choice(kinds), "el": self.rng.choice(els), "x": x, "y": y, "r": 3, "deep": deep,
                                  "loot": PROFILE_LOOT.get(self.profile, 1.0)})

    def add_chests(self, n, min_dist=8):
        cells = self.free_cells(min_dist)
        self.rng.shuffle(cells)
        placed = []
        for (x, y) in cells:
            if len(placed) >= n:
                break
            if all(math.hypot(x - a, y - b) >= 6 for a, b in placed) and self.place("chest_c", x, y, 1):
                placed.append((x, y))
                self.entities.append({"id": f"c{len(placed)}", "k": "chest", "x": x, "y": y, "loot": self.chest_loot()})

    def chest_loot(self):
        p, r = self.profile, self.rng
        if p == "rich":
            return "rich"
        if p == "poor":
            return "empty" if r.random() < .75 else "normal"
        if p == "trap":
            return "mimic" if r.random() < .6 else "normal"
        if p == "mixed":
            return r.choice(["normal", "rich", "empty", "mimic"])
        return "normal"

    def add_npc(self, role, name, x, y, wander=True):
        self.entities.append({"id": self.eid("n"), "k": "npc", "role": role, "name": name, "npc": role_sprite(role, self.rng), "x": x, "y": y, "wander": wander})

    # ---- 版型 ----
    def build(self):
        getattr(self, "_" + self.cat)()
        # 入口告示牌
        sx, sy = self.spawn
        for dx in (-3, 3, -4, 4):
            if self.place("sign", sx + dx, sy - 1, 0):
                self.entities.append({"id": "sign", "k": "sign", "x": sx + dx, "y": sy - 1, "text": f"【{self.loc['name'].split('（')[0]}】{self.loc.get('note', '')}"})
                break
        ground = self.grid.rows()
        solid = _solid_grid(ground, self.W, self.H, BLOCK_LOC, self.objects)
        # 保證：出口、出生點、任務 NPC 位置、實體皆連通
        reach = bfs(solid, self.W, self.H, self.spawn)
        self.entities = [e for e in self.entities if e["k"] not in ("enemy", "npc", "plot") or (e["x"], e["y"]) in reach]
        # 寶箱／告示／假人本身是實心，需其相鄰格可達
        def touch(e):
            return any((e["x"] + dx, e["y"] + dy) in reach for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        self.entities = [e for e in self.entities if e["k"] not in ("chest", "sign", "dummy", "portal", "altar", "furnace", "bed") or touch(e)]
        self.objects = [o for o in self.objects if o["t"] != "chest_c" or any(e["k"] == "chest" and (e["x"], e["y"]) == (o["x"], o["y"]) for e in self.entities)]
        solid = _solid_grid(ground, self.W, self.H, BLOCK_LOC, self.objects)
        npc_spot = getattr(self, "npc_spot", None)
        if not npc_spot or (npc_spot not in bfs(solid, self.W, self.H, self.spawn)):
            npc_spot = min(bfs(solid, self.W, self.H, self.spawn), key=lambda c: math.hypot(c[0] - self.W / 2, c[1] - self.H * .4))
        return {
            "id": "loc:" + self.loc["id"], "kind": "loc", "objScale": OBJ_SCALE, "w": self.W, "h": self.H, "biome": self.region, "cat": self.cat,
            "name": self.loc["name"].split("（")[0], "type": self.loc["type"], "ground": ground,
            "solid": ["".join(map(str, r)) for r in solid], "objects": self.objects, "entities": self.entities,
            "spawn": list(self.spawn), "exit": [list(c) for c in self.exit_cells], "npcSpot": list(npc_spot),
        }

    def _town(self):
        W, H, R = self.W, self.H, self.rng
        self.border("h")
        self.exit_gap()
        cx = W // 2
        mid = 10
        self.path_line(cx, H - 2, cx, mid, "p", 2)
        self.path_line(3, mid, W - 4, mid, "p", 2)
        self.grid.fill_rect(cx - 3, mid - 2, cx + 3, mid + 3, "c")
        self.reserve(2, mid - 1, W - 3, mid + 2)
        self.reserve(cx - 1, mid, cx + 1, H - 1)
        self.reserve(cx - 4, mid - 3, cx + 4, mid + 4)
        self.place("well", cx, mid + 1, 0, force=True)
        for x in range(4, W - 6, 6):
            self.place(R.choice(["house0", "house1"]), x + 1, mid - 3, 1)
            self.place(R.choice(["house0", "house1"]), x + 1, mid + 6, 1)
        self.place("stall", cx - 6, mid + 3, 1)
        self.place("stall", cx + 6, mid + 3, 1)
        self.place("lantern", cx - 3, mid + 3, 0)
        self.place("lantern", cx + 3, mid + 3, 0)
        self.scatter(["tree", "bush", "flowers"], 12)
        self.npc_spot = (cx + 3, mid + 4) if (cx + 3, mid + 4) not in self._solid_cells else (cx - 2, mid + 4)
        self.add_npc("inn", "旅店老闆", cx - 4, mid + 4)
        self.add_npc("shop", "藥販", cx + 5, mid + 4)
        self.add_npc("villager", "村民", R.randrange(4, W - 4), mid - 1)
        self.add_npc("villager", "行商", R.randrange(4, W - 4), mid + 1)
        self.add_npc("guard", "守衛", cx + 3, H - 4, wander=False)

    def _sect(self):
        W, H, R = self.W, self.H, self.rng
        self.border("h")
        self.exit_gap(width=4)
        cx = W // 2
        self.grid.fill_rect(cx - 6, 5, cx + 6, H - 3, "c")
        self.grid.fill_rect(3, H - 8, 12, H - 3, "d")
        self.path_line(cx, H - 2, cx, 8, "p", 2)
        self.reserve(cx - 7, 3, cx + 7, H - 1)
        self.place("gate", cx, H - 2, 0, force=True)
        self.place("pagoda", cx, 8, 0, force=True)
        self.place("house1", cx - 10, 12, 1)
        self.place("house0", cx + 10, 12, 1)
        self.place("house1", cx - 10, 18, 1)
        self.place("house0", cx + 10, 18, 1)
        for i, x in enumerate((cx - 4, cx + 4)):
            self.place("lantern", x, 12, 0)
            self.place("lantern", x, 18, 0)
        # 練功場
        for i in range(3):
            self.place("dummy", 4 + i * 3, H - 6, 0, force=True)
            self.entities.append({"id": f"d{i}", "k": "dummy", "x": 4 + i * 3, "y": H - 6})
        # 池塘
        self.grid.fill_rect(W - 9, H - 9, W - 4, H - 4, "w")
        self.reserve(W - 10, H - 10, W - 3, H - 3)
        self.scatter(["tree", "bush", "flowers", "statue"], 10)
        self.npc_spot = (cx, 11)
        self.add_npc("elder", "長老", cx + 2, 10, wander=False)
        for i in range(3):
            self.add_npc("disciple", "弟子", R.randrange(cx - 5, cx + 5), R.randrange(13, H - 7))
        self.add_npc("guard", "守門弟子", cx - 4, H - 4, wander=False)

    def _wild(self):
        W, H, R = self.W, self.H, self.rng
        flavor = FLAVOR.get(self.loc["type"], "forest")
        base = {"desert": "s", "coast": "s", "sea": "s", "island": "s", "mountain": "d", "battle": "d", "camp": "g", "river": "g", "forest": "g"}[flavor]
        self.grid = Grid(W, H, base)
        self.border("h")
        self.exit_gap(floor="d")
        cx = W // 2
        self.path_line(cx, H - 2, cx, H - 8, "d", 2)
        self.path_line(cx, H - 8, R.randrange(8, W - 8), 6, "d", 1)
        if flavor in ("coast", "sea", "island"):
            self.grid.fill_rect(1, 1, W - 2, 6, "w")
            for x in range(1, W - 1):
                self.grid.set(x, 7, "s")
        if flavor == "river":
            for x in range(1, W - 1):
                for dy in range(2):
                    self.grid.set(x, 12 + dy + int(2 * math.sin(x / 4)), "w")
            self.path_line(cx, 13, cx, 14, "d", 3)
            for y in range(11, 18):
                self.grid.set(cx, y, "d")
                self.grid.set(cx + 1, y, "d")
        for _ in range(R.randrange(1, 3)):   # 小池
            px, py = R.randrange(4, W - 8), R.randrange(8, H - 10)
            self.grid.fill_rect(px, py, px + R.randrange(3, 6), py + R.randrange(2, 4), "w")
        self.reserve(cx - 2, H - 9, cx + 2, H - 1)
        dens = {"forest": 26, "mountain": 10, "desert": 6, "coast": 8, "sea": 4, "island": 12, "battle": 5, "camp": 8, "river": 12}[flavor]
        trees = {"desert": ["rock", "boulder", "bush"], "mountain": ["boulder", "rock", "pine"], "coast": ["rock", "bush"], "sea": ["rock"],
                 "island": ["tree", "rock", "bush"], "battle": ["tomb", "rock", "banner"], "camp": ["tree", "pine", "bush"],
                 "river": ["tree", "bush", "rock"], "forest": ["tree", "pine", "bamboo", "bush"]}[flavor]
        self.scatter(trees, dens, 1)
        if flavor == "camp":
            self.place("tent", W // 2 - 8, 8, 1)
            self.place("tent", W // 2 + 8, 8, 1)
            self.place("campfire0", W // 2, 10, 1)
        if flavor == "battle":
            self.scatter(["banner", "tomb"], 5, 1)
        self.scatter(["flowers"], 6, 0)
        self.npc_spot = (cx, H - 8)
        self.add_enemies(5, min_dist=9)
        self.add_chests(2 + (self.profile == "rich"))
        if self.loc["id"] == "jixi":         # 極西之地：空間節點
            self.place("crystal", 6, 5, 1)
            self.entities.append({"id": "portal", "k": "portal", "x": 6, "y": 5, "name": "空間節點", "to": "tianyuan"})

    def _deep(self):
        W, H, R = self.W, self.H, self.rng
        self.grid = Grid(W, H, "W")
        rooms = []
        cols, rows = 3, 3
        cw, ch = (W - 2) // cols, (H - 2) // rows
        for r in range(rows):
            for c in range(cols):
                rw, rh = R.randrange(6, cw - 1), R.randrange(5, ch - 1)
                x0 = 1 + c * cw + R.randrange(0, cw - rw)
                y0 = 1 + r * ch + R.randrange(0, ch - rh)
                rooms.append((c, r, x0, y0, rw, rh))
        for (_, _, x0, y0, rw, rh) in rooms:
            self.grid.fill_rect(x0, y0, x0 + rw - 1, y0 + rh - 1, "k")
        # 依序連接（蛇形）：保證連通
        order = sorted(rooms, key=lambda r: (r[1] if r[1] % 2 == 0 else r[1], r[0] if r[1] % 2 == 0 else -r[0]))
        order = sorted(rooms, key=lambda r: (-r[1], r[0] if (rows - 1 - r[1]) % 2 == 0 else -r[0]))
        for a, b in zip(order, order[1:]):
            ax, ay = a[2] + a[4] // 2, a[3] + a[5] // 2
            bx, by = b[2] + b[4] // 2, b[3] + b[5] // 2
            self.path_line(ax, ay, bx, by, "k", 2, thru=True)
        start = order[0]
        sx, sy = start[2] + start[4] // 2, start[3] + start[5] // 2
        # 出口：入口房間正下方直通到底邊
        self.path_line(sx, sy, sx, H - 2, "k", 2, thru=True)
        self.grid.set(sx, H - 1, "e")
        self.grid.set(sx + 1, H - 1, "e")
        self.exit_cells = [(sx, H - 1), (sx + 1, H - 1)]
        self.spawn = (sx, H - 3)
        self.reserve(sx - 2, sy - 2, sx + 3, H - 1)
        boss = order[-1]
        bx, by = boss[2] + boss[4] // 2, boss[3] + boss[5] // 2
        self.place("altar", bx, by, 1, force=True)
        self.entities.append({"id": "altar", "k": "altar", "x": bx, "y": by, "name": "祭壇"})
        self.scatter(["crystal", "boulder", "tomb"], 16, 1)
        self.npc_spot = (sx, sy)
        self.add_enemies(6, deep=True, min_dist=7)
        self.add_chests(3 + (self.profile == "rich"), min_dist=6)


ROLE_SPRITES = {
    "inn": ["villager_m"], "shop": ["merchant"], "villager": ["villager_m", "villager_f"], "guard": ["soldier"],
    "elder": ["li", "mo"], "disciple": ["disciple", "lifeiyu", "zhangtie"],
}


def role_sprite(role, rng):
    return rng.choice(ROLE_SPRITES.get(role, ["villager_m"]))


def build_location(data, loc_id):
    for w in data.regions:
        for g in w["regions"]:
            for loc in g["locations"]:
                if loc["id"] == loc_id:
                    return LocBuilder(data, g["id"], loc).build()
    raise KeyError(loc_id)


# ---- 藥園 / 洞府 ----
def _garden(self):
    W, H, R = self.W, self.H, self.rng
    self.border("h")
    self.exit_gap(width=3, floor="d")
    cx = W // 2
    self.path_line(cx, H - 2, cx, 9, "d", 2)
    self.path_line(4, 9, W - 5, 9, "d", 2)
    self.reserve(cx - 1, 8, cx + 1, H - 1)
    self.reserve(2, 8, W - 3, 10)
    # 房子（可歇息）
    self.place("house0", 6, 6, 0, force=True)
    self.entities.append({"id": "bed", "k": "bed", "x": 6, "y": 7, "name": "小屋"})
    self.reserve(3, 3, 9, 8)
    # 煉丹爐
    self.place("furnace", W - 7, 6, 0, force=True)
    self.entities.append({"id": "furnace", "k": "furnace", "x": W - 7, "y": 6, "name": "煉丹爐"})
    self.reserve(W - 9, 4, W - 5, 8)
    self.place("well", cx + 4, 6, 1)
    self.place("scarecrow", cx - 5, 15, 1)
    # 藥田：3 排 × 4 欄
    n = 0
    for row, y in enumerate((13, 16, 19)):
        for col, x in enumerate((8, 12, 16, 20)):
            if x >= W - 3:
                continue
            self.entities.append({"id": f"p{n}", "k": "plot", "x": x, "y": y})
            self.grid.fill_rect(x - 1, y - 1, x + 1, y + 1, "d") if False else None
            self.reserve(x, y, x, y)
            n += 1
    self.scatter(["flowers", "bush", "tree"], 8, 1)
    self.npc_spot = (cx + 2, 11)
    self.add_npc("farmer", "藥農", cx + 3, 11)
    self.add_npc("villager", "採藥人", R.randrange(6, W - 6), 22)


def _dwelling(self):
    W, H = self.W, self.H
    self.grid = Grid(W, H, "o")
    for x in range(W):
        self.grid.set(x, 0, "W")
    for y in range(H):
        self.grid.set(0, y, "W")
        self.grid.set(W - 1, y, "W")
    for x in range(W):
        self.grid.set(x, H - 1, "W")
    self.exit_gap(width=2, floor="o")
    cx = W // 2
    self.place("bed", 5, 4, 0, force=True)
    self.entities.append({"id": "bed", "k": "bed", "x": 5, "y": 5, "name": "石床"})
    self.place("altar", cx, 3, 0, force=True)
    self.entities.append({"id": "altar", "k": "altar", "x": cx, "y": 3, "name": "蒲團"})
    self.place("furnace", W - 5, 4, 0, force=True)
    self.entities.append({"id": "furnace", "k": "furnace", "x": W - 5, "y": 4, "name": "煉丹爐"})
    self.place("lantern", 3, 8, 0)
    self.place("lantern", W - 4, 8, 0)
    self.npc_spot = (cx, 8)


LocBuilder._garden = _garden
LocBuilder._dwelling = _dwelling
ROLE_SPRITES["farmer"] = ["villager_m", "merchant"]
