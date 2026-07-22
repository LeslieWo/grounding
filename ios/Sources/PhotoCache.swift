import SwiftUI
import UIKit

/// 照片只存在这台手机上：Documents/photos/{id}.jpg。
/// 后端没有任何照片，所以这里**不会**、也不能去云上拉图——除了第一次装上新版本时的一次性搬家
/// （见 LibraryStore.migrateIfNeeded），那之后永远只读本地。
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

/// 显示一张照片（永远从手机本地读，秒开）。
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
