Scriptname CR_ZhangTianPing extends ObjectReference
{掌天瓶（神秘小瓶）。任務物品，不可丟棄。
 每逢月圓（Skyrim 月相：GameDaysPassed % 24 的第 0 日附近視為滿月）吸收月華，
 產出一滴「靈液」(CR_Misc_LingYe)。靈液對植物類 Ingredient 使用可升級藥材，
 直接飲用回復大量法力。月相事件同時送出 CR_OnMoonFull 供其他模組掛接。}

MiscObject Property CR_Misc_LingYe Auto
Message Property CR_Msg_LingYeProduced Auto
GlobalVariable Property GameDaysPassed Auto
GlobalVariable Property CR_GV_LastMoonDay Auto
int Property MoonCycleDays = 24 AutoReadOnly   ; Skyrim 月相週期

Event OnContainerChanged(ObjectReference akNewContainer, ObjectReference akOldContainer)
    if akNewContainer == Game.GetPlayer()
        RegisterForSingleUpdateGameTime(1.0)
    else
        UnregisterForUpdateGameTime()
    endif
EndEvent

Event OnUpdateGameTime()
    int day = GameDaysPassed.GetValueInt()
    ; 月圓：週期內第 0 天；避免同一天重複觸發
    if (day % MoonCycleDays) == 0 && CR_GV_LastMoonDay.GetValueInt() != day
        CR_GV_LastMoonDay.SetValueInt(day)
        ; 需在室外且夜間才吸收月華（忠實原作：小瓶須置於月光下）
        Actor p = Game.GetPlayer()
        float hour = (Utility.GetCurrentGameTime() - Utility.GetCurrentGameTime() as int) * 24.0
        if !p.IsInInterior() && (hour >= 21.0 || hour <= 4.0)
            p.AddItem(CR_Misc_LingYe, 1, true)
            CR_Msg_LingYeProduced.Show()
        endif
        int h = ModEvent.Create("CR_OnMoonFull")
        if h
            ModEvent.PushInt(h, day)
            ModEvent.Send(h)
        endif
    endif
    RegisterForSingleUpdateGameTime(6.0)
EndEvent
