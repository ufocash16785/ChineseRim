#include "PCH.h"
#include "Flight.h"

namespace ChineseRim::Flight {
    namespace {
        std::unordered_set<RE::FormID> g_flying;
        float g_speed = 1.0f;
    }
    void Install() { SKSE::log::info("Flight installed (stub)"); }
    void Reset() { g_flying.clear(); }
    bool IsFlying(RE::Actor* a) { return a && g_flying.contains(a->GetFormID()); }
    void Set(RE::Actor* a, bool enable)
    {
        if (!a) return;
        if (enable) {
            if (a->HasKeywordString("CR_Kw_NoFly")) return;   // 元磁神光 / 陣法禁飛
            g_flying.insert(a->GetFormID());
            a->SetGraphVariableBool("bCR_Flying", true);        // OAR 條件：御劍動畫
            // TODO: 角色控制器改為 kFlying 狀態，關閉重力，依 g_speed 推進
        } else {
            g_flying.erase(a->GetFormID());
            a->SetGraphVariableBool("bCR_Flying", false);
        }
    }
    void SetSpeed(float speed) { g_speed = std::clamp(speed, 0.1f, 5.0f); }
}
