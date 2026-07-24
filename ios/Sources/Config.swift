import Foundation

/// Neither the backend URL nor the API key is hard-coded: they're read from Info.plist,
/// whose values come from `Config.xcconfig` (a file that stays out of the repo).
/// To get running: copy `Config.example.xcconfig` to `Config.xcconfig` and fill in your own values.
enum Config {
    private static func plist(_ key: String) -> String {
        (Bundle.main.object(forInfoDictionaryKey: key) as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    /// The agent backend URL (the stateless one).
    static var apiBase: String { plist("GroundingAPIBase") }

    /// The key every backend call must carry. Without it, the backend always returns 401.
    static var apiKey: String { plist("GroundingAPIKey") }

    /// The **old** backend URL used for the one-time migration (the one still holding the photos).
    /// Once the move is done it can be deleted from Config.xcconfig and the old service shut down.
    static var migrateBase: String { plist("GroundingMigrateBase") }

    static var isConfigured: Bool { !apiBase.isEmpty && !apiKey.isEmpty }
}
