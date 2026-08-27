import Cocoa
import UserNotifications

final class NotificationDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    private let notificationLifetime: TimeInterval = 6
    private let notificationTitle = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "Spotify Like"
    private let notificationBody = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "Ready"

    func applicationDidFinishLaunching(_ notification: Notification) {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.getNotificationSettings { settings in
            self.record("authorization=\(settings.authorizationStatus.rawValue)")
            switch settings.authorizationStatus {
            case .notDetermined:
                DispatchQueue.main.async {
                    NSApp.activate(ignoringOtherApps: true)
                }
                center.requestAuthorization(options: [.alert]) { granted, error in
                    if granted {
                        self.record("authorization=2")
                        self.deliver(using: center)
                    } else {
                        self.record("authorization=1")
                        self.finish(error?.localizedDescription ?? "Notifications were not allowed.")
                    }
                }
            case .authorized, .provisional, .ephemeral:
                self.deliver(using: center)
            case .denied:
                self.finish("Notifications are disabled in System Settings.")
            @unknown default:
                self.finish("Unknown notification permission state.")
            }
        }
    }

    private func deliver(using center: UNUserNotificationCenter) {
        let content = UNMutableNotificationContent()
        content.title = notificationTitle
        content.body = notificationBody
        let identifier = UUID().uuidString
        let request = UNNotificationRequest(
            identifier: identifier,
            content: content,
            trigger: nil
        )
        center.add(request) { error in
            if let error = error {
                self.finish(error.localizedDescription)
                return
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + self.notificationLifetime) {
                center.removeDeliveredNotifications(withIdentifiers: [identifier])
                center.removePendingNotificationRequests(withIdentifiers: [identifier])
                NSApp.terminate(nil)
            }
        }
    }

    private func record(_ message: String) {
        let directory = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/state/spotify-like-hotkey", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true
        )
        try? (message + "\n").write(
            to: directory.appendingPathComponent("notifier-status.txt"),
            atomically: true,
            encoding: .utf8
        )
    }

    private func finish(_ error: String?) {
        if let error = error {
            FileHandle.standardError.write(Data((error + "\n").utf8))
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            NSApp.terminate(nil)
        }
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list])
    }
}

let app = NSApplication.shared
let delegate = NotificationDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
