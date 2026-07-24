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
                            Image(systemName: "clock.arrow.circlepath")   // history
                        }.tint(Theme.sage)
                    }
                    ToolbarItem(placement: .topBarLeading) {
                        Button { showLibrary = true } label: {
                            Image(systemName: "photo.on.rectangle.angled") // memory library
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
        // On the first launch of this version, move photos and cards from the old backend back to the phone.
        // Once done, the old service can be shut down and the photos are on no cloud from then on.
        // Every later launch skips straight past this (there's a one-time flag).
        .task { await library.migrateIfNeeded() }
    }
}
