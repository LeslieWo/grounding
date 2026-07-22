import SwiftUI

/// 记忆库：回忆卡片存在手机 Documents/library.json，照片存在 Documents/photos/。
/// **服务器上一份都没有。** 每一轮对话，我们把卡片带上去给 agent 读，它读完就忘。
@MainActor
final class LibraryStore: ObservableObject {
    @Published private(set) var cards: [MemoryCard] = []
    @Published var migrating = false
    @Published var migrateError: String?

    private static var fileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("library.json")
    }

    private let migratedKey = "libraryMigrated"

    init() { load() }

    var isEmpty: Bool { cards.isEmpty }

    // MARK: - 本地读写

    func load() {
        guard let data = try? Data(contentsOf: Self.fileURL),
              let list = try? JSONDecoder().decode([MemoryCard].self, from: data) else { return }
        cards = list
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(cards) {
            try? data.write(to: Self.fileURL, options: .atomic)
        }
    }

    func add(_ card: MemoryCard, photo: Data) {
        var c = card
        if c.id.isEmpty { c.id = UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(8).lowercased() }
        PhotoCache.save(id: c.id, data: photo)
        cards.removeAll { $0.id == c.id }
        cards.append(c)
        persist()
    }

    func delete(_ id: String) {
        cards.removeAll { $0.id == id }
        PhotoCache.delete(id)
        persist()
    }

    // MARK: - 一次性搬家：把旧后端上的照片和卡片全部搬回手机

    /// 只在第一次装上这个版本时跑一次。搬完之后旧服务就可以彻底关掉，
    /// 照片就再也不在任何云上了——回到最初"照片不出设备"的那条线。
    func migrateIfNeeded() async {
        guard !UserDefaults.standard.bool(forKey: migratedKey) else { return }
        guard cards.isEmpty, !Config.migrateBase.isEmpty else {
            UserDefaults.standard.set(true, forKey: migratedKey)   // 没什么可搬的
            return
        }

        migrating = true
        migrateError = nil
        do {
            let remote = try await API.exportFromOldBackend()
            var got: [MemoryCard] = []
            for card in remote {
                guard !card.id.isEmpty else { continue }
                if PhotoCache.cachedImage(card.id) == nil {
                    if let data = try? await API.photoFromOldBackend(card.id) {
                        PhotoCache.save(id: card.id, data: data)
                    } else {
                        continue      // 照片没搬下来就先不收这张，下次再试
                    }
                }
                got.append(card)
            }
            if !got.isEmpty {
                cards = got
                persist()
                UserDefaults.standard.set(true, forKey: migratedKey)
            } else {
                migrateError = "一张也没搬下来，等下再试试"
            }
        } catch {
            migrateError = error.localizedDescription
        }
        migrating = false
    }
}
