import SwiftUI
import PhotosUI

/// 从相册加一张照片进记忆库。
///
/// 流程：挑照片 → 送去后端让视觉模型起草一张卡片（照片只穿过内存，不落盘）
///      → 你补上只有你知道的部分（时间/和谁/发生了什么）→ 存在这台手机上。
struct AddMemoryView: View {
    @EnvironmentObject private var library: LibraryStore
    @Environment(\.dismiss) private var dismiss

    @State private var pick: PhotosPickerItem?
    @State private var image: UIImage?
    @State private var jpeg: Data?
    @State private var card: MemoryCard?
    @State private var drafting = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                if drafting {
                    VStack(spacing: 10) {
                        ProgressView().tint(Theme.sage)
                        Text("正在看这张照片…").font(Theme.small).foregroundStyle(.secondary)
                    }
                } else if let card {
                    editor(card)
                } else {
                    picker
                }
            }
            .navigationTitle("加一张回忆")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("取消") { dismiss() }.tint(Theme.sage)
                }
            }
        }
    }

    // MARK: - 选照片

    private var picker: some View {
        VStack(spacing: 16) {
            PhotosPicker(selection: $pick, matching: .images, photoLibrary: .shared()) {
                VStack(spacing: 8) {
                    Image(systemName: "photo.badge.plus").font(.system(size: 42)).foregroundStyle(Theme.sage)
                    Text("从相册挑一张").font(Theme.body).foregroundStyle(Theme.ink)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 40)
                .background(Theme.sage.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            Text("挑一张让你觉得温暖、安全的照片。它会存在这台手机上；后端只会看它一眼来起草卡片，不会留下任何副本。")
                .font(Theme.small).foregroundStyle(.secondary).multilineTextAlignment(.center)
            if let error {
                Text(error).font(Theme.small).foregroundStyle(.red)
            }
            Spacer()
        }
        .padding(20)
        .onChange(of: pick) { _, item in
            guard let item else { return }
            Task { await load(item) }
        }
    }

    private func load(_ item: PhotosPickerItem) async {
        error = nil
        guard let data = try? await item.loadTransferable(type: Data.self),
              let ui = UIImage(data: data) else {
            error = "这张照片读不出来，换一张试试"
            return
        }
        image = ui
        let small = ui.jpegShrunk(maxSide: 1200)      // 存在手机上的那份
        jpeg = small

        drafting = true
        do {
            var draft = try await API.ingest(imageData: ui.jpegShrunk(maxSide: 1024) ?? small ?? data)
            draft.id = UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(8).lowercased()
            card = draft
        } catch {
            // 起草失败也别卡住她——给一张空卡片，她自己填
            var blank = MemoryCard(id: UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(8).lowercased())
            blank.title = ""
            card = blank
            self.error = "没看成图（\(error.localizedDescription)），你可以自己写"
        }
        drafting = false
    }

    // MARK: - 补充卡片

    private func editor(_ c: MemoryCard) -> some View {
        let binding = Binding<MemoryCard>(get: { card ?? c }, set: { card = $0 })
        return Form {
            if let image {
                Section {
                    Image(uiImage: image).resizable().scaledToFit()
                        .frame(maxHeight: 220)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
            Section {
                TextField("小标题", text: binding.title)
            } footer: {
                Text("下面这些是视觉模型起草的。写着「（请你补充）」的地方只有你知道 —— 补上去，agent 陪你的时候会用到。")
            }
            Section("只有你知道的") {
                TextField("在哪", text: binding.whereText)
                TextField("什么时候", text: binding.when)
                TextField("和谁在一起", text: binding.who)
                TextField("发生了什么", text: binding.what_happened)
            }
            Section("那天的感觉") {
                TextField("看到什么", text: binding.see)
                TextField("听到什么", text: binding.hear)
                TextField("摸到 / 身体的感觉", text: binding.touch)
                TextField("气味 / 味道", text: binding.smell_taste)
                TextField("天气 / 温度", text: binding.weather_temp)
                TextField("吃了什么", text: binding.food)
                TextField("当时的心情", text: binding.emotion)
            }
            Section {
                Button("存进记忆库") { save() }
                    .disabled(jpeg == nil)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.bg)
    }

    private func save() {
        guard let c = card, let data = jpeg else { return }
        library.add(c, photo: data)
        dismiss()
    }
}

extension UIImage {
    /// 缩到最长边不超过 maxSide 的 JPEG（手机原图动辄几 MB，没必要）。
    func jpegShrunk(maxSide: CGFloat, quality: CGFloat = 0.85) -> Data? {
        let longest = max(size.width, size.height)
        guard longest > 0 else { return nil }
        let scale = min(1, maxSide / longest)
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let r = UIGraphicsImageRenderer(size: target)
        let img = r.image { _ in draw(in: CGRect(origin: .zero, size: target)) }
        return img.jpegData(compressionQuality: quality)
    }
}
