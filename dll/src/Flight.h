#pragma once
// 御器飛行：築基滑翔 / 結丹以上完整飛行。
// 實作方向：切換 Actor 的 bhkCharacterController 為飛行狀態（類似 Flying Mod 的 SetActorFlying），
// 並以 OAR 條件切換御劍動畫。元磁神光等「禁飛」效果透過 CR_Kw_NoFly Keyword 檢查。
namespace ChineseRim::Flight {
    void Install();
    void Reset();
    bool IsFlying(RE::Actor* a);
    void Set(RE::Actor* a, bool enable);
    void SetSpeed(float speed);
}
