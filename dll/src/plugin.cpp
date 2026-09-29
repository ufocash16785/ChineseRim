// ChineseRim.dll — SKSE 插件進入點（CommonLibSSE-NG）
// 職責：註冊 Papyrus 原生函式、掛 OnHit 五行倍率、飛行、境界 Keyword、JSON 熱載入。
#include "PCH.h"
#include "Papyrus.h"
#include "ElementHook.h"
#include "Flight.h"
#include "DataRegistry.h"

namespace {
    void MessageHandler(SKSE::MessagingInterface::Message* msg)
    {
        switch (msg->type) {
        case SKSE::MessagingInterface::kDataLoaded:
            ChineseRim::DataRegistry::Get().LoadAll();   // Data/SKSE/Plugins/ChineseRim/*.json
            ChineseRim::ElementHook::Install();          // 五行倍率（HitEvent / ApplyDamage hook）
            ChineseRim::Flight::Install();               // 御器飛行（havok 角色控制器）
            SKSE::log::info("ChineseRim: data loaded, hooks installed");
            break;
        case SKSE::MessagingInterface::kPostLoadGame:
        case SKSE::MessagingInterface::kNewGame:
            ChineseRim::Flight::Reset();
            break;
        default:
            break;
        }
    }
}

SKSEPluginLoad(const SKSE::LoadInterface* skse)
{
    SKSE::Init(skse);
    SKSE::log::info("ChineseRim v{}", SKSE::PluginDeclaration::GetSingleton()->GetVersion().string());

    SKSE::GetMessagingInterface()->RegisterListener(MessageHandler);
    SKSE::GetPapyrusInterface()->Register(ChineseRim::Papyrus::Bind);   // CR_Native.* 與 CR_API 的 Native 函式
    return true;
}
