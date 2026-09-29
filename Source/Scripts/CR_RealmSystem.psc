Scriptname CR_RealmSystem extends Quest
{境界系統。附在 CR_SystemQuest（Start Game Enabled）上。
 以 Actor 的 Faction Rank 儲存境界（CR_Fac_RealmTracker：Rank = order*20 + sub），
 這樣境界資訊會隨存檔保存、可被 SPID/條件函式讀取，也不需要額外 AV。
 屬性基礎值由 data/realms.json 的 skyrim.* 欄位重算（透過 JContainers）。}

import JMap
import JArray
import JValue

Faction Property CR_Fac_RealmTracker Auto
GlobalVariable Property CR_GV_PlayerRealmOrder Auto
GlobalVariable Property CR_GV_PlayerRealmSub Auto
Keyword Property CR_Kw_Realm_Mortal Auto
Keyword Property CR_Kw_Realm_QiRefining Auto
Keyword Property CR_Kw_Realm_Foundation Auto
Keyword Property CR_Kw_Realm_CoreFormation Auto
Keyword Property CR_Kw_Realm_NascentSoul Auto
Keyword Property CR_Kw_Realm_DeityTransformation Auto
Spell Property CR_Ab_RealmPressure Auto
{境界威壓被動：由 CR_ElementResolver/Perk 條件讀 Rank 判斷恐懼}

int Property _realmsJson = 0 Auto   ; JContainers 物件（JArray of realms）

CR_RealmSystem Function GetInstance() Global
    return Game.GetFormFromFile(0x000D62, "ChineseRim.esm") as CR_RealmSystem
EndFunction

Event OnInit()
    LoadRealmTable()
EndEvent

Function LoadRealmTable()
    int root = JValue.readFromFile("Data/SKSE/Plugins/ChineseRim/realms.json")
    if root
        _realmsJson = JMap.getObj(root, "realms")
        JValue.retain(_realmsJson, "CR_RealmSystem")
    else
        Debug.Trace("[ChineseRim] realms.json 讀取失敗")
    endif
EndFunction

; ---- 查詢 ----
int Function GetRealmOrder(Actor akActor)
    int rank = akActor.GetFactionRank(CR_Fac_RealmTracker)
    if rank < 0
        return 0
    endif
    return rank / 20
EndFunction

int Function GetRealmSub(Actor akActor)
    int rank = akActor.GetFactionRank(CR_Fac_RealmTracker)
    if rank < 0
        return 0
    endif
    return rank % 20
EndFunction

string Function GetRealmId(Actor akActor)
    int order = GetRealmOrder(akActor)
    int entry = JArray.getObj(_realmsJson, order)
    return JMap.getStr(entry, "id", "mortal")
EndFunction

int Function OrderOf(string asRealmId)
    int i = 0
    int n = JArray.count(_realmsJson)
    while i < n
        if JMap.getStr(JArray.getObj(_realmsJson, i), "id") == asRealmId
            return i
        endif
        i += 1
    endwhile
    return -1
EndFunction

; ---- 設定 ----
Function SetRealm(Actor akActor, string asRealmId, int aiSub = 0)
    int order = OrderOf(asRealmId)
    if order < 0
        Debug.Trace("[ChineseRim] 未知境界 " + asRealmId)
        return
    endif
    int oldOrder = GetRealmOrder(akActor)
    akActor.SetFactionRank(CR_Fac_RealmTracker, order * 20 + aiSub)
    ApplyRealmStats(akActor, order)
    ApplyRealmKeyword(akActor, order)
    if akActor == Game.GetPlayer()
        CR_GV_PlayerRealmOrder.SetValueInt(order)
        CR_GV_PlayerRealmSub.SetValueInt(aiSub)
    endif
    int h = ModEvent.Create("CR_OnRealmChanged")
    if h
        ModEvent.PushForm(h, akActor)
        ModEvent.PushInt(h, order)
        ModEvent.PushInt(h, aiSub)
        ModEvent.PushInt(h, oldOrder)
        ModEvent.Send(h)
    endif
EndFunction

Function AdvanceSub(Actor akActor)
    int order = GetRealmOrder(akActor)
    int sub = GetRealmSub(akActor)
    int entry = JArray.getObj(_realmsJson, order)
    int maxSub = JArray.count(JMap.getObj(entry, "sub")) - 1
    if sub < maxSub
        akActor.SetFactionRank(CR_Fac_RealmTracker, order * 20 + sub + 1)
        if akActor == Game.GetPlayer()
            CR_GV_PlayerRealmSub.SetValueInt(sub + 1)
        endif
    endif
EndFunction

; 依 realms.json skyrim.healthBase 等重算基礎屬性。
; 只改 Actor Value 基礎值，不動任何原版 Perk/技能，保持與戰鬥模組相容。
Function ApplyRealmStats(Actor akActor, int aiOrder)
    int entry = JArray.getObj(_realmsJson, aiOrder)
    int sk = JMap.getObj(entry, "skyrim")
    if !sk
        return
    endif
    float hp = JMap.getFlt(sk, "healthBase", -1.0)
    float mp = JMap.getFlt(sk, "magickaBase", -1.0)
    float sp = JMap.getFlt(sk, "staminaBase", -1.0)
    if hp > 0
        akActor.SetActorValue("Health", hp)
    endif
    if mp > 0
        akActor.SetActorValue("Magicka", mp)
    endif
    if sp > 0
        akActor.SetActorValue("Stamina", sp)
    endif
    if !akActor.HasSpell(CR_Ab_RealmPressure)
        akActor.AddSpell(CR_Ab_RealmPressure, false)
    endif
EndFunction

; 境界 Keyword 讓對話條件、SPID、其他模組可用 HasKeyword 判斷
Function ApplyRealmKeyword(Actor akActor, int aiOrder)
    ; Keyword 無法在執行期加到 Actor；改以 Faction Rank + Perk 條件實作，
    ; 此函式保留給 DLL（ChineseRim.dll 提供 AddKeywordToRef）。
    if SKSE.GetPluginVersion("ChineseRim") > 0
        CR_Native.SetRealmKeyword(akActor, aiOrder)
    endif
EndFunction
