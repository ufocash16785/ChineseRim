#include "PCH.h"
#include "Papyrus.h"
#include "ElementHook.h"
#include "Flight.h"
#include "RealmKeyword.h"
#include "DataRegistry.h"

namespace ChineseRim::Papyrus {
    using VM = RE::BSScript::IVirtualMachine;

    void SetRealmKeyword(RE::StaticFunctionTag*, RE::Actor* a, std::int32_t order) { if (a) RealmKeyword::Apply(a, order); }
    void ScaleEnchantment(RE::StaticFunctionTag*, RE::TESObjectREFR* item, float mult) { if (item) ElementHook::ScaleEnchantment(item, mult); }
    bool IsFlying(RE::StaticFunctionTag*, RE::Actor* a) { return a && Flight::IsFlying(a); }
    void SetFlight(RE::StaticFunctionTag*, RE::Actor* a, bool enable) { if (a) Flight::Set(a, enable); }
    void SetFlightSpeed(RE::StaticFunctionTag*, float speed) { Flight::SetSpeed(speed); }
    void SetElementHookEnabled(RE::StaticFunctionTag*, bool enabled) { ElementHook::SetEnabled(enabled); }
    void ReloadData(RE::StaticFunctionTag*) { DataRegistry::Get().LoadAll(); }

    bool Bind(VM* vm)
    {
        // CR_Native（內部）
        vm->RegisterFunction("SetRealmKeyword", "CR_Native", SetRealmKeyword);
        vm->RegisterFunction("ScaleEnchantment", "CR_Native", ScaleEnchantment);
        vm->RegisterFunction("IsFlying", "CR_Native", IsFlying);
        vm->RegisterFunction("SetFlight", "CR_Native", SetFlight);
        vm->RegisterFunction("SetFlightSpeed", "CR_Native", SetFlightSpeed);
        vm->RegisterFunction("SetElementHookEnabled", "CR_Native", SetElementHookEnabled);
        vm->RegisterFunction("ReloadData", "CR_Native", ReloadData);
        // CR_API（公開，與 CR_Native 同實作）
        vm->RegisterFunction("IsFlying", "CR_API", IsFlying);
        vm->RegisterFunction("SetFlight", "CR_API", SetFlight);
        return true;
    }
}
