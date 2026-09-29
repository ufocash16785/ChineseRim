#pragma once
// 五行相生相剋傷害倍率。Hook：RE::HitData 建構後、套用傷害前（ApplyDamage / HitEventHandler）。
// 讀取攻擊來源（法術 MagicItem 或武器）上的 CR_Kw_Elem_* Keyword，與目標 Race 的靈根 Keyword 比對。
namespace ChineseRim::ElementHook {
    void Install();
    void SetEnabled(bool enabled);
    float Resolve(RE::TESForm* source, RE::Actor* target);
    void ScaleEnchantment(RE::TESObjectREFR* item, float mult);
}
