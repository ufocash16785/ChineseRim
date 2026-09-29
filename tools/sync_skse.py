#!/usr/bin/env python3
"""把 data/*.json 複製到 SKSE/Plugins/ChineseRim/（遊戲執行期讀取的位置），
並產生 config.json（DLL 讀取的五行倍率等設定）。

用法：python tools/sync_skse.py
"""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data"
DST = ROOT / "SKSE" / "Plugins" / "ChineseRim"

def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    for sub in ("techniques", "sects", "pills"):
        (DST / sub).mkdir(exist_ok=True)   # 第三方掛載資料夾
    n = 0
    for f in SRC.glob("*.json"):
        shutil.copy2(f, DST / f.name)
        n += 1
    (DST / "config.json").write_text(json.dumps({"elemAdvMult": 1.5, "elemDisMult": 0.75}, indent=2), encoding="utf-8")
    print(f"同步 {n} 個檔案 → {DST}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
