import QtQuick
import QtQuick.Window
import QtQuick.Dialogs

// Settings, grouped like System Settings, searchable. Sliders apply live; the card preview shows the in-game
// card's Liquid Glass with the current values as you drag.
Page {
    id: sp
    key: "settings"
    title: "Settings"
    property string query: ""
    function focusSearch() { search.focusField(true) }

    readonly property var s: App.settings
    readonly property bool glassOn: !!s.glass && !s.reduce_transparency

    actions: [
        TextBox {
            id: search
            search: true
            width: 240
            placeholder: "Search settings"
            backdrop: sp.stageTex; backdropItem: sp.stage
            onEdited: (t) => { sp.query = t; scroller.toTop() }
        }
    ]

    FileDialog {
        id: exportDlg
        title: "Export Settings"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["Settings (*.json)"]
        onAccepted: App.flash(App.exportSettings(selectedFile))
    }
    FileDialog {
        id: importDlg
        title: "Import Settings"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Settings (*.json)"]
        onAccepted: App.flash(App.importSettings(selectedFile))
    }

    body: Scroller {
        id: scroller
        objectName: "settingsScroll"
        spacing: 22

        SettingsGroup {
            id: gGeneral
            title: "General"; icon: "gear"; iconColor: "#8e8e93"; query: sp.query
            SettingRow {
                title: "Appearance"; keywords: "theme dark light mode"
                GlassSegmented {
                    width: 230
                    options: [{ label: "System", value: "system" }, { label: "Light", value: "light" }, { label: "Dark", value: "dark" }]
                    value: sp.s.appearance
                    onSelected: (v) => App.set("appearance", v)
                }
            }
            SettingRow {
                title: "Window material"
                desc: "Glass blurs what’s behind the window; Mica tints it with your wallpaper."
                keywords: "acrylic mica translucent liquid glass"
                PopupButton {
                    minWidth: 120
                    options: [{ label: "Glass", value: "acrylic", desc: "Blurs the windows and desktop behind Mitsuke." },
                              { label: "Mica", value: "mica", desc: "A calm tint taken from your wallpaper." },
                              { label: "Solid", value: "solid", desc: "No translucency." }]
                    value: sp.s.window_material
                    onSelected: (v) => App.set("window_material", v)
                }
            }
            SettingRow {
                title: "Open at Windows startup"; desc: "Mitsuke starts quietly in the tray."; keywords: "autostart login boot"
                GlassSwitch { checked: !!sp.s.autostart; onToggled: (v) => App.set("autostart", v) }
            }
        }

        SettingsGroup {
            id: gScan
            title: "Scanning"; icon: "viewfinder"; iconColor: "#0a84ff"; query: sp.query
            subtitle: "How Mitsuke reads the word under your cursor in the game."
            SettingRow {
                title: "Scan key"; desc: "Hold this key and point at a word."; keywords: "trigger hotkey modifier"
                PopupButton {
                    options: [{ label: "Shift", value: "shift" }, { label: "Ctrl", value: "ctrl" }, { label: "Alt", value: "alt" }]
                    value: sp.s.key
                    onSelected: (v) => App.set("key", v)
                }
            }
            SettingRow {
                title: "Delay before scanning"; desc: "Keeps the card from appearing when you press the key briefly."; keywords: "hold delay"
                SliderSetting { key: "hold_ms"; from: 0; to: 600; stepSize: 10; unit: "ms" }
            }
            SettingRow {
                title: "Recognition"; keywords: "ocr quality accuracy"
                PopupButton {
                    minWidth: 130
                    options: [{ label: "Fast", value: 1, desc: "Quickest. Best for large, clear text." },
                              { label: "Balanced", value: 2, desc: "Recommended for most games." },
                              { label: "Precise", value: 3, desc: "Reads small fonts reliably; a little slower." }]
                    value: sp.s.scale
                    onSelected: (v) => App.set("scale", v)
                }
            }
            SettingRow {
                title: "Reading area"
                desc: "How much of the line around the cursor is read. A wider area finds separable verbs at the end of long sentences."
                keywords: "capture width ocr"
                SliderSetting { key: "capture_width"; from: 600; to: 2400; stepSize: 100; unit: "px" }
            }
            SettingRow {
                title: "Pin with a double-tap"; desc: "Tap the scan key twice quickly to keep the card open: scroll it, drag it, save the word."
                keywords: "pin keep sticky"
                GlassSwitch { checked: !!sp.s.pin_double_tap; onToggled: (v) => App.set("pin_double_tap", v) }
            }
            SettingRow {
                title: "Highlight the word being read"
                desc: "Tints the word under the cursor and outlines words linked to it, like the particle of a separable verb."
                keywords: "highlight selection mark"
                GlassSwitch { checked: !!sp.s.highlight; onToggled: (v) => App.set("highlight", v) }
            }
            SettingRow {
                title: "Show the reading area"; desc: "Outlines the strip of the screen that is read. Useful when a word isn’t found."
                keywords: "debug capture area ocr"
                GlassSwitch { checked: !!sp.s.highlight_area; onToggled: (v) => App.set("highlight_area", v) }
            }
        }

        SettingsGroup {
            id: gCard
            title: "Word Card"; icon: "textcard"; iconColor: "#ff9f0a"; query: sp.query
            subtitle: "What appears next to the word while you hold the scan key."
            SettingRow {
                title: "Preview"; desc: "Updates live while you change the settings below and under Liquid Glass."
                keywords: "card example sample glass"; wide: true
                CardPreview { width: Math.min(560, sp.width - 110) }
            }
            SettingRow {
                title: "Text size"; keywords: "font"
                SliderSetting { key: "font_size"; from: 9; to: 16; stepSize: 1; unit: "pt" }
            }
            SettingRow {
                title: "Card width"; keywords: "size"
                SliderSetting { key: "card_width"; from: 360; to: 640; stepSize: 10; unit: "px" }
            }
            SettingRow {
                title: "Entries per card"; desc: "Matching words, phrases and separable verbs."; keywords: "results"
                PopupButton {
                    minWidth: 64
                    options: [1, 2, 3, 4, 5, 6].map((n) => ({ label: String(n), value: n }))
                    value: sp.s.card_entries
                    onSelected: (v) => App.set("card_entries", v)
                }
            }
            SettingRow {
                title: "Meanings per entry"; keywords: "senses definitions"
                PopupButton {
                    minWidth: 64
                    options: [1, 2, 3, 4, 5, 6].map((n) => ({ label: String(n), value: n }))
                    value: sp.s.card_senses
                    onSelected: (v) => App.set("card_senses", v)
                }
            }
            SettingRow {
                title: "Example sentences"
                GlassSwitch { checked: !!sp.s.card_examples; onToggled: (v) => App.set("card_examples", v) }
            }
            SettingRow {
                title: "Position"
                PopupButton {
                    minWidth: 150
                    options: [{ label: "Below the word", value: "below" }, { label: "Above the word", value: "above" }]
                    value: sp.s.card_position
                    onSelected: (v) => App.set("card_position", v)
                }
            }
        }

        SettingsGroup {
            id: gPron
            title: "Pronunciation"; icon: "speaker"; iconColor: "#ff375f"; query: sp.query
            subtitle: "Listen to words with the speaker button on the cards."
            SettingRow {
                title: "Voice"; keywords: "audio sound recording speech tts"
                PopupButton {
                    minWidth: 170
                    options: [{ label: "Native speakers", value: "recordings", desc: "Recordings from Wiktionary; the Windows voice when there's none." },
                              { label: "Windows voice", value: "voice", desc: "Always the German voice built into Windows." }]
                    value: sp.s.pron_source
                    onSelected: (v) => App.set("pron_source", v)
                }
            }
            SettingRow {
                title: "Show the pronunciation"; desc: "The IPA transcription next to the word, like [haʊ̯s]."
                keywords: "ipa phonetic transcription"
                GlassSwitch { checked: sp.s.pron_ipa !== false; onToggled: (v) => App.set("pron_ipa", v) }
            }
            SettingRow {
                title: "Speak words in the game"; desc: "Says the word aloud when its card appears."
                keywords: "autoplay audio automatic"
                GlassSwitch { checked: !!sp.s.pron_autoplay; onToggled: (v) => App.set("pron_autoplay", v) }
            }
            SettingRow {
                title: "Try it"; desc: App.state.voiceAvailable ? "“Abschlussball” — no recording exists, so the Windows voice reads it."
                                                               : "No German Windows voice is installed: only recordings play."
                keywords: "test listen"
                Row {
                    spacing: 8
                    SpeakButton { word: "Haus"; audio: [{ f: "De-Haus.ogg", r: "" }] }
                    Label { text: "Haus"; textStyle: "body"; anchors.verticalCenter: parent.verticalCenter }
                    Item { width: 8; height: 1 }
                    SpeakButton { word: "Abschlussball"; audio: [] }
                    Label { text: "Abschlussball"; textStyle: "body"; anchors.verticalCenter: parent.verticalCenter }
                }
            }
        }

        SettingsGroup {
            id: gGlass
            title: "Liquid Glass"; icon: "drop"; iconColor: "#32ade6"; query: sp.query
            subtitle: "The translucent material of the in-game card."
            footer: "Text on glass always keeps at least 4.5:1 contrast — over bright scenes the card becomes more solid automatically."
            SettingRow {
                title: "Preview"; keywords: "card example sample glass style"; wide: true
                CardPreview { width: Math.min(560, sp.width - 110) }
            }
            SettingRow {
                title: "Liquid Glass"; desc: "Blurs, refracts and reflects the game behind the card."; keywords: "blur transparent"
                GlassSwitch { checked: !!sp.s.glass; onToggled: (v) => App.set("glass", v) }
            }
            SettingRow {
                title: "Style"; active: sp.glassOn
                GlassSegmented {
                    width: 230
                    options: [{ label: "Glass", value: "glass" }, { label: "Clear", value: "clear" }, { label: "Tinted", value: "tinted" }]
                    value: sp.s.glass_style
                    onSelected: (v) => App.set("glass_style", v)
                }
            }
            SettingRow {
                title: "Transparency"; keywords: "opacity"; active: sp.glassOn
                SliderSetting { key: "glass_transparency"; from: 0; to: 100; stepSize: 1; unit: "%" }
            }
            SettingRow {
                title: "Thickness"; desc: "Thicker glass blurs and bends the game more."; keywords: "blur refraction"; active: sp.glassOn
                GlassSegmented {
                    width: 230
                    options: [{ label: "Thin", value: "thin" }, { label: "Regular", value: "regular" }, { label: "Thick", value: "thick" }]
                    value: sp.s.glass_thickness
                    onSelected: (v) => App.set("glass_thickness", v)
                }
            }
            SettingRow {
                title: "Light highlights"; desc: "Specular light along the rim that follows the pointer."; keywords: "specular"; active: sp.glassOn
                GlassSwitch { checked: !!sp.s.glass_highlight; onToggled: (v) => App.set("glass_highlight", v) }
            }
        }

        SettingsGroup {
            id: gAcc
            title: "Accessibility"; icon: "accessibility"; iconColor: "#0a84ff"; query: sp.query
            SettingRow {
                title: "Reduce transparency"; desc: "Makes the window, the menus and the word card solid."
                GlassSwitch { checked: !!sp.s.reduce_transparency; onToggled: (v) => App.set("reduce_transparency", v) }
            }
            SettingRow {
                title: "Increase contrast"; desc: "Stronger text colours and clear outlines on glass."
                GlassSwitch { checked: !!sp.s.increase_contrast; onToggled: (v) => App.set("increase_contrast", v) }
            }
            SettingRow {
                title: "Reduce motion"; desc: "Turns off springs, fades and sliding selections."; keywords: "animation"
                GlassSwitch { checked: !!sp.s.reduce_motion; onToggled: (v) => App.set("reduce_motion", v) }
            }
        }

        SettingsGroup {
            id: gUpd
            title: "Updates"; icon: "arrow.clockwise"; iconColor: "#30d158"; query: sp.query
            footer: "New versions come from GitHub Releases and are verified with a SHA-256 checksum. Your settings, dictionary and saved words are kept."
            SettingRow {
                title: "Check for updates automatically"; desc: "Once a day, quietly, when Mitsuke starts."; keywords: "auto update version"
                GlassSwitch { checked: !!sp.s.update_check; onToggled: (v) => App.set("update_check", v) }
            }
            SettingRow {
                title: "Update source"; desc: "The GitHub repository that publishes Mitsuke, as owner/name."; keywords: "github repository"
                TextBox {
                    id: repo
                    width: 220
                    placeholder: "owner/repository"
                    text: sp.s.update_repo || ""
                    onSubmitted: (t) => App.set("update_repo", t.trim())
                    Connections {
                        target: repo.input
                        function onActiveFocusChanged() { if (!repo.input.activeFocus) App.set("update_repo", repo.text.trim()) }
                    }
                }
            }
            SettingRow {
                title: "Version"; desc: (App.state.update || {}).text || ""; keywords: "update version"
                GlassButton {
                    small: true
                    text: (App.state.update || {}).button || "Check Now"
                    kind: (App.state.update || {}).primary ? "primary" : "secondary"
                    enabled: !!(App.state.update || {}).enabled
                    onClicked: App.updateAction()
                }
            }
        }

        SettingsGroup {
            id: gData
            title: "Data"; icon: "folder"; iconColor: "#8e8e93"; query: sp.query
            SettingRow {
                title: "Data folder"; desc: "Dictionary, settings, saved words and log."; keywords: "files"
                GlassButton { small: true; text: "Open"; onClicked: App.openDataDir() }
            }
            SettingRow {
                title: "Log file"; desc: "Useful when something doesn’t work."
                GlassButton { small: true; text: "Show"; onClicked: if (!App.openLog()) App.flash("No log file yet.") }
            }
            SettingRow {
                title: "Export settings"; keywords: "backup"
                GlassButton { small: true; text: "Export…"; onClicked: exportDlg.open() }
            }
            SettingRow {
                title: "Import settings"; keywords: "restore"
                GlassButton { small: true; text: "Import…"; onClicked: importDlg.open() }
            }
            SettingRow {
                title: "Reset all settings"; desc: "Restores every setting to its default."; keywords: "defaults"
                GlassButton {
                    small: true; text: "Reset…"; kind: "destructive"
                    onClicked: sp.Window.window.ask("Reset all settings?", "Every setting returns to its default. Your dictionary and saved words are kept.",
                                                    [{ label: "Reset", value: "reset" }, { label: "Cancel", value: "no" }],
                                                    (v) => { if (v === "reset") App.resetSettings() }, true)
                }
            }
        }

        Label {
            visible: sp.query !== "" && gGeneral.shown + gScan.shown + gCard.shown + gPron.shown + gGlass.shown + gAcc.shown + gUpd.shown + gData.shown === 0
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            topPadding: 40
            text: "No settings match “" + sp.query + "”."
            textStyle: "callout"; color: Theme.label3
        }
        Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "Mitsuke " + App.version
            textStyle: "footnote"; color: Theme.label4
        }
    }
}
