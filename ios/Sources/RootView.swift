import SwiftUI

struct RootView: View {
    @StateObject private var library: LibraryStore
    @StateObject private var model: ChatModel
    @State private var showLibrary = false
    @State private var showHistory = false

    init() {
        let lib = LibraryStore()
        _library = StateObject(wrappedValue: lib)
        _model = StateObject(wrappedValue: ChatModel(library: lib))
    }

    var body: some View {
        NavigationStack {
            ChatView(model: model)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .principal) {
                        Text("🕊️ 我在这儿").font(Theme.title).foregroundStyle(Theme.ink)
                    }
                    ToolbarItem(placement: .topBarLeading) {
                        Button { showHistory = true } label: {
                            Image(systemName: "clock.arrow.circlepath")   // 历史
                        }.tint(Theme.sage)
                    }
                    ToolbarItem(placement: .topBarLeading) {
                        Button { showLibrary = true } label: {
                            Image(systemName: "photo.on.rectangle.angled") // 记忆库
                        }.tint(Theme.sage)
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        if !model.messages.isEmpty {
                            Button("新的一次") { model.reset() }
                                .font(Theme.small)
                                .tint(Theme.sage)
                        }
                    }
                }
                .toolbarBackground(Theme.bg, for: .navigationBar)
                .sheet(isPresented: $showLibrary) { LibraryView().environmentObject(library) }
                .sheet(isPresented: $showHistory) { HistoryView() }
        }
        .tint(Theme.sage)
        // 第一次装上这个版本时，把照片和卡片从旧后端搬回手机。搬完旧服务就能关掉，
        // 照片从此不在任何云上。之后每次启动这里都直接跳过（有个一次性标记）。
        .task { await library.migrateIfNeeded() }
    }
}
