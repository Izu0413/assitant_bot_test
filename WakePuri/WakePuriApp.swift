import SwiftUI

@main
struct WakePuriApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            HomeView()
                .environment(appState)
        }
    }
}
