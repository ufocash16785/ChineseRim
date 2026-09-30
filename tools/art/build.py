#!/usr/bin/env python3
"""產生 chineserim/static/art/ 下的所有像素素材。用法：python -m tools.art.build （需 pillow）"""
import json
import pathlib
import sys

from PIL import Image

from . import beasts, humans, scenery
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
    "villager_f": dict(robe="#b98a5a", trim="#e8d8b0", sash="#8a5a3a", hair="#3a2a2a", hairstyle="long"),
    "villager_m": dict(robe="#8a7a5a", trim="#c8b88a", sash="#5a4a2a", hair="#3a2a2a", hairstyle="short"),
    "disciple": dict(robe="#8a3a2a", trim="#e8d0a0", sash="#3a2a2a", hair="#2b2233", hairstyle="topknot"),
    "lifeiyu": dict(robe="#6a7b8c", trim="#d8e0e8", sash="#3a4a5a", hair="#2b2233", hairstyle="ponytail"),
    "zhangtie": dict(robe="#7a6a4a", trim="#b8a878", sash="#4a3a2a", hair="#2b2233", hairstyle="short"),
    "mo": dict(robe="#6a8a5a", trim="#e0e0c0", sash="#4a5a3a", hair="#b0b0b0", beard="#c0c0c0", hairstyle="elder"),
    "li": dict(robe="#d8a82a", trim="#fff0b0", sash="#8a5a1a", hair="#d0d0d0", beard="#d8d8d8", hairstyle="elder"),
    "nangong": dict(robe="#f4f6fb", trim="#8ec5e8", sash="#6aa0d8", hair="#1e1a2a", hairstyle="long", accessory="pin"),
    "dayan": dict(robe="#d8c880", trim="#fff8d0", sash="#a08830", hair="#f0f0f0", beard="#f0f0f0", hairstyle="elder"),
    "villain": dict(robe="#3a2a4a", trim="#c0406a", sash="#1a1020", hair="#1a1020", hairstyle="ponytail"),
    "xuangu": dict(robe="#2a2030", trim="#a03030", sash="#6a1a1a", hair="#d0d0d0", beard="#d0d0d0", hairstyle="elder"),
    "mupei": dict(robe="#c0492b", trim="#f0d090", sash="#6a2a1a", hair="#3a2418", hairstyle="long", accessory="pin"),
    "lingyu": dict(robe="#7a6ad8", trim="#f0e0ff", sash="#4a3a9a", hair="#241a34", hairstyle="long", accessory="pin"),
    "yuzitong": dict(robe="#5a3a3a", trim="#a08a7a", sash="#2a1a1a", hair="#1a1414", hairstyle="topknot"),
    "merchant": dict(robe="#5a7a3a", trim="#e8d8a0", sash="#8a6a2a", hair="#3a2a2a", hairstyle="short", hat="#6a4a2a"),
    "boatman": dict(robe="#4a6a8a", trim="#a8c0d0", sash="#2a3a4a", hair="#3a3a3a", hairstyle="short", hat="#b89a5a"),
    "soldier": dict(robe="#7a8592", trim="#e0c060", sash="#4a5560", hair="#2b2233", hairstyle="short", hat="#5a6570"),
}

SPEAKERS = {
    "母親": "villager_f", "三叔": "villager_m", "執事": "disciple", "落雲宗執事": "disciple", "靈獸山弟子": "disciple",
    "聯盟使者": "disciple", "厲飛雨": "lifeiyu", "張鐵": "zhangtie", "墨大夫": "mo", "李化元": "li",
    "南宮婉": "nangong", "大衍神君": "dayan", "曲魂": "villain", "玄骨老祖": "xuangu", "慕沛靈": "mupei",
    "凌玉靈": "lingyu", "余子童": "yuzitong", "攤主": "merchant", "藥鋪掌櫃": "merchant", "掌櫃": "merchant", "船夫": "boatman",
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
    sheets = [human_sheet(dict(NPCS[i], sword=False), fly=False, rows=("idle", "walk")) for i in ids]
    im, starts = stack(sheets, humans.FW, humans.FH, 4)
    im.save(OUT / "npcs.png")
    manifest["npcs"] = {i: {"row": s} for i, s in zip(ids, starts)}
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
    fx = [(f"slash{t}", scenery.slash_frame(t).image(shade=False, outline=False)) for t in range(3)]
    fx += [(f"spark{t}", scenery.spark_frame(t).image(shade=False, outline=False)) for t in range(3)]
    for el, (m, d, l, a) in beasts.ELEMENT_PALETTES.items():
        for t in range(2):
            fx.append((f"orb_{el}_{t}", scenery.orb_frame(t, hexc(m), hexc(a)).image(shade=False, outline=False)))
    atlas, rects = pack_atlas(fx, 256)
    atlas.save(OUT / "fx.png")
    manifest["fx"] = {"rects": rects}

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("素材輸出到", OUT, sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    sys.exit(main())
