#include "PCH.h"
#include "RealmKeyword.h"

namespace ChineseRim::RealmKeyword {
    static constexpr std::array kNames = {
        "CR_Kw_Realm_Mortal"sv, "CR_Kw_Realm_QiRefining"sv, "CR_Kw_Realm_Foundation"sv, "CR_Kw_Realm_CoreFormation"sv,
        "CR_Kw_Realm_NascentSoul"sv, "CR_Kw_Realm_DeityTransformation"sv, "CR_Kw_Realm_VoidRefining"sv,
        "CR_Kw_Realm_BodyIntegration"sv, "CR_Kw_Realm_Mahayana"sv, "CR_Kw_Realm_TrueImmortal"sv
    };

    void Apply(RE::Actor* a, std::int32_t order)
    {
        auto base = a->GetActorBase();
        if (!base) return;
        auto& kwf = static_cast<RE::BGSKeywordForm&>(*base);
        auto dh = RE::TESDataHandler::GetSingleton();
        for (std::size_t i = 0; i < kNames.size(); ++i) {
            auto kw = RE::TESForm::LookupByEditorID<RE::BGSKeyword>(kNames[i]);   // 需 po3 Tweaks 或自建 EditorID 快取
            if (!kw) continue;
            if (static_cast<std::int32_t>(i) == order) kwf.AddKeyword(kw); else kwf.RemoveKeyword(kw);
        }
        (void)dh;
    }
}
