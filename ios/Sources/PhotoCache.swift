import SwiftUI
import UIKit

/// Photos live only on this phone: Documents/photos/{id}.jpg.
/// The backend has no photos at all, so this **never** pulls images from the cloud (and can't), except
/// for the one-time migration on first install of the new version (see LibraryStore.migrateIfNeeded);
/// after that, it reads local storage only, forever.
enum PhotoCache {
    static let dir: URL = {
        let base = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let d = base.appendingPathComponent("photos", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }()

    static func localURL(_ id: String) -> URL { dir.appendingPathComponent("\(id).jpg") }

    static func cachedImage(_ id: String) -> UIImage? {
        let u = localURL(id)
        guard FileManager.default.fileExists(atPath: u.path),
              let data = try? Data(contentsOf: u) else { return nil }
        return UIImage(data: data)
    }

    static func save(id: String, data: Data) {
        try? data.write(to: localURL(id), options: .atomic)
    }

    static func delete(_ id: String) {
        try? FileManager.default.removeItem(at: localURL(id))
    }
}

/// Display a photo (always read from local storage; opens instantly).
struct LocalPhoto: View {
    let id: String
    @State private var img: UIImage?

    var body: some View {
        Group {
            if let img {
                Image(uiImage: img).resizable().scaledToFill()
            } else {
                Rectangle().fill(Theme.sage.opacity(0.1))
                    .overlay(Image(systemName: "photo").foregroundStyle(Theme.sage.opacity(0.5)))
            }
        }
        .task(id: id) { img = PhotoCache.cachedImage(id) }
    }
}
