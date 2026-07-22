import Foundation

/// 可信联系人：发作到危险时，agent 会把这个人端到你面前。
/// **只存在手机本地**（UserDefaults），随请求带给后端用一次，后端不留。
enum ContactStore {
    private static let nameKey = "trustedContactName"
    private static let noteKey = "trustedContactNote"

    static var name: String {
        get { UserDefaults.standard.string(forKey: nameKey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: nameKey) }
    }

    static var note: String {
        get { UserDefaults.standard.string(forKey: noteKey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: noteKey) }
    }

    /// 没设就返回 nil —— 后端会退回到通用求助热线。
    static var contact: Contact? {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !n.isEmpty else { return nil }
        return Contact(contact_name: n, contact_note: note)
    }
}
