#pragma once
// 執行期為 Actor 加上境界 Keyword（CR_Kw_Realm_*），讓對話條件與其他模組可用 HasKeyword。
namespace ChineseRim::RealmKeyword { void Apply(RE::Actor* a, std::int32_t order); }
