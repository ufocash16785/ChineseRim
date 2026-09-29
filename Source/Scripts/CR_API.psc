Scriptname CR_API Hidden
{ChineseRim 公開 API。第三方模組請只呼叫此檔內的 Global 函式，內部腳本可能變動。
 所有函式在 ChineseRim.esm 載入後可用；需要 JContainers。}

; ---------------------------------------------------------------------------
; 境界
; ---------------------------------------------------------------------------

; 回傳境界 order：0 凡人, 1 練氣, 2 築基, 3 結丹, 4 元嬰, 5 化神, 6 煉虛, 7 合體, 8 大乘, 9 真仙
int Function GetRealm(Actor akActor) Global
    return CR_RealmSystem.GetInstance().GetRealmOrder(akActor)
EndFunction

; 回傳子階：練氣期為 1~13 層；其他境界 0 初期 / 1 中期 / 2 後期 / 3 圓滿
int Function GetRealmSub(Actor akActor) Global
    return CR_RealmSystem.GetInstance().GetRealmSub(akActor)
EndFunction

; 境界 id 字串（"qi_refining" 等），對應 data/realms.json
string Function GetRealmId(Actor akActor) Global
    return CR_RealmSystem.GetInstance().GetRealmId(akActor)
EndFunction

; 嘗試突破。akPill 可為 None（純閉關）。成功回傳 true 並送出 CR_OnBreakthrough 事件。
bool Function TryBreakthrough(Actor akActor, Form akPill = None) Global
    return CR_Breakthrough.GetInstance().Attempt(akActor, akPill)
EndFunction

; 直接設定境界（劇情/除錯用；會重算屬性並送出 CR_OnRealmChanged）
Function SetRealm(Actor akActor, string asRealmId, int aiSub = 0) Global
    CR_RealmSystem.GetInstance().SetRealm(akActor, asRealmId, aiSub)
EndFunction

; ---------------------------------------------------------------------------
; 功法 / 法術
; ---------------------------------------------------------------------------

; 執行期註冊功法 JSON（路徑相對於 Data/）。啟動時 CR_Registry 已自動掃描
; SKSE/Plugins/ChineseRim/techniques/，此函式供 .esp 腳本動態加入。
Function RegisterGongfa(string asJsonPath) Global
    CR_Registry.GetInstance().LoadFile(asJsonPath, "gongfa")
EndFunction

; 是否已習得功法（id 對應 techniques.json 的 gongfa[].id）
bool Function HasGongfa(Actor akActor, string asGongfaId) Global
    return CR_Registry.GetInstance().ActorHasGongfa(akActor, asGongfaId)
EndFunction

; 傳授功法：加入 Perk 樹入口 Perk、送出通知
Function TeachGongfa(Actor akActor, string asGongfaId) Global
    CR_Registry.GetInstance().TeachGongfa(akActor, asGongfaId)
EndFunction

; ---------------------------------------------------------------------------
; 五行
; ---------------------------------------------------------------------------

; 五行剋制倍率：來源（法術/武器 Form 帶 CR_Kw_Elem_*）對目標（Actor 靈根/主屬性）
float Function GetElementMult(Form akSource, Actor akTarget) Global
    return CR_ElementResolver.GetInstance().Resolve(akSource, akTarget)
EndFunction

; 取得 Actor 主五行："金" "木" "水" "火" "土"，或變異 "雷" "冰" "風"
string Function GetPrimaryElement(Actor akActor) Global
    return CR_ElementResolver.GetInstance().PrimaryElementOf(akActor)
EndFunction

; ---------------------------------------------------------------------------
; 門派
; ---------------------------------------------------------------------------

; 門派聲望增減；Rank 範圍 -4 ~ 4，跨越門檻會送出 CR_OnSectRankChanged
Function ModSectRep(Actor akActor, Faction akSect, int aiDelta) Global
    CR_SectSystem.GetInstance().ModRep(akActor, akSect, aiDelta)
EndFunction

int Function GetSectRank(Actor akActor, Faction akSect) Global
    return akActor.GetFactionRank(akSect)
EndFunction

; ---------------------------------------------------------------------------
; 飛行（由 ChineseRim.dll 實作；DLL 未載入時回傳 false / 無作用）
; ---------------------------------------------------------------------------

bool Function IsFlying(Actor akActor) Global Native
Function SetFlight(Actor akActor, bool abEnable) Global Native
; 0 = 不可飛, 1 = 滑翔（築基）, 2 = 完整飛行（結丹以上）
int Function GetFlightTier(Actor akActor) Global
    int realm = GetRealm(akActor)
    if realm >= 3
        return 2
    elseif realm == 2
        return 1
    endif
    return 0
EndFunction

; ---------------------------------------------------------------------------
; 法寶
; ---------------------------------------------------------------------------

; 祭煉等級 0~N（對應 treasures.json growth 陣列索引）
int Function GetTreasureGrade(ObjectReference akItem) Global
    return CR_TreasureGrowth.GetInstance().GradeOf(akItem)
EndFunction

bool Function RefineTreasure(Actor akOwner, ObjectReference akItem) Global
    return CR_TreasureGrowth.GetInstance().Refine(akOwner, akItem)
EndFunction

; ---------------------------------------------------------------------------
; 版本
; ---------------------------------------------------------------------------
int Function GetAPIVersion() Global
    return 1
EndFunction
