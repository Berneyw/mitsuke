import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as C
import Mitsuke

// The main window: frameless, per-pixel transparent over native Acrylic. Layers, bottom to top:
//   scene  = window tint + stage (page content)            -> sceneTex, refracted by menus and alerts
//   stage  = the pages' scrolling content                  -> stageTex, refracted by the toolbar glass
//   chrome = floating sidebar, toolbars, caption buttons (inside scene, above the stage)
Window {
    id: win
    width: 1020
    height: 720
    minimumWidth: 800
    minimumHeight: 560
    visible: false
    title: "Mitsuke"
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint

    property string page: "lookup"
    property real scrolled: 0                 // scroll offset of the visible page
    // the light every glass surface is lit from; it trails the pointer slightly so highlights glide
    property point pointer: hh.hovered ? hh.point.position : Qt.point(-300, -500)
    Behavior on pointer { enabled: !Theme.reduceMotion && hh.hovered; PropertyAnimation { duration: 140; easing.type: Easing.OutCubic } }
    property alias sceneTex: sceneTex
    property alias sceneItem: scene
    readonly property real contentX: Theme.sidebarWidth + 20

    Binding { target: Theme; property: "settings"; value: App.settings }
    Binding { target: Theme; property: "hasSF"; value: hasSF }
    Connections {
        target: Theme
        function onDarkChanged() { App.setDark(Theme.dark) }
    }
    Component.onCompleted: {
        App.setDark(Theme.dark)
        const last = App.settings.last_page                 // reopen where you left it
        if (["words", "history", "dictionary", "settings"].indexOf(last) >= 0) page = last
    }

    function go(key) { page = key }
    Connections {
        target: App
        function onPageRequested(key) { win.page = key }
        function onLookupRequested(q) { win.page = "lookup"; lookupPage.lookup(q) }
        function onFlash(text) { flashText.show(text) }
    }

    Item {
        id: scene
        anchors.fill: parent

        Rectangle { anchors.fill: parent; color: Theme.windowTint }

        Item {
            id: stage
            x: win.contentX
            width: parent.width - x
            height: parent.height
        }

        // ---------------------------------------------------------------- chrome
        Item {
            id: chrome
            x: win.contentX
            width: parent.width - x
            height: parent.height

            Glass {          // scroll edge: only once content actually passes under the toolbar
                width: parent.width
                height: Theme.toolbarHeight + 8
                opacity: Math.min(1, win.scrolled / 24)
                visible: opacity > 0.01
                radius: 0
                bezel: 1
                refraction: 0
                blur: Theme.reduceTransparency ? 0 : 14
                saturation: 1.3
                specular: 0
                edge: 0
                backdrop: stageTex
                backdropItem: stage
                tint: Qt.rgba(Theme.windowTint.r, Theme.windowTint.g, Theme.windowTint.b, Theme.reduceTransparency ? 1 : 0.8)
                passAlpha: 1
                fadeBottom: 22
            }
            MouseArea {      // empty toolbar space drags the window; double-click maximizes
                width: parent.width; height: Theme.toolbarHeight
                onPressed: win.startSystemMove()
                onDoubleClicked: win.visibility === Window.Maximized ? win.showNormal() : win.showMaximized()
            }

            LookupPage {
                id: lookupPage
                current: win.page === "lookup"
                stage: stage; stageTex: stageTex; trailing: caption.width
            }
            WordsPage {
                id: wordsPage
                current: win.page === "words"
                stage: stage; stageTex: stageTex; trailing: caption.width
            }
            HistoryPage {
                id: historyPage
                current: win.page === "history"
                stage: stage; stageTex: stageTex; trailing: caption.width
            }
            DictionaryPage {
                current: win.page === "dictionary"
                stage: stage; stageTex: stageTex; trailing: caption.width
            }
            SettingsPage {
                id: settingsPage
                current: win.page === "settings"
                stage: stage; stageTex: stageTex; trailing: caption.width
            }

            CaptionButtons {
                id: caption
                window: win
                anchors.right: parent.right; anchors.rightMargin: 8
                y: 8
            }
        }

        Sidebar {
            x: 10; y: 10
            width: Theme.sidebarWidth
            height: parent.height - 20
            page: win.page
            onNavigate: (k) => win.page = k
            onDragStarted: win.startSystemMove()
        }

        Rectangle {        // transient confirmation, bottom centre (“Saved to My Words.”)
            id: flashText
            property string text: ""
            function show(t) { text = t; opacity = 1; hideTimer.restart() }
            anchors.horizontalCenter: stage.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 22
            width: ft.implicitWidth + 30; height: 34
            radius: 17
            color: Theme.dark ? Qt.rgba(0.22, 0.22, 0.25, 0.92) : Qt.rgba(1, 1, 1, 0.94)
            border.width: 1; border.color: Theme.edge
            opacity: 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
            Label { id: ft; anchors.centerIn: parent; text: flashText.text; textStyle: "callout"; font.weight: Font.Medium }
            Timer { id: hideTimer; interval: 2600; onTriggered: flashText.opacity = 0 }
        }
    }

    ShaderEffectSource { id: stageTex; sourceItem: stage; live: true; mipmap: true; visible: false; hideSource: false }
    ShaderEffectSource { id: sceneTex; sourceItem: scene; live: true; mipmap: true; visible: false; hideSource: false }

    HoverHandler { id: hh }

    AlertPopup { id: alert }
    function ask(title, message, buttons, cb, destructive) { alert.ask(title, message, buttons, cb, destructive) }

    Shortcut { sequence: "Ctrl+1"; onActivated: win.page = "lookup" }
    Shortcut { sequence: "Ctrl+2"; onActivated: win.page = "words" }
    Shortcut { sequence: "Ctrl+3"; onActivated: win.page = "history" }
    Shortcut { sequence: "Ctrl+4"; onActivated: win.page = "dictionary" }
    Shortcut { sequence: "Ctrl+5"; onActivated: win.page = "settings" }
    Shortcut { sequence: "Ctrl+,"; onActivated: win.page = "settings" }
    Shortcut { sequences: ["Ctrl+F", "Ctrl+L"]; onActivated: { if (win.page === "settings") settingsPage.focusSearch(); else { win.page = "lookup"; lookupPage.focusSearch() } } }
    Shortcut { sequence: "Ctrl+S"; enabled: win.page === "lookup"; onActivated: App.toggleSave() }
    Shortcut { sequence: "Escape"; enabled: !alert.opened; onActivated: App.hideWindow() }

    onPageChanged: { App.rememberPage(page); if (page === "lookup") lookupPage.focusSearch() }
    onActiveChanged: if (active && page === "lookup") lookupPage.focusSearch()
}
