#include "PCH.h"
#include "ElementHook.h"
#include "DataRegistry.h"

namespace ChineseRim::ElementHook {
    namespace {
        bool g_enabled = true;
        enum class Elem { None, Jin, Mu, Shui, Huo, Tu };

        Elem ElemOf(RE::TESForm* form)
        {
            if (!form) return Elem::None;
            auto kw = form->As<RE::BGSKeywordForm>();
            if (!kw) return Elem::None;
            // 變異屬性映射父五行：雷/風→木、冰/暗→水
            static const std::vector<std::pair<std::string_view, Elem>> table = {
                {"CR_Kw_Elem_Jin"sv, Elem::Jin}, {"CR_Kw_Elem_Mu"sv, Elem::Mu}, {"CR_Kw_Elem_Lei"sv, Elem::Mu}, {"CR_Kw_Elem_Feng"sv, Elem::Mu},
                {"CR_Kw_Elem_Shui"sv, Elem::Shui}, {"CR_Kw_Elem_Bing"sv, Elem::Shui}, {"CR_Kw_Elem_An"sv, Elem::Shui},
                {"CR_Kw_Elem_Huo"sv, Elem::Huo}, {"CR_Kw_Elem_Tu"sv, Elem::Tu}
            };
            for (auto& [name, e] : table)
                if (kw->HasKeywordString(name)) return e;
            return Elem::None;
        }

        bool Overcomes(Elem a, Elem b)
        {
            return (a == Elem::Mu && b == Elem::Tu) || (a == Elem::Tu && b == Elem::Shui) || (a == Elem::Shui && b == Elem::Huo) ||
                   (a == Elem::Huo && b == Elem::Jin) || (a == Elem::Jin && b == Elem::Mu);
        }

        // Hook 點：Actor::HandleHealthDamage 之前的 HitData 處理（CommonLibSSE-NG 位址由 Address Library 解析）
        struct ProcessHit {
            static void thunk(RE::Actor* target, RE::HitData& hitData)
            {
                if (g_enabled && target) {
                    RE::TESForm* source = hitData.weapon ? static_cast<RE::TESForm*>(hitData.weapon) : nullptr;
                    // 法術命中時 weapon 為 null；由 MagicTarget 事件另行處理（見 MagicHit）
                    float mult = Resolve(source, target);
                    hitData.totalDamage *= mult;
                    hitData.physicalDamage *= mult;
                }
                func(target, hitData);
            }
            static inline REL::Relocation<decltype(thunk)> func;
            static constexpr std::size_t idx = 0;
        };
    }

    float Resolve(RE::TESForm* source, RE::Actor* target)
    {
        auto a = ElemOf(source);
        auto b = target ? ElemOf(target->GetRace()) : Elem::None;
        if (a == Elem::None || b == Elem::None) return 1.0f;
        auto& cfg = DataRegistry::Get().Config();
        if (Overcomes(a, b)) return cfg.elemAdvMult;
        if (Overcomes(b, a)) return cfg.elemDisMult;
        return 1.0f;
    }

    void SetEnabled(bool enabled) { g_enabled = enabled; }

    void ScaleEnchantment(RE::TESObjectREFR* item, float mult)
    {
        // 透過 ExtraEnchantment 的 charge/強度縮放；細節依 CommonLibSSE 版本調整
        if (auto xEnch = item->extraList.GetByType<RE::ExtraEnchantment>()) {
            xEnch->charge = static_cast<std::uint16_t>(std::min(65535.0f, xEnch->charge * mult));
        }
    }

    void Install()
    {
        // TODO: 以 Address Library ID 定位 Actor 傷害處理函式並 write_call；
        // 開發初期可改用 RE::ScriptEventSourceHolder 的 TESHitEvent 後補傷害（精度較低）。
        SKSE::log::info("ElementHook installed (stub)");
    }
}
