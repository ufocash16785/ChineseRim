Scriptname CR_Native Hidden
{由 ChineseRim.dll（SKSE 插件）註冊的原生函式。DLL 未載入時呼叫會失敗，
 請先用 SKSE.GetPluginVersion("ChineseRim") > 0 檢查。}

; 境界 Keyword（執行期加到 Actor，讓 HasKeyword 條件可用）
Function SetRealmKeyword(Actor akActor, int aiOrder) Global Native

; 縮放物品附魔強度（成長型法寶）
Function ScaleEnchantment(ObjectReference akItem, float afMult) Global Native

; 飛行
bool Function IsFlying(Actor akActor) Global Native
Function SetFlight(Actor akActor, bool abEnable) Global Native
Function SetFlightSpeed(float afSpeed) Global Native

; 五行傷害 Hook 開關（MCM）
Function SetElementHookEnabled(bool abEnabled) Global Native

; 熱載入 JSON（開發用）
Function ReloadData() Global Native
