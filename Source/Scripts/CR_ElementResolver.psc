Scriptname CR_ElementResolver extends Quest
{五行相生相剋。
 相生：木→火→土→金→水→木
 相剋：木剋土、土剋水、水剋火、火剋金、金剋木
 變異屬性映射父五行：雷→木、冰→水、風→木、暗→水
 倍率：剋制 1.5、被剋 0.75、其餘 1.0（可在 MCM 調整）。
 實際傷害 Hook 由 ChineseRim.dll 在 OnHit 前套用（效能考量）；此腳本提供
 查詢與 DLL 不存在時的 Papyrus 後備（OnHit 事件，僅玩家與追隨者）。}

Keyword Property CR_Kw_Elem_Jin Auto
Keyword Property CR_Kw_Elem_Mu Auto
Keyword Property CR_Kw_Elem_Shui Auto
Keyword Property CR_Kw_Elem_Huo Auto
Keyword Property CR_Kw_Elem_Tu Auto
Keyword Property CR_Kw_Elem_Lei Auto
Keyword Property CR_Kw_Elem_Bing Auto
Keyword Property CR_Kw_Elem_Feng Auto
GlobalVariable Property CR_GV_ElemAdvMult Auto   ; 預設 1.5
GlobalVariable Property CR_GV_ElemDisMult Auto   ; 預設 0.75

CR_ElementResolver Function GetInstance() Global
    return Game.GetFormFromFile(0x000D65, "ChineseRim.esm") as CR_ElementResolver
EndFunction

string Function ElementOfForm(Form akForm)
    if akForm.HasKeyword(CR_Kw_Elem_Jin)
        return "金"
    elseif akForm.HasKeyword(CR_Kw_Elem_Mu) || akForm.HasKeyword(CR_Kw_Elem_Lei) || akForm.HasKeyword(CR_Kw_Elem_Feng)
        return "木"
    elseif akForm.HasKeyword(CR_Kw_Elem_Shui) || akForm.HasKeyword(CR_Kw_Elem_Bing)
        return "水"
    elseif akForm.HasKeyword(CR_Kw_Elem_Huo)
        return "火"
    elseif akForm.HasKeyword(CR_Kw_Elem_Tu)
        return "土"
    endif
    return ""
EndFunction

; Actor 主屬性：靈根 Race 帶 CR_Kw_Elem_* Keyword
string Function PrimaryElementOf(Actor akActor)
    return ElementOfForm(akActor.GetRace())
EndFunction

; 攻擊方 a 是否剋制 b
bool Function Overcomes(string a, string b)
    return (a == "木" && b == "土") || (a == "土" && b == "水") || (a == "水" && b == "火") || (a == "火" && b == "金") || (a == "金" && b == "木")
EndFunction

float Function Resolve(Form akSource, Actor akTarget)
    string a = ElementOfForm(akSource)
    string b = PrimaryElementOf(akTarget)
    if a == "" || b == ""
        return 1.0
    endif
    if Overcomes(a, b)
        return CR_GV_ElemAdvMult.GetValue()
    elseif Overcomes(b, a)
        return CR_GV_ElemDisMult.GetValue()
    endif
    return 1.0
EndFunction
