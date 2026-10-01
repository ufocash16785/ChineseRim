#!/usr/bin/env python3
"""產生 chineserim/static/art/ 下的所有像素素材。用法：python -m tools.art.build （需 pillow）"""
import json
import pathlib
import sys

from PIL import Image

from . import beasts, humans, scenery, tiles
from .canvas import hexc

OUT = pathlib.Path(__file__).resolve().parents[2] / "chineserim" / "static" / "art"

# 主角服飾：依境界 0~5 換裝（凡人麻衣 → 化神金紫）
HERO_OUTFITS = [
    dict(robe="#9a7b55", trim="#d8c8a0", sash="#6a4a2a", hair="#2b2233", hairstyle="topknot"),   # 凡人
    dict(robe="#4a86b8", trim="#f2f0e6", sash="#c0392b", hair="#2b2233", hairstyle="topknot"),   # 練氣
    dict(robe="#3fa08a", trim="#ffe9a0", sash="#8a5a2b", hair="#2b2233", hairstyle="topknot"),   # 築基
    dict(robe="#f0f0f5", trim="#e0b84a", sash="#4a6ab8", hair="#2b2233", hairstyle="topknot"),   # 結丹
    dict(robe="#7a58c8", trim="#f0d878", sash="#e0e0f0", hair="#2b2233", hairstyle="ponytail"),  # 元嬰
    dict(robe="#2a2438", trim="#ffd35a", sash="#c8a030", hair="#e8e8f0", hairstyle="ponytail"),  # 化神
]

NPCS = {
    "villager_f": dict(robe="#b98a5a", trim="#e8d8b0", sash="#8a5a3a", hair="#3a2a2a", hairstyle="long", female=True, eye="#6a4a3a", shawl="#e8d8b0", accessory="bow", ornament="#e0a070"),
    "villager_m": dict(robe="#8a7a5a", trim="#c8b88a", sash="#5a4a2a", hair="#3a2a2a", hairstyle="short"),
    "disciple": dict(robe="#8a3a2a", trim="#e8d0a0", sash="#3a2a2a", hair="#2b2233", hairstyle="topknot"),
    "lifeiyu": dict(robe="#6a7b8c", trim="#d8e0e8", sash="#3a4a5a", hair="#2b2233", hairstyle="ponytail"),
    "zhangtie": dict(robe="#7a6a4a", trim="#b8a878", sash="#4a3a2a", hair="#2b2233", hairstyle="short"),
    "mo": dict(robe="#6a8a5a", trim="#e0e0c0", sash="#4a5a3a", hair="#b0b0b0", beard="#c0c0c0", hairstyle="elder"),
    "li": dict(robe="#d8a82a", trim="#fff0b0", sash="#8a5a1a", hair="#d0d0d0", beard="#d8d8d8", hairstyle="elder"),
    "nangong": dict(robe="#f4f6fb", trim="#8ec5e8", sash="#6aa0d8", hair="#1e1a2a", hairstyle="long", accessory="pin", female=True, eye="#4a7ac8", shawl="#bfe2ff"),
    "dayan": dict(robe="#d8c880", trim="#fff8d0", sash="#a08830", hair="#f0f0f0", beard="#f0f0f0", hairstyle="elder"),
    "villain": dict(robe="#3a2a4a", trim="#c0406a", sash="#1a1020", hair="#1a1020", hairstyle="ponytail"),
    "xuangu": dict(robe="#2a2030", trim="#a03030", sash="#6a1a1a", hair="#d0d0d0", beard="#d0d0d0", hairstyle="elder"),
    "mupei": dict(robe="#c0492b", trim="#f0d090", sash="#6a2a1a", hair="#3a2418", hairstyle="long", accessory="flower", female=True, eye="#8a4a2a", shawl="#f8d8a0", ornament="#ffb84a"),
    "lingyu": dict(robe="#7a6ad8", trim="#f0e0ff", sash="#4a3a9a", hair="#241a34", hairstyle="long", accessory="pin", female=True, eye="#8a4ac8", shawl="#e0d0ff"),
    "wangchan": dict(robe="#b8402a", trim="#f0c060", sash="#5a1a10", hair="#2a1414", hairstyle="short", hat="#7a2a1a"),
    "tianxing": dict(robe="#3a4a9a", trim="#e0e8ff", sash="#1a2258", hair="#dcdcf0", beard="#dcdcf0", hairstyle="elder"),
    "mozu": dict(robe="#2a1a2a", trim="#d03a1a", sash="#8a1a10", hair="#c02a1a", hairstyle="ponytail", hat="#3a2a3a"),
    "xinmo": dict(robe="#1a1a24", trim="#8a8ab0", sash="#4a4a6a", hair="#0e0e16", hairstyle="topknot"),
    "puppet": dict(robe="#9a6a3a", trim="#d8b070", sash="#5a3a1a", hair="#6a4a2a", hairstyle="short", hat="#7a5a2a"),
    "puppet_spirit": dict(robe="#6a5ad8", trim="#e0d8ff", sash="#3a2a9a", hair="#9a8af0", hairstyle="short", hat="#5a4ac8"),
    "puppet_iron": dict(robe="#8a929c", trim="#d0d8e0", sash="#4a525c", hair="#5a626c", hairstyle="short", hat="#6a727c"),
    "wanglin": dict(robe="#5a6a7a", trim="#c8d0d8", sash="#2a3440", hair="#1a1a24", hairstyle="topknot"),
    "limuwan": dict(robe="#eef2fa", trim="#9ec8f0", sash="#7aa8e0", hair="#221c2c", hairstyle="long", accessory="pin", female=True, eye="#5a8ad8", shawl="#d0e8ff", ornament="#a8d8ff"),
    "situnan": dict(robe="#7a8a5a", trim="#d8e0b8", sash="#4a5a2a", hair="#2b2233", hairstyle="short"),
    "tianyunzi": dict(robe="#4a5a9a", trim="#e0e8ff", sash="#2a3468", hair="#e0e0f0", beard="#e0e0f0", hairstyle="elder"),
    "xuezhan": dict(robe="#e8d8a0", trim="#c0a040", sash="#8a6a20", hair="#1a1414", hairstyle="ponytail"),
    "tiandao": dict(robe="#f4f0e0", trim="#ffd35a", sash="#fff0b0", hair="#f8f4e8", hairstyle="long"),
    "tashi": dict(robe="#9fb4c8", trim="#e8f4ff", sash="#5a6a80", hair="#e8f0f8", beard="#e8f0f8", hairstyle="elder", halo="#bfe8ff", sword=False),
    "tianfa": dict(robe="#34446a", trim="#d8e8ff", sash="#e0d060", hair="#f0f0ff", hairstyle="ponytail", hat="#9aa8c0", pauldron="#c8d0e0"),
    "mojie": dict(robe="#2a1220", trim="#e04020", sash="#801010", hair="#c02020", hairstyle="ponytail", horns="#4a1a1a", pauldron="#6a2020"),
    "dao_true": dict(robe="#fffdf2", trim="#ffd35a", sash="#ffe890", hair="#ffffff", hairstyle="long", halo="#ffe890", wings="#fff4c8", sword=False),
    "taiyi": dict(robe="#5a3a8a", trim="#f0d070", sash="#2a1a4a", hair="#e8e0f0", beard="#e8e0f0", hairstyle="elder", hat="#3a2a5a", sword=False),
    "zhu": dict(robe="#2a2a44", trim="#a890ff", sash="#6a58c8", hair="#d8d0ff", beard="#d8d0ff", hairstyle="elder", halo="#a890ff", sword=False),
    "yuzitong": dict(robe="#5a3a3a", trim="#a08a7a", sash="#2a1a1a", hair="#1a1414", hairstyle="topknot"),
    "merchant": dict(robe="#5a7a3a", trim="#e8d8a0", sash="#8a6a2a", hair="#3a2a2a", hairstyle="short", hat="#6a4a2a"),
    "boatman": dict(robe="#4a6a8a", trim="#a8c0d0", sash="#2a3a4a", hair="#3a3a3a", hairstyle="short", hat="#b89a5a"),
    "soldier": dict(robe="#7a8592", trim="#e0c060", sash="#4a5560", hair="#2b2233", hairstyle="short", hat="#5a6570"),
    # 新增：藥鋪掌櫃、奸商、道侶候選人
    "pharmacist": dict(robe="#e8e0c0", trim="#4aa070", sash="#2a6a4a", hair="#2a2a2a", beard="#2a2a2a", hairstyle="elder"),
    "shady": dict(robe="#4a3a2a", trim="#c8a040", sash="#2a1a10", hair="#1a1a1a", hairstyle="short", hat="#3a2a1a"),
    "dongxuaner": dict(robe="#fbe7a8", trim="#fff8e0", sash="#f08a4a", hair="#3a2a20", hairstyle="long", accessory="flower", female=True, eye="#a06a2a", shawl="#fff0c0", ornament="#ffb84a"),
    "mocaihuan": dict(robe="#a8d8b8", trim="#f0fff0", sash="#3a8a5a", hair="#2a2a2a", hairstyle="ponytail", accessory="bow", female=True, eye="#3a8a5a", shawl="#e8ffe0", ornament="#ffd0e0"),
    "chenqiaoqian": dict(robe="#f2a8b8", trim="#fff0f0", sash="#c0304a", hair="#3a2028", hairstyle="long", accessory="flower", female=True, eye="#a0406a", shawl="#ffe0e8", ornament="#ff3a6a"),
    "yuanyao": dict(robe="#b8d0f0", trim="#f0f6ff", sash="#5a7ac8", hair="#2a2a3a", hairstyle="long", accessory="pin", female=True, eye="#5a7ac8", shawl="#e0eeff"),
    "wenshier": dict(robe="#f8c898", trim="#fff4e0", sash="#c8683a", hair="#4a2a1a", hairstyle="ponytail", accessory="bow", female=True, eye="#c8683a", shawl="#ffe8c8", ornament="#ffd35a"),
    "ziling": dict(robe="#c8b0f0", trim="#f4ecff", sash="#7a4ac8", hair="#5a3a8a", hairstyle="long", accessory="flower", female=True, eye="#8a4ac8", shawl="#ecdcff", ornament="#e08aff"),
}

SPEAKERS = {
    "母親": "villager_f", "三叔": "villager_m", "執事": "disciple", "落雲宗執事": "disciple", "靈獸山弟子": "disciple",
    "聯盟使者": "disciple", "厲飛雨": "lifeiyu", "張鐵": "zhangtie", "墨大夫": "mo", "李化元": "li",
    "南宮婉": "nangong", "大衍神君": "dayan", "曲魂": "villain", "玄骨老祖": "xuangu", "慕沛靈": "mupei",
    "凌玉靈": "lingyu", "余子童": "yuzitong", "王林": "wanglin", "李慕婉": "limuwan", "司徒南": "situnan", "天運子": "tianyunzi", "薛戰": "xuezhan", "黑衣修士": "villain", "五行守衛": "puppet_iron", "天道化身": "tiandao", "珠中之聲": "zhu", "天罰使者": "tianfa", "天道本體": "dao_true", "塔靈": "tashi", "魔劫使": "mojie", "太一宗主": "taiyi", "王蟬": "wangchan", "天星雙聖": "tianxing", "魔族將領": "mozu", "心魔": "xinmo", "攤主": "merchant", "藥鋪掌櫃": "pharmacist", "掌櫃": "pharmacist", "奸商": "shady", "董萱兒": "dongxuaner", "墨彩環": "mocaihuan", "陳巧倩": "chenqiaoqian", "元瑤": "yuanyao", "文詩兒": "wenshier", "紫靈": "ziling", "船夫": "boatman",
    "天淵守軍": "soldier",
}


def human_sheet(cfg, fly=True, rows=None):
    p = humans.Pal(**cfg)
    anims = humans.frames(p, fly=fly)
    if rows:
        anims = [a for a in anims if a[0] in rows]
    out = []
    for name, poses in anims:
        out.append((name, [humans.draw_human(p, ps).image() for ps in poses]))
    for name, poses in humans.frames_dir(p):          # 俯視地圖用：正面 / 背面
        if rows is None or name in rows:
            out.append((name, [humans.draw_human_dir(p, ps).image() for ps in poses]))
    return out


def stack(sheets, fw, fh, cols):
    """sheets: list of list[(name, frames)]；垂直堆疊，回傳 (Image, [(起始 row)])。"""
    total = sum(len(s) for s in sheets)
    im = Image.new("RGBA", (cols * fw, total * fh), (0, 0, 0, 0))
    starts, r = [], 0
    for s in sheets:
        starts.append(r)
        for _, frames in s:
            for c, f in enumerate(frames):
                im.paste(f, (c * fw, r * fh))
            r += 1
    return im, starts


def pack_atlas(sprites, width=512, pad=1):
    x = y = rowh = 0
    place = {}
    for name, im in sprites:
        if x + im.width > width:
            x, y, rowh = 0, y + rowh + pad, 0
        place[name] = (x, y, im.width, im.height)
        x += im.width + pad
        rowh = max(rowh, im.height)
    atlas = Image.new("RGBA", (width, y + rowh), (0, 0, 0, 0))
    for name, im in sprites:
        atlas.paste(im, place[name][:2])
    return atlas, {k: list(v) for k, v in place.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"human": {"frameW": humans.FW, "frameH": humans.FH, "baseline": humans.BASE}}
    ANIM_NAMES = [n for n, _ in humans.frames(humans.Pal("#000000", "#000000", "#000000", "#000000"))]

    # 主角 6 套
    sheets = [human_sheet(c) for c in HERO_OUTFITS]
    im, starts = stack(sheets, humans.FW, humans.FH, 8)
    im.save(OUT / "heroes.png")
    manifest["heroes"] = {"outfitRows": starts, "rowsPerOutfit": len(sheets[0]),
                          "anims": {n: {"row": i, "n": len(f)} for i, (n, f) in enumerate(sheets[0])}}

    # NPC
    ids = list(NPCS)
    NPC_ROWS = ("idle", "walk", "idle_d", "walk_d", "idle_u", "walk_u")
    sheets = [human_sheet(dict(NPCS[i], sword=False), fly=False, rows=NPC_ROWS) for i in ids]
    im, starts = stack(sheets, humans.FW, humans.FH, 4)
    im.save(OUT / "npcs.png")
    manifest["npcs"] = {i: {"row": s} for i, s in zip(ids, starts)}
    manifest["npcAnims"] = {n: {"row": r, "n": len(f)} for r, (n, f) in enumerate(sheets[0])}
    manifest["speakers"] = SPEAKERS

    # 妖獸
    names = list(beasts.BEASTS)
    sheets = []
    for n in names:
        fn = beasts.BEASTS[n][0]
        sheets.append([(el, [fn(el, t).image() for t in range(4)]) for el in beasts.ELEMENTS])
    im, starts = stack(sheets, beasts.FW, beasts.FH, 4)
    im.save(OUT / "beasts.png")
    manifest["beasts"] = {"frameW": beasts.FW, "frameH": beasts.FH, "elements": beasts.ELEMENTS,
                          "kinds": {n: {"row": s, "name": beasts.BEASTS[n][1]} for n, s in zip(names, starts)}}

    # 場景與特效（每個生態區一份）
    manifest["biomes"] = {}
    for b, P in scenery.BIOMES.items():
        sp = [("house0", scenery.house(b, 0).image()), ("house1", scenery.house(b, 1).image()),
              ("pagoda", scenery.pagoda(b).image()), ("gate", scenery.sect_gate(b).image()), ("cave", scenery.cave(b).image()),
              ("tree", scenery.tree_round(b).image()), ("pine", scenery.pine(b).image()), ("bamboo", scenery.bamboo(b).image()),
              ("rock", scenery.rock(b).image()), ("lantern", scenery.lantern(b).image()),
              ("ground0", scenery.ground_tile(b, 0).image()), ("ground1", scenery.ground_tile(b, 1).image()),
              ("platform", scenery.platform(b).image())]
        sp += [(f"portal{t}", scenery.portal_frame(t).image()) for t in range(4)]
        atlas, rects = pack_atlas(sp)
        atlas.save(OUT / f"scene_{b}.png")
        manifest["biomes"][b] = {"rects": rects, "sky": P["sky"]}
    # 俯視地圖：地磚與物件
    manifest["tiles"], manifest["objects"] = {}, {}
    for b, P in scenery.BIOMES.items():
        tl = []
        for v in range(4): tl.append((f"grass{v}", tiles.grass(b, v)))
        for v in range(2): tl.append((f"dirt{v}", tiles.dirt(b, v)))
        for v in range(2): tl.append((f"path{v}", tiles.path(b, v)))
        for v in range(2): tl.append((f"sand{v}", tiles.sand(b, v)))
        for f in range(4): tl.append((f"water{f}", tiles.water(b, f)))
        for f in range(4): tl.append((f"sea{f}", tiles.water(b, f, True)))
        for n, fn in (("wood0", tiles.wood), ("court0", tiles.court), ("cave0", tiles.cave_floor), ("cavewall0", tiles.cave_wall), ("hedge0", tiles.hedge)):
            tl.append((n, fn(b, 0)))
        for v in range(3): tl.append((f"mountain{v}", tiles.mountain(b, v)))
        for v in range(3): tl.append((f"forest{v}", tiles.forest(b, v)))
        tl.append(("bridgeH", tiles.bridge(b, False))); tl.append(("bridgeV", tiles.bridge(b, True)))
        for m in range(16): tl.append((f"shore{m}", tiles.shore(b, m)))
        cols = 16
        atlas = Image.new("RGBA", (cols * 32, ((len(tl) + cols - 1) // cols) * 32), (0, 0, 0, 0))
        pos = {}
        for i, (n, cv) in enumerate(tl):
            x, y = (i % cols) * 32, (i // cols) * 32
            atlas.paste(cv.image(shade=False, outline=False), (x, y))
            pos[n] = [x, y]
        atlas.save(OUT / f"tiles_{b}.png")
        manifest["tiles"][b] = pos
        ob = [("house0", scenery.house(b, 0)), ("house1", scenery.house(b, 1)), ("pagoda", scenery.pagoda(b)), ("gate", scenery.sect_gate(b)),
              ("cave", scenery.cave(b)), ("tree", scenery.tree_round(b)), ("pine", scenery.pine(b)), ("bamboo", scenery.bamboo(b)),
              ("rock", scenery.rock(b)), ("lantern", scenery.lantern(b)), ("well", tiles.well(b)), ("stall", tiles.stall(b)),
              ("chest_c", tiles.chest(b, False)), ("chest_o", tiles.chest(b, True)), ("statue", tiles.statue(b)), ("sign", tiles.sign(b)),
              ("banner", tiles.banner(b)), ("tent", tiles.tent(b)), ("campfire0", tiles.campfire(b, 0)), ("campfire1", tiles.campfire(b, 1)),
              ("dock", tiles.dock(b)), ("crystal", tiles.crystal(b)), ("altar", tiles.altar(b)), ("tomb", tiles.tomb(b)),
              ("dummy", tiles.dummy(b)), ("bush", tiles.bush(b)), ("flowers", tiles.flowers(b)), ("boulder", tiles.boulder(b)),
              ("icon_town", tiles.icon_town(b)), ("icon_sect", tiles.icon_sect(b)), ("icon_cave", tiles.icon_cave(b)),
              ("icon_battle", tiles.icon_battle(b)), ("icon_camp", tiles.icon_camp(b)), ("icon_port", tiles.icon_port(b)),
              ("icon_ruin", tiles.icon_ruin(b)), ("icon_portal", tiles.icon_portal(b)),
              ("furnace", tiles.furnace(b)), ("plot0", tiles.plot(b, 0)), ("plot1", tiles.plot(b, 1)), ("plot2", tiles.plot(b, 2)), ("plot3", tiles.plot(b, 3)),
              ("thunder_pillar", tiles.thunder_pillar(b)), ("ruin_arch", tiles.ruin_arch(b)), ("scarecrow", tiles.scarecrow(b)), ("bed", tiles.bed(b)), ("board", tiles.board(b)), ("pharmacy", tiles.pharmacy(b)), ("icon_garden", tiles.icon_garden(b)), ("icon_hut", tiles.icon_hut(b))]
        atlas, rects = pack_atlas([(n, cv.image()) for n, cv in ob], 512)
        atlas.save(OUT / f"objects_{b}.png")
        manifest["objects"][b] = rects
    fx = [(f"slash{t}", scenery.slash_frame(t).image(shade=False, outline=False)) for t in range(3)]
    fx += [(f"spark{t}", scenery.spark_frame(t).image(shade=False, outline=False)) for t in range(3)]
    for el, (m, d, l, a) in beasts.ELEMENT_PALETTES.items():
        for t in range(2):
            fx.append((f"orb_{el}_{t}", scenery.orb_frame(t, hexc(m), hexc(a)).image(shade=False, outline=False)))
    atlas, rects = pack_atlas(fx, 256)
    atlas.save(OUT / "fx.png")
    manifest["fx"] = {"rects": rects}

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    from . import endings
    endings.main()
    print("素材輸出到", OUT, sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    sys.exit(main())
