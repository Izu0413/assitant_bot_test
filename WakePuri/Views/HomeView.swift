import SwiftUI

struct HomeView: View {
    @Environment(AppState.self) private var appState

    enum Route: Hashable {
        case shoot
        case receive
    }

    var body: some View {
        @Bindable var appState = appState

        NavigationStack {
            VStack(spacing: 32) {
                Spacer()

                VStack(spacing: 8) {
                    Text("わけプリ")
                        .font(.system(size: 44, weight: .heavy, design: .rounded))
                        .foregroundStyle(.tint)
                    Text("撮って、切って、わけあおう")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("ニックネーム")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("みんなに表示される名前", text: $appState.nickname)
                        .textFieldStyle(.roundedBorder)
                        .submitLabel(.done)
                        .onChange(of: appState.nickname) { _, newValue in
                            if newValue.count > AppState.nicknameMaxLength {
                                appState.nickname = String(newValue.prefix(AppState.nicknameMaxLength))
                            }
                        }
                    if !appState.hasNickname {
                        Text("ニックネームを入れると始められます")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 32)

                VStack(spacing: 16) {
                    NavigationLink(value: Route.shoot) {
                        Label("撮る", systemImage: "camera.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    NavigationLink(value: Route.receive) {
                        Label("受け取る", systemImage: "tray.and.arrow.down.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
                .controlSize(.large)
                .disabled(!appState.hasNickname)
                .padding(.horizontal, 32)

                Spacer()
            }
            .navigationDestination(for: Route.self) { route in
                // 各画面はタスク5(撮る→切る)とタスク6(受け取る)で差し替える
                switch route {
                case .shoot:
                    UnderConstructionView(title: "撮る")
                case .receive:
                    UnderConstructionView(title: "受け取る")
                }
            }
        }
    }
}

/// 後続タスクで本物の画面に差し替えるまでの仮画面
private struct UnderConstructionView: View {
    let title: String

    var body: some View {
        ContentUnavailableView(title, systemImage: "hammer", description: Text("この画面はこれから作ります"))
            .navigationTitle(title)
    }
}

#Preview {
    HomeView()
        .environment(AppState())
}
