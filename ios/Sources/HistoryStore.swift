import Foundation

/// The archive of one conversation.
struct SessionRecord: Identifiable, Codable {
    let id: UUID
    let date: Date
    var messages: [ChatMsg]

    var firstUser: String {
        messages.first(where: { $0.role == "me" })?.text ?? "（这次没开口）"
    }
    var rounds: Int { messages.filter { $0.role == "companion" }.count }
}

/// Conversation history: stored locally on the phone (Documents/history.json), never sent to any server.
enum HistoryStore {
    private static var fileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("history.json")
    }

    static func load() -> [SessionRecord] {
        guard let data = try? Data(contentsOf: fileURL),
              let recs = try? JSONDecoder().decode([SessionRecord].self, from: data) else { return [] }
        return recs.sorted { $0.date > $1.date }   // most recent on top
    }

    /// Called automatically every turn: only saves once at least one round has been exchanged; the same conversation is overwritten by id.
    static func save(id: UUID, messages: [ChatMsg]) {
        guard messages.contains(where: { $0.role == "companion" }) else { return }
        var recs = load().filter { $0.id != id }
        recs.append(SessionRecord(id: id, date: Date(), messages: messages))
        persist(recs)
    }

    static func delete(_ id: UUID) {
        persist(load().filter { $0.id != id })
    }

    private static func persist(_ recs: [SessionRecord]) {
        if let data = try? JSONEncoder().encode(recs) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }
}
