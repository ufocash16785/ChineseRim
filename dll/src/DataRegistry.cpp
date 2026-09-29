#include "PCH.h"
#include "DataRegistry.h"
#include <fstream>

namespace ChineseRim {
    DataRegistry& DataRegistry::Get() { static DataRegistry inst; return inst; }

    void DataRegistry::LoadAll()
    {
        const std::filesystem::path root = "Data/SKSE/Plugins/ChineseRim";
        try {
            std::ifstream f(root / "realms.json");
            if (f) realms_ = nlohmann::json::parse(f);
            std::ifstream ini(root / "config.json");
            if (ini) {
                auto j = nlohmann::json::parse(ini);
                cfg_.elemAdvMult = j.value("elemAdvMult", 1.5f);
                cfg_.elemDisMult = j.value("elemDisMult", 0.75f);
            }
            SKSE::log::info("DataRegistry: realms={}", realms_.contains("realms") ? realms_["realms"].size() : 0);
        } catch (const std::exception& e) {
            SKSE::log::error("DataRegistry: {}", e.what());
        }
    }
}
