#!/usr/bin/env python3
"""將 data/*.json 注入 docs/design_doc.template.html，輸出 docs/design_doc.html。

用法：python tools/build_docs.py
單一資料來源：修改 data/*.json 後重新執行即可更新設計文件網頁。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TEMPLATE = ROOT / "docs" / "design_doc.template.html"
OUT = ROOT / "docs" / "design_doc.html"

FILES = ["realms", "regions", "sects", "characters", "techniques", "treasures", "story_arcs"]


def main() -> int:
    bundle = {}
    for name in FILES:
        path = DATA / f"{name}.json"
        with path.open(encoding="utf-8") as fh:
            bundle[name] = json.load(fh)
    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    # 避免 </script> 提前結束
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    marker = "/*__DATA__*/"
    if marker not in html:
        print("template 缺少 /*__DATA__*/ 標記", file=sys.stderr)
        return 1
    html = html.replace(marker, payload, 1)
    OUT.write_text(html, encoding="utf-8")
    print(f"寫入 {OUT} ({len(html)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
