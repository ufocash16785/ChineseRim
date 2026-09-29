Scriptname CR_TreasureGrowth extends Quest
{法寶祭煉成長。每件成長型法寶（treasures.json 內含 skyrim.growth 的條目）是一個帶
 CR_Kw_Treasure_Growable Keyword 的物品；祭煉等級存放在 JContainers 的 JFormMap（以 ObjectReference 為鍵）。
 祭煉條件：玩家境界 >= 下一階所需境界，並消耗靈石。升階時以 SetItemHealthPercent /
 附魔強度重算，讓「法寶隨境界變強」而不需要建立多個物品 Form。}

import JFormMap
import JValue

Keyword Property CR_Kw_Treasure_Growable Auto
MiscObject Property CR_Misc_LingShi_Zhong Auto  ; 中品靈石
Message Property CR_Msg_RefineSuccess Auto
Message Property CR_Msg_RefineNeedRealm Auto
CR_RealmSystem Property RealmSystem Auto

int _grades = 0

CR_TreasureGrowth Function GetInstance() Global
    return Game.GetFormFromFile(0x000D66, "ChineseRim.esm") as CR_TreasureGrowth
EndFunction

Event OnInit()
    _grades = JFormMap.object()
    JValue.retain(_grades, "CR_TreasureGrowth")
EndEvent

int Function GradeOf(ObjectReference akItem)
    return JFormMap.getInt(_grades, akItem, 0)
EndFunction

; 每階所需境界：grade 1 需築基(2)、grade 2 需結丹(3)、grade 3 需元嬰(4)
int Function RequiredRealm(int aiGrade)
    return aiGrade + 1
EndFunction

int Function CostLingShi(int aiGrade)
    return 50 * aiGrade * aiGrade
EndFunction

bool Function Refine(Actor akOwner, ObjectReference akItem)
    if !akItem.HasKeyword(CR_Kw_Treasure_Growable)
        return false
    endif
    int next = GradeOf(akItem) + 1
    if RealmSystem.GetRealmOrder(akOwner) < RequiredRealm(next)
        CR_Msg_RefineNeedRealm.Show()
        return false
    endif
    int cost = CostLingShi(next)
    if akOwner.GetItemCount(CR_Misc_LingShi_Zhong) < cost
        return false
    endif
    akOwner.RemoveItem(CR_Misc_LingShi_Zhong, cost, true)
    JFormMap.setInt(_grades, akItem, next)
    ApplyGrade(akItem, next)
    int h = ModEvent.Create("CR_OnTreasureRefined")
    if h
        ModEvent.PushForm(h, akItem)
        ModEvent.PushInt(h, next)
        ModEvent.Send(h)
    endif
    CR_Msg_RefineSuccess.Show(next)
    return true
EndFunction

; 用附魔強度與物品耐久（Tempering）表達成長，兩者都是原版機制，
; 因此 Enchanting/Smithing 相關模組的顯示與計算不受影響。
Function ApplyGrade(ObjectReference akItem, int aiGrade)
    akItem.SetItemHealthPercent(1.0 + 0.25 * aiGrade)
    ; 附魔強度：WornObject.SetEnchantment 需要 SKSE；由 DLL 提供 CR_Native.ScaleEnchantment
    if SKSE.GetPluginVersion("ChineseRim") > 0
        CR_Native.ScaleEnchantment(akItem, 1.0 + 0.5 * aiGrade)
    endif
EndFunction
