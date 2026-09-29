# 地圖建置指南（Creation Kit）

## Worldspace 規劃

| Worldspace | 插件 | 尺寸（Cell） | 建置方式 |
|---|---|---|---|
| `CR_TianNan` 天南 | ChineseRim_TianNan.esp | 128×128（與天際省相當） | 高度圖匯入（TESAnnwyn / CK Heightmap Editor）→ 手工修整 |
| `CR_MuLan` 慕蘭草原 | ChineseRim_TianNan.esp | 64×64 | 高度圖，大面積草地 LOD |
| `CR_LuanXingHai` 亂星海 | ChineseRim_LuanXingHai.esp | 96×96，海面為主 | 島嶼為 Location，船隻快速旅行 |
| `CR_DaJin` 大晉 | ChineseRim_DaJin.esp | 初版 48×48 節點 | 州府、落雲宗、昆吾山；其他以傳送陣連結 |
| `CR_TianYuan` 天淵（DLC） | ChineseRim_LingJie.esp | 64×64 | 天淵城為巨型城市 Worldspace |
| 七玄門/彩霞山 | ChineseRim_TianNan.esp | 天南內的子區域 | 垂直切片先做這裡（10×10） |

## 每個地點的最小需求

1. `Location` 記錄（`CR_Loc_*`），Parent 指向地區 Location（`CR_Loc_TianNan` 等）。
2. `Encounter Zone`，Min/Max Level 取自 `data/story_arcs.json` 對應卷的 levelRange。
3. Map Marker（門派用宗門圖示、坊市用市集圖示、秘境用洞窟圖示）。
4. 至少一個 `CR_Fac_*` 擁有者 Faction（門派駐地），用於盜竊/入侵判定。

## 門派駐地範本

- 山門（大門 + 護山陣法 Activator，非門人觸發警戒）
- 大殿（掌門、任務發布、對話）
- 弟子居所（可租用/獲贈洞府 = 玩家家園）
- 藏經閣（功法典籍 Book，依 Faction Rank 解鎖）
- 丹房 / 煉器房（丹爐、煉器台 = 改名的 Alchemy/Enchanting/Smithing 工作台）
- 靈藥園（Ingredient 生長點，靈液可催熟）
- 傳送陣（Activator，連結其他門派/坊市）

## 坊市範本

商人（法器、丹藥、材料、符籙、靈獸）、拍賣會（定期 Quest，Radiant 產生拍品）、
攤位租用（玩家販售，走原版商人庫存）、黑市（魔道物品）。

## 資產策略

- 建築：中式木構、飛簷、道觀、亭台、石階；先以模組化套件（Modular Set）建 12 種基礎件。
- 自然：竹林、松、楓（黃楓谷）、草原、海島礁岩、雪山（大晉北部）。
- 天氣：每地區獨立 Weather / Climate；靈氣濃郁區加薄霧與粒子。
- 嚴禁使用 Bethesda 原始 mesh/texture 重新打包；可引用原版資源（原版自帶，不重新發布）。

## 命名規則

`CR_<類型>_<拼音>`：`CR_Loc_HuangFengGu`、`CR_Cell_QiXuanMen_DaDian`、`CR_MQ11_XueSe`、
`CR_NPC_NanGongWan`、`CR_Spell_HuoDan`、`CR_Tree_QingYuan`、`CR_Kw_Elem_Huo`。
