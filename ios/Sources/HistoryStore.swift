import Foundation

/// 一次对话的存档。
struct SessionRecord: Identifiable, Codable {
    let id: UUID
    let date: Date
    var messages: [ChatMsg]

    var firstUser: String {
        messages.first(where: { $0.role == "me" })?.text ?? "（这次没开口）"
    }
    var rounds: Int { messages.filter { $0.role == "companion" }.count }
}

/// 对话历史：存在手机本地（Documents/history.json），不上任何服务器。
enum HistoryStore {
    private static var fileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("history.json")
    }

    static func load() -> [SessionRecord] {
        guard let data = try? Data(contentsOf: fileURL),
              let recs = try? JSONDecoder().decode([SessionRecord].self, from: data) else { return [] }
        return recs.sorted { $0.date > $1.date }   // 最近的在最上面
    }

    /// 每轮自动调用：至少聊过一轮才存；同一次对话按 id 覆盖更新。
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
