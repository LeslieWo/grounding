import Foundation

/// 后端地址和 API key 都不写死在代码里 —— 它们从 Info.plist 读，
/// 而 Info.plist 的值来自 `Config.xcconfig`（这个文件不进仓库）。
/// 想跑起来：把 `Config.example.xcconfig` 复制成 `Config.xcconfig` 填上你自己的值。
enum Config {
    private static func plist(_ key: String) -> String {
        (Bundle.main.object(forInfoDictionaryKey: key) as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    /// agent 后端地址（无状态的那个）。
    static var apiBase: String { plist("GroundingAPIBase") }

    /// 调后端要带的 key。没有它，后端一律 401。
    static var apiKey: String { plist("GroundingAPIKey") }

    /// 一次性搬家用的**旧**后端地址（照片还存在那上面的那个）。
    /// 搬完就可以从 Config.xcconfig 里删掉，旧服务也能关了。
    static var migrateBase: String { plist("GroundingMigrateBase") }

    static var isConfigured: Bool { !apiBase.isEmpty && !apiKey.isEmpty }
}
