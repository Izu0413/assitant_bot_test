import Foundation
import Observation

@Observable
final class AppState {
    /// MCPeerID の表示名は UTF-8 で 63 バイトまで。日本語(1文字3バイト)でも収まり、
    /// メンバー欄のアイコン下にも表示しきれる長さに抑える。
    static let nicknameMaxLength = 12

    private static let nicknameDefaultsKey = "nickname"

    var nickname: String {
        didSet {
            UserDefaults.standard.set(nickname, forKey: Self.nicknameDefaultsKey)
        }
    }

    var trimmedNickname: String {
        nickname.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var hasNickname: Bool {
        !trimmedNickname.isEmpty
    }

    init() {
        nickname = UserDefaults.standard.string(forKey: Self.nicknameDefaultsKey) ?? ""
    }
}
