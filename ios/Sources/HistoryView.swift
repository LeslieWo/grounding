import SwiftUI

/// History: every time you walked yourself through it (all stored locally on the phone).
struct HistoryView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var records: [SessionRecord] = []

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.bg.ignoresSafeArea()
                if records.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.system(size: 42)).foregroundStyle(Theme.sage.opacity(0.5))
                        Text("还没有历史。\n你陪自己走过的每一次，都会留在这里。")
                            .font(Theme.body).foregroundStyle(Theme.ink.opacity(0.7))
                            .multilineTextAlignment(.center)
                    }.padding()
                } else {
                    List {
                        ForEach(records) { r in
                            NavigationLink { SessionDetailView(record: r) } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(dateStr(r.date)).font(Theme.small).foregroundStyle(Theme.sage)
                                    Text(r.firstUser).font(Theme.body).foregroundStyle(Theme.ink).lineLimit(2)
                                    Text("陪你聊了 \(r.rounds) 轮").font(Theme.small).foregroundStyle(Theme.ink.opacity(0.5))
                                }.padding(.vertical, 4)
                            }
                            .listRowBackground(Color.white.opacity(0.6))
                        }
                        .onDelete { idx in
                            idx.map { records[$0].id }.forEach(HistoryStore.delete)
                            records = HistoryStore.load()
                        }
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("你走过的每一次")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }.tint(Theme.sage)
                }
            }
        }
        .onAppear { records = HistoryStore.load() }
    }

    private func dateStr(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.dateFormat = "M月d日 HH:mm"
        return f.string(from: d)
    }
}

/// Look back at a past conversation (read-only, reusing the chat bubbles).
struct SessionDetailView: View {
    let record: SessionRecord
    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(record.messages) { m in MessageRow(msg: m) }
                }
                .padding(16)
            }
        }
        .navigationTitle("回看")
        .navigationBarTitleDisplayMode(.inline)
    }
}
