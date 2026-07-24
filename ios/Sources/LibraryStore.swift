import SwiftUI

/// The memory library: memory cards live in the phone's Documents/library.json, photos in Documents/photos/.
/// **The server has no copy of any of it.** Each conversation turn we carry the cards up for the agent to read; once it's done reading, it forgets.
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

    // MARK: - Local read/write

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

    // MARK: - One-time migration: move all photos and cards from the old backend back to the phone

    /// Runs only once, the first time this version is installed. After the move, the old service
    /// can be shut down for good and the photos are no longer on any cloud, back to the original
    /// "photos never leave the device" line.
    func migrateIfNeeded() async {
        guard !UserDefaults.standard.bool(forKey: migratedKey) else { return }
        guard cards.isEmpty, !Config.migrateBase.isEmpty else {
            UserDefaults.standard.set(true, forKey: migratedKey)   // nothing to migrate
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
                        continue      // if the photo didn't come down, skip this card for now and retry next time
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
