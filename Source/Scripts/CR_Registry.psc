Scriptname CR_Registry extends Quest
;/ 資料驅動註冊表。啟動時掃描 Data/SKSE/Plugins/ChineseRim/{techniques,sects,pills}/*.json
 並合併到記憶體（JContainers）。第三方模組只需把 JSON 丟進對應資料夾。
 功法 → 找到 perkTree/perks 的 EditorID（透過 Game.GetFormFromFile 或 JContainers 的 form 字串 "__formData|Plugin.esp|0x1234"）。/;

import JMap
import JArray
import JValue

int Property Gongfa = 0 Auto Hidden     ; JMap id -> entry
int Property Spells = 0 Auto Hidden
int Property Sects  = 0 Auto Hidden
int Property Pills  = 0 Auto Hidden

CR_Registry Function GetInstance() Global
    return Game.GetFormFromFile(0x000D64, "ChineseRim.esm") as CR_Registry
EndFunction

Event OnInit()
    Reload()
EndEvent

Function Reload()
    Gongfa = JMap.object()  ; JValue.retain 讓物件不被 GC
    JValue.retain(Gongfa, "CR_Registry")
    Spells = JMap.object()
    JValue.retain(Spells, "CR_Registry")
    Sects = JMap.object()
    JValue.retain(Sects, "CR_Registry")
    Pills = JMap.object()
    JValue.retain(Pills, "CR_Registry")

    ; 核心資料
    LoadFile("Data/SKSE/Plugins/ChineseRim/techniques.json", "gongfa")
    LoadFile("Data/SKSE/Plugins/ChineseRim/sects.json", "sects")
    LoadFile("Data/SKSE/Plugins/ChineseRim/treasures.json", "pills")
    ; 第三方掛載
    LoadDir("Data/SKSE/Plugins/ChineseRim/techniques", "gongfa")
    LoadDir("Data/SKSE/Plugins/ChineseRim/sects", "sects")
    LoadDir("Data/SKSE/Plugins/ChineseRim/pills", "pills")
    Debug.Trace("[ChineseRim] Registry: gongfa=" + JMap.count(Gongfa) + " spells=" + JMap.count(Spells) + " sects=" + JMap.count(Sects) + " pills=" + JMap.count(Pills))
EndFunction

Function LoadDir(string asDir, string asKind)
    int files = JValue.readFromDirectory(asDir, ".json")  ; JMap filename -> object
    string k = JMap.nextKey(files)
    while k != ""
        MergeObject(JMap.getObj(files, k), asKind, k)
        k = JMap.nextKey(files, k)
    endwhile
EndFunction

Function LoadFile(string asPath, string asKind)
    int root = JValue.readFromFile(asPath)
    if root
        MergeObject(root, asKind, asPath)
    endif
EndFunction

Function MergeObject(int aiRoot, string asKind, string asSource)
    int target
    string arrKey
    if asKind == "gongfa"
        target = Gongfa
        arrKey = "gongfa"
        MergeArray(JMap.getObj(aiRoot, "spells"), Spells, asSource)
    elseif asKind == "sects"
        target = Sects
        arrKey = "sects"
    else
        target = Pills
        arrKey = "pills"
    endif
    MergeArray(JMap.getObj(aiRoot, arrKey), target, asSource)
EndFunction

Function MergeArray(int aiArr, int aiTarget, string asSource)
    if !aiArr
        return
    endif
    int i = 0
    int n = JArray.count(aiArr)
    while i < n
        int e = JArray.getObj(aiArr, i)
        string id = JMap.getStr(e, "id")
        if id != ""
            if JMap.hasKey(aiTarget, id)
                Debug.Trace("[ChineseRim] " + asSource + " 覆寫既有 id " + id)
            endif
            JMap.setStr(e, "_source", asSource)
            JMap.setObj(aiTarget, id, e)
        endif
        i += 1
    endwhile
EndFunction

; ---- 功法 ----
bool Function ActorHasGongfa(Actor akActor, string asId)
    int e = JMap.getObj(Gongfa, asId)
    if !e
        return false
    endif
    Perk entry = EntryPerk(e)
    return entry && akActor.HasPerk(entry)
EndFunction

Function TeachGongfa(Actor akActor, string asId)
    int e = JMap.getObj(Gongfa, asId)
    if !e
        Debug.Trace("[ChineseRim] 未知功法 " + asId)
        return
    endif
    Perk entry = EntryPerk(e)
    if entry && !akActor.HasPerk(entry)
        akActor.AddPerk(entry)
        if akActor == Game.GetPlayer()
            Debug.Notification("習得功法：" + JMap.getStr(e, "name"))
        endif
    endif
EndFunction

; 功法入口 Perk：skyrim.perks[0] 的 EditorID（需 po3 Tweaks 的 GetFormFromEditorID）
; 或 JSON 內 "entryPerk": "__formData|MyMod.esp|0x000D65"
Perk Function EntryPerk(int aiEntry)
    Form f = JMap.getForm(aiEntry, "entryPerk")
    if f
        return f as Perk
    endif
    int sk = JMap.getObj(aiEntry, "skyrim")
    string perkTree = JMap.getStr(sk, "perkTree")
    if perkTree != "" && SKSE.GetPluginVersion("po3_Tweaks") > 0
        return PO3_SKSEFunctions.GetFormFromEditorID(perkTree + "_Entry") as Perk
    endif
    return None
EndFunction
