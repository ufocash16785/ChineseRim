Scriptname CR_SectSystem extends Quest
;/ 門派聲望系統。與 CR_RealmSystem 掛在同一個 CR_SystemQuest（Start Game Enabled）上 —
 需要在 Creation Kit 裡把本腳本額外附加到該 Quest（沿用同一個 FormID 0x000D62），
 不需要建立新的 Quest 物件。
 以 Actor 對特定門派 Faction 的 Rank 儲存聲望，範圍固定為 -4 ~ 4；
 Rank 實際發生變動時會送出 CR_OnSectRankChanged(akActor, akSect, aiNewRank, aiOldRank) 事件。/;

CR_SectSystem Function GetInstance() Global
    return Game.GetFormFromFile(0x000D62, "ChineseRim.esm") as CR_SectSystem
EndFunction

; 門派聲望增減；Rank 範圍 -4 ~ 4（超出會被夾住），Rank 實際改變時送出 CR_OnSectRankChanged
Function ModRep(Actor akActor, Faction akSect, int aiDelta)
    if !akActor || !akSect || aiDelta == 0
        return
    endif

    int oldRank = akActor.GetFactionRank(akSect)
    int newRank = oldRank + aiDelta
    if newRank > 4
        newRank = 4
    elseif newRank < -4
        newRank = -4
    endif

    if newRank == oldRank
        return
    endif

    akActor.SetFactionRank(akSect, newRank)

    int h = ModEvent.Create("CR_OnSectRankChanged")
    if h
        ModEvent.PushForm(h, akActor)
        ModEvent.PushForm(h, akSect)
        ModEvent.PushInt(h, newRank)
        ModEvent.PushInt(h, oldRank)
        ModEvent.Send(h)
    endif
EndFunction
