Scriptname CR_Breakthrough extends Quest
{突破系統。攔截玩家升級：當玩家等級到達當前境界 levelRange 上限時，
 鎖住升級（透過把 Level Up 所需經驗設為極大值），直到成功突破。
 突破 = 丹藥（可選）+ 閉關（時間推進）+ 機率/考驗。}

import JMap
import JArray
import JValue

CR_RealmSystem Property RealmSystem Auto
GlobalVariable Property CR_GV_BreakthroughLocked Auto
Message Property CR_Msg_BottleneckReached Auto
Message Property CR_Msg_BreakthroughSuccess Auto
Message Property CR_Msg_BreakthroughFail Auto
FormList Property CR_FL_BreakthroughPills Auto
{索引與境界 order 對齊：[1]=築基丹, [2]=結金丹, [3]=元嬰丹 ...}

float Property BaseChance = 0.35 AutoReadOnly
float Property PillBonus = 0.45 AutoReadOnly
float Property SubBonus = 0.05 AutoReadOnly   ; 每一子階（圓滿）加成

CR_Breakthrough Function GetInstance() Global
    return Game.GetFormFromFile(0x000D63, "ChineseRim.esm") as CR_Breakthrough
EndFunction

Event OnInit()
    RegisterForModEvent("CR_OnRealmChanged", "OnRealmChanged")
    RegisterForSingleUpdate(5.0)
EndEvent

Event OnUpdate()
    CheckBottleneck(Game.GetPlayer())
    RegisterForSingleUpdate(30.0)
EndEvent

Event OnRealmChanged(Form akActor, int aiOrder, int aiSub, int aiOld)
    if akActor == Game.GetPlayer()
        Unlock()
    endif
EndEvent

Function CheckBottleneck(Actor akPlayer)
    int order = RealmSystem.GetRealmOrder(akPlayer)
    int entry = JArray.getObj(RealmSystem._realmsJson, order)
    int range = JMap.getObj(entry, "levelRange")
    int maxLevel = JArray.getInt(range, 1)
    if akPlayer.GetLevel() >= maxLevel && CR_GV_BreakthroughLocked.GetValueInt() == 0
        Lock()
        CR_Msg_BottleneckReached.Show()
    endif
EndFunction

Function Lock()
    CR_GV_BreakthroughLocked.SetValueInt(1)
    ; 讓等級無法再提升：把升級門檻乘到極大。Game 設定 fXPLevelUpMult 只影響公式，
    ; 這裡改用 SKSE 的 Game.SetGameSettingFloat 拉高 fXPLevelUpBase。
    Game.SetGameSettingFloat("fXPLevelUpBase", 999999.0)
EndFunction

Function Unlock()
    CR_GV_BreakthroughLocked.SetValueInt(0)
    Game.SetGameSettingFloat("fXPLevelUpBase", 75.0)
EndFunction

; 由 CR_API.TryBreakthrough 呼叫
bool Function Attempt(Actor akActor, Form akPill = None)
    int order = RealmSystem.GetRealmOrder(akActor)
    int sub = RealmSystem.GetRealmSub(akActor)
    int entry = JArray.getObj(RealmSystem._realmsJson, order)
    int bt = JMap.getObj(entry, "breakthrough")
    string btType = JMap.getStr(bt, "type", "none")

    float chance = BaseChance + sub * SubBonus
    bool needsPill = (btType == "pill" || btType == "pill_or_chance" || btType == "pill_and_trial")
    Form requiredPill = CR_FL_BreakthroughPills.GetAt(order + 1)
    if needsPill && akPill == None && btType == "pill"
        return false ; 必須丹藥
    endif
    if akPill != None && akPill == requiredPill
        chance += PillBonus
        akActor.RemoveItem(akPill, 1, true)
    endif
    if btType == "insight" || btType == "ascension"
        ; 化神/煉虛以上：機率改由試煉任務決定（任務完成後呼叫 SetRealm）
        return false
    endif

    ; 閉關：推進遊戲時間（可被 MCM 設定）
    Game.FadeOutGame(true, true, 0.5, 2.0)
    Utility.Wait(1.0)
    GameHour.SetValue(GameHour.GetValue() + 6.0)   ; 6 小時閉關
    Game.FadeOutGame(false, true, 0.5, 2.0)

    bool ok = Utility.RandomFloat(0.0, 1.0) < chance
    int h = ModEvent.Create("CR_OnBreakthrough")
    if h
        ModEvent.PushForm(h, akActor)
        ModEvent.PushBool(h, ok)
        ModEvent.PushString(h, JMap.getStr(entry, "id"))
        ModEvent.Send(h)
    endif
    if ok
        int nextEntry = JArray.getObj(RealmSystem._realmsJson, order + 1)
        RealmSystem.SetRealm(akActor, JMap.getStr(nextEntry, "id"), 0)
        if akActor == Game.GetPlayer()
            CR_Msg_BreakthroughSuccess.Show()
        endif
    else
        if akActor == Game.GetPlayer()
            CR_Msg_BreakthroughFail.Show()
            akActor.DamageActorValue("Health", akActor.GetActorValue("Health") * 0.5) ; 反噬
        endif
    endif
    return ok
EndFunction

GlobalVariable Property GameHour Auto
