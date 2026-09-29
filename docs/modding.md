# ChineseRim 模組擴充指南

ChineseRim 本身是一組 Skyrim SE 模組，擴充方式與擴充 Skyrim 完全相同。
本文說明三種掛接層次，由淺到深。

## 1. 純資料：丟一個 JSON

把檔案放到 `Data/SKSE/Plugins/ChineseRim/<類別>/`，遊戲啟動時 `CR_Registry` 自動合併。
`id` 相同者後載入覆蓋（會寫入 Papyrus log）。

| 資料夾 | 內容 | 範例欄位 |
|---|---|---|
| `techniques/` | 功法（`gongfa[]`）、法術（`spells[]`） | 見 `data/techniques.json` |
| `sects/` | 門派（`sects[]`） | 見 `data/sects.json` |
| `pills/` | 丹藥（`pills[]`） | 見 `data/treasures.json` |

功法的 Perk 樹仍需在你自己的 `.esp` 裡建立；JSON 用 `entryPerk` 指向入口 Perk：

```json
{ "gongfa": [{
  "id": "mymod_xuanyin_jue", "name": "玄陰訣", "element": "水", "minRealm": "foundation",
  "entryPerk": "__formData|MyMod.esp|0x000D65",
  "skyrim": { "perkTree": "MyMod_Tree_XuanYin", "baseSkill": "Destruction" }
}]}
```

## 2. 插件：依賴 ChineseRim.esm

在 Creation Kit 以 `ChineseRim.esm` 為 master 建立 `.esp`，即可直接使用：

- **Faction**：`CR_Fac_*`（門派）、`CR_Fac_XiuShi`（所有修士）、`CR_Fac_RealmTracker`（境界 Rank = order×20 + sub）
- **Keyword**：`CR_Kw_Elem_*`（五行/變異屬性）、`CR_Kw_Realm_*`（境界）、`CR_Kw_MoDao`、`CR_Kw_NoFly`、`CR_Kw_Treasure_Growable`
- **Race**：`CR_Race_LingGen_*`（靈根）
- **GlobalVariable**：`CR_GV_PlayerRealmOrder / Sub`（對話與任務條件）
- **Perk 樹**：`CR_Tree_*`；在 Actor Value Info 中掛到自訂技能

新門派範例流程：建立 Faction（父 Faction 設為 `CR_Fac_ZhengDao` 或 `CR_Fac_MoDaoLiuZong` 以繼承敵對）、駐地 Location、
一個 `*_DISTR.ini` 分派法術給成員、一個 JSON 讓門派出現在圖鑑。

## 3. 腳本：Papyrus API 與事件

```papyrus
; 讀境界
int realm = CR_API.GetRealm(Game.GetPlayer())   ; 0 凡人 … 5 化神

; 突破
bool ok = CR_API.TryBreakthrough(Game.GetPlayer(), CR_Pill_ZhuJiDan)

; 訂閱事件
RegisterForModEvent("CR_OnRealmChanged", "OnRealmChanged")
Event OnRealmChanged(Form akActor, int aiOrder, int aiSub, int aiOld)
EndEvent
```

| 事件 | 參數 |
|---|---|
| `CR_OnRealmChanged` | Form actor, int order, int sub, int oldOrder |
| `CR_OnBreakthrough` | Form actor, bool success, string realmId |
| `CR_OnSectRankChanged` | Form actor, int factionFormID, int newRank |
| `CR_OnTreasureRefined` | Form item, int grade |
| `CR_OnMoonFull` | int day |

DLL 提供的原生函式在 `CR_Native.psc`，呼叫前用 `SKSE.GetPluginVersion("ChineseRim") > 0` 檢查。

## 4. 相容性守則

1. 不刪除、不改名原版 Actor Value、Keyword、Skill、裝備 Slot、Race 骨架。
2. 不覆寫 `0_master.hkx`；動畫走 Nemesis/Pandora + OAR（飛行動畫條件變數 `bCR_Flying`）。
3. 所有新記錄使用你自己的前綴（不要用 `CR_`）。
4. 法術傷害走原版 Magic Effect，讓法術縮放類模組照常作用。
5. 境界數值以玩家等級 1–100 尺度壓縮（見 `data/realms.json` levelRange）。

## 5. 戰鬥模組相容矩陣（目標）

| 模組類型 | 狀態 | 備註 |
|---|---|---|
| MCO / ADXP、SkySA、Valhalla | 相容 | 飛行時自動停用近戰動畫集 |
| TK Dodge RE、Precision、True Directional Movement | 相容 | — |
| Ordinator / Adamant 等 Perk 大修 | 部分 | 原版 18 技能仍在，功法樹另外存在；平衡需自行調整 |
| Wildcat / Blade & Blunt | 相容 | 傷害倍率會疊加五行倍率 |
| Requiem 類全面大修 | 不建議 | 兩者都改升級曲線 |
| 追隨者框架（NFF、AFT） | 相容 | 銀月/南宮婉走原版追隨者 Faction |
| 生存模式 | 相容 | 築基後辟穀免疫飢餓（MCM 可關） |
