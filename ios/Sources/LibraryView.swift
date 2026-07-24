import SwiftUI

/// The memory library: the treasured photos you've saved. **All of them live on this phone**; the server has not a single one.
struct LibraryView: View {
    @EnvironmentObject private var library: LibraryStore
    @Environment(\.dismiss) private var dismiss
    @State private var showAdd = false
    @State private var showContact = false

    private let cols = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                if library.migrating {
                    VStack(spacing: 10) {
                        ProgressView().tint(Theme.sage)
                        Text("正在把照片搬回你的手机…").font(Theme.small).foregroundStyle(.secondary)
                    }
                } else if library.isEmpty {
                    VStack(spacing: 12) {
                        Text("记忆库还是空的").font(Theme.body).foregroundStyle(Theme.ink)
                        Text("加几张让你觉得温暖、安全的照片。它们只会存在这台手机上。")
                            .font(Theme.small).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                        Button("加一张照片") { showAdd = true }
                            .font(Theme.body).tint(Theme.sage)
                    }
                    .padding(30)
                } else {
                    ScrollView {
                        LazyVGrid(columns: cols, spacing: 10) {
                            ForEach(library.cards) { m in
                                VStack(alignment: .leading, spacing: 4) {
                                    PhotoView(id: m.id)
                                        .frame(maxWidth: .infinity)
                                    Text(m.title)
                                        .font(Theme.small)
                                        .foregroundStyle(Theme.ink)
                                        .lineLimit(1)
                                }
                                .contextMenu {
                                    Button("删掉这张", role: .destructive) { library.delete(m.id) }
                                }
                            }
                        }
                        .padding(14)
                    }
                }
            }
            .navigationTitle("你的记忆库")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showContact = true } label: {
                        Image(systemName: "heart.text.square")     // trusted contact
                    }.tint(Theme.sage)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showAdd = true } label: { Image(systemName: "plus") }.tint(Theme.sage)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }.tint(Theme.sage)
                }
            }
            .sheet(isPresented: $showAdd) { AddMemoryView().environmentObject(library) }
            .sheet(isPresented: $showContact) { ContactView() }
        }
    }
}

/// Trusted contact: when an episode turns dangerous, the agent will put this person right in front of you. Stored only on this phone.
struct ContactView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ContactStore.name
    @State private var note = ContactStore.note

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("名字", text: $name)
                    TextField("怎么联系 ta（电话 / 微信 / 备注）", text: $note)
                } header: {
                    Text("可信联系人")
                } footer: {
                    Text("如果 agent 察觉到你有危险，它会把这个人端到你面前，鼓励你现在就联系 ta。不填也可以，那样它会给你一条通用的求助热线。这些字只存在这台手机上。")
                }
            }
            .navigationTitle("可信联系人")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("存好") {
                        ContactStore.name = name
                        ContactStore.note = note
                        dismiss()
                    }.tint(Theme.sage)
                }
            }
        }
    }
}
