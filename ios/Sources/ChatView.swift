import SwiftUI

struct ChatView: View {
    @ObservedObject var model: ChatModel
    @FocusState private var focused: Bool

    var body: some View {
        ZStack {
            BreathingBackground().ignoresSafeArea()

            VStack(spacing: 0) {
                if let c = model.crisis {
                    CrisisCard(crisis: c).padding(.horizontal, 16).padding(.top, 8)
                }

                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 14) {
                            if model.messages.isEmpty {
                                GreetingBubble()
                            }
                            ForEach(model.messages) { m in
                                MessageRow(msg: m).id(m.id)
                            }
                            if model.sending {
                                TypingDots().id("typing")
                            }
                            Color.clear.frame(height: 1).id("bottom")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 14)
                    }
                    .scrollDismissesKeyboard(.interactively)
                    .onChange(of: model.messages.count) { _, _ in
                        withAnimation(.easeOut(duration: 0.25)) { proxy.scrollTo("bottom", anchor: .bottom) }
                    }
                    .onChange(of: model.sending) { _, _ in
                        withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                    }
                }

                if let e = model.errorText {
                    Text(e)
                        .font(Theme.small)
                        .foregroundStyle(.red.opacity(0.8))
                        .padding(.horizontal, 16).padding(.bottom, 4)
                }

                InputBar(model: model, focused: $focused)
            }
        }
    }
}

// MARK: - Breathing background (slowly brightening and dimming, like one deep breath after another)

struct BreathingBackground: View {
    @State private var breathe = false
    var body: some View {
        ZStack {
            Theme.bg
            RadialGradient(
                colors: [Theme.sage.opacity(breathe ? 0.22 : 0.10), .clear],
                center: .center,
                startRadius: 40,
                endRadius: breathe ? 520 : 360
            )
        }
        .animation(.easeInOut(duration: 5).repeatForever(autoreverses: true), value: breathe)
        .onAppear { breathe = true }
    }
}

// MARK: - Opening greeting (before anything is said, the AI gently says hello first)

struct GreetingBubble: View {
    var body: some View {
        HStack {
            Text("我在这儿。\n此刻你心里最难受的那一点，能告诉我吗？我们慢慢来。")
                .font(Theme.body)
                .foregroundStyle(Theme.ink)
                .padding(14)
                .background(Color.white.opacity(0.9))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .shadow(color: .black.opacity(0.04), radius: 6, y: 2)
            Spacer(minLength: 40)
        }
    }
}

// MARK: - One message (mine on the right / companion on the left; companion messages can carry a photo on top)

struct MessageRow: View {
    let msg: ChatMsg

    var body: some View {
        if msg.role == "me" {
            HStack {
                Spacer(minLength: 40)
                Text(msg.text)
                    .font(Theme.body)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Theme.sage)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
        } else {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    if let pid = msg.photoId {
                        PhotoView(id: pid)
                    }
                    Text(msg.text)
                        .font(Theme.body)
                        .foregroundStyle(Theme.ink)
                        .padding(14)
                        .background(Color.white.opacity(0.92))
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .shadow(color: .black.opacity(0.04), radius: 6, y: 2)
                    if let t = msg.think {
                        ThinkDisclosure(think: t)   // a gentle tap to see "what it was thinking"
                    }
                }
                Spacer(minLength: 40)
            }
        }
    }
}

struct PhotoView: View {
    let id: String
    var body: some View {
        LocalPhoto(id: id)                          // local-first, opens instantly; downloads from the cloud only the first time
            .frame(maxWidth: 260, maxHeight: 300)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .shadow(color: .black.opacity(0.08), radius: 8, y: 3)
    }
}

// MARK: - Crisis card (pinned to the top when danger is detected)

struct CrisisCard: View {
    let crisis: Crisis
    var who: String {
        let name = crisis.contact_name ?? ""
        let note = crisis.contact_note ?? ""
        if name.isEmpty { return "一个你信任的人" }
        return note.isEmpty ? name : "\(name)（\(note)）"
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("🤍 你不是一个人。此刻，给 \(who) 发一句话或打个电话，好吗？就现在。")
                .font(Theme.body).foregroundStyle(.white)
            if let h = crisis.hotline, !h.isEmpty {
                Text(h).font(Theme.small).foregroundStyle(.white.opacity(0.9))
            }
            Text("我会一直在这儿陪着你，不走。")
                .font(Theme.small).foregroundStyle(.white.opacity(0.9))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.sageDeep)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

// MARK: - "They're typing" three dots

struct TypingDots: View {
    @State private var on = false
    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3) { i in
                Circle().fill(Theme.sage.opacity(0.6))
                    .frame(width: 7, height: 7)
                    .scaleEffect(on ? 1 : 0.5)
                    .animation(.easeInOut(duration: 0.6).repeatForever().delay(Double(i) * 0.2), value: on)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Color.white.opacity(0.8))
        .clipShape(Capsule())
        .onAppear { on = true }
    }
}

// MARK: - Bottom input bar

struct InputBar: View {
    @ObservedObject var model: ChatModel
    var focused: FocusState<Bool>.Binding

    var body: some View {
        HStack(spacing: 10) {
            TextField("把此刻的感受，告诉我……", text: $model.input, axis: .vertical)
                .font(Theme.body)
                .lineLimit(1...4)
                .focused(focused)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Color.white.opacity(0.95))
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                .onSubmit { model.send() }

            Button {
                model.send()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(canSend ? Theme.sage : Theme.sage.opacity(0.35))
            }
            .disabled(!canSend)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    var canSend: Bool {
        !model.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !model.sending
    }
}

// MARK: - "What it was thinking" (expandable; tucked away so it doesn't intrude on the conversation during an episode)

struct ThinkDisclosure: View {
    let think: ThinkInfo
    @State private var open = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) { open.toggle() }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: open ? "chevron.down" : "chevron.right").font(.system(size: 10))
                    Text("它怎么想的").font(Theme.small)
                }
                .foregroundStyle(Theme.sage.opacity(0.85))
            }
            if open {
                VStack(alignment: .leading, spacing: 5) {
                    row("读到的情绪", think.emotionalRead)
                    row("这一步", think.actionCN)
                    row("选这张照片", think.pickReason)
                    row("为什么", think.reasoning)
                }
                .font(Theme.small)
                .padding(11)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.sage.opacity(0.09))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
        }
        .padding(.leading, 2)
    }

    @ViewBuilder
    private func row(_ k: String, _ v: String) -> some View {
        if !v.trimmingCharacters(in: .whitespaces).isEmpty {
            (Text(k + "：").foregroundStyle(Theme.sage) + Text(v).foregroundStyle(Theme.ink.opacity(0.75)))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
