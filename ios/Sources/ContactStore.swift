import Foundation

/// Trusted contact: when an episode turns dangerous, the agent will put this person right in front of you.
/// **Stored only on the phone** (UserDefaults); carried along with each request for one-time use, and the backend keeps nothing.
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

    /// Returns nil if not set; the backend falls back to a generic help hotline.
    static var contact: Contact? {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !n.isEmpty else { return nil }
        return Contact(contact_name: n, contact_note: note)
    }
}
