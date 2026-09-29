#pragma once
// 讀取 Data/SKSE/Plugins/ChineseRim/*.json（與 Papyrus 端 CR_Registry 相同來源），
// 供 C++ 側快速查表（五行倍率、境界屬性）。
namespace ChineseRim {
    struct Config { float elemAdvMult = 1.5f; float elemDisMult = 0.75f; };
    class DataRegistry {
    public:
        static DataRegistry& Get();
        void LoadAll();
        const Config& Config() const { return cfg_; }
        const nlohmann::json& Realms() const { return realms_; }
    private:
        struct Config cfg_;
        nlohmann::json realms_;
    };
}
