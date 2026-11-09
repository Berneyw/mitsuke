pragma Singleton
import QtQuick

// SF Symbols–style line icons on a 24×24 grid (stroke icons, rounded caps). Generated shapes (star, gear)
// are computed once so their geometry is exact.
QtObject {
    function _star(r1, r2) {
        let d = ""
        for (let i = 0; i < 10; ++i) {
            const a = -Math.PI / 2 + i * Math.PI / 5
            const r = i % 2 ? r2 : r1
            d += (i ? "L" : "M") + (12 + r * Math.cos(a)).toFixed(2) + " " + (12.6 + r * Math.sin(a)).toFixed(2)
        }
        return d + "Z"
    }
    function _gear() {
        const teeth = 8, ro = 9.2, ri = 7.0
        let d = ""
        for (let i = 0; i < teeth; ++i) {
            const a0 = (i / teeth) * 2 * Math.PI
            const w = Math.PI / teeth
            const pts = [[ri, a0 - w * 0.62], [ro, a0 - w * 0.36], [ro, a0 + w * 0.36], [ri, a0 + w * 0.62]]
            for (let k = 0; k < pts.length; ++k) {
                const p = pts[k]
                d += ((i === 0 && k === 0) ? "M" : "L") + (12 + p[0] * Math.cos(p[1])).toFixed(2) + " "
                     + (12 + p[0] * Math.sin(p[1])).toFixed(2)
            }
        }
        return d + "Z M12 9a3 3 0 1 0 0.01 0Z"
    }
    readonly property var paths: ({
        "search": "M10.5 4a6.5 6.5 0 1 0 0.01 0Z M15.4 15.4L20 20",
        "book": "M3.5 5.5C3.5 4.7 4.2 4 5 4H9.5c1.4 0 2.5 1.1 2.5 2.5V20c0-1.1-.9-2-2-2H3.5Z M20.5 5.5c0-.8-.7-1.5-1.5-1.5H14.5c-1.4 0-2.5 1.1-2.5 2.5V20c0-1.1.9-2 2-2h6.5Z",
        "gear": _gear(),
        "star": _star(8.6, 3.9),
        "xmark": "M6.5 6.5L17.5 17.5 M17.5 6.5L6.5 17.5",
        "chevron.updown": "M8.5 9.5L12 6L15.5 9.5 M8.5 14.5L12 18L15.5 14.5",
        "chevron.down": "M6.5 9.5L12 15L17.5 9.5",
        "chevron.right": "M9.5 6L15.5 12L9.5 18",
        "checkmark": "M5.5 12.5L10 17L18.5 7.5",
        "warning": "M12 4L21 19.5H3Z M12 10V14 M12 16.9V17",
        "text.magnifyingglass": "M3 6.5H13 M3 11H8.5 M3 15.5H7.5 M15.5 9a4 4 0 1 0 0.01 0Z M18.5 16L21.5 19",
        "copy": "M9 9h9.5a1.5 1.5 0 0 1 1.5 1.5V19a1.5 1.5 0 0 1-1.5 1.5H10.5A1.5 1.5 0 0 1 9 19Z M15.5 9V5.5A1.5 1.5 0 0 0 14 4H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5H9",
        "open": "M14 4.5h5.5V10 M19.5 4.5L11 13 M17.5 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8.5a2 2 0 0 1 2-2h4",
        "pin": "M14.5 3.5l6 6 M17.5 6.5l-4.5 4.5l-4.5-1l-2.5 2.5l7 7l2.5-2.5l-1-4.5l4.5-4.5 M9.5 14.5L4 20",
        "export": "M12 3.5V15 M8 7.5L12 3.5L16 7.5 M8.5 10.5H6.5a2 2 0 0 0-2 2V18.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V12.5a2 2 0 0 0-2-2h-2",
        "trash": "M4.5 7H19.5 M9.5 7V4.5h5V7 M6.5 7l.9 11.8A2 2 0 0 0 9.4 20.5h5.2a2 2 0 0 0 2-1.7L17.5 7 M10 10.5v6 M14 10.5v6",
        "minimize": "M6 12H18",
        "maximize": "M6.5 6.5H17.5V17.5H6.5Z",
        "restore": "M8.5 8.5H17.5V17.5H8.5Z M6.5 15V6.5H15",
        "viewfinder": "M4 8.5V6a2 2 0 0 1 2-2h2.5 M15.5 4H18a2 2 0 0 1 2 2v2.5 M20 15.5V18a2 2 0 0 1-2 2h-2.5 M8.5 20H6a2 2 0 0 1-2-2v-2.5 M8.5 12H15.5",
        "textcard": "M4 5.5h16v13H4Z M7.5 9.5h9 M7.5 13h5.5",
        "drop": "M12 3.5C12 3.5 5.5 10.6 5.5 14.6a6.5 6.5 0 0 0 13 0C18.5 10.6 12 3.5 12 3.5Z",
        "accessibility": "M12 2.8a9.2 9.2 0 1 0 0.01 0Z M12 6.2a1.5 1.5 0 1 0 0.01 0Z M7 9.6l5 1.2l5-1.2 M12 10.8V14.5 M9.4 18.5L12 14.5L14.6 18.5",
        "arrow.clockwise": "M19 12.5a7 7 0 1 1-2.1-5 M19.5 4v4h-4",
        "folder": "M3.5 7.5a2 2 0 0 1 2-2h3.8l2 2h7.2a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z",
        "cards": "M7 4.5h11a1.5 1.5 0 0 1 1.5 1.5v9 M4.5 8.5a1.5 1.5 0 0 1 1.5-1.5h9.5a1.5 1.5 0 0 1 1.5 1.5v10a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5Z",
        "checkmark.circle": "M12 3a9 9 0 1 0 0.01 0Z M8 12.3L11 15.3L16.2 9",
        "sparkles": "M10 3.5l1.6 4.4l4.4 1.6l-4.4 1.6L10 15.5l-1.6-4.4L4 9.5l4.4-1.6Z M17.5 13.5l.8 2.2l2.2.8l-2.2.8l-.8 2.2l-.8-2.2l-2.2-.8l2.2-.8Z",
        "keyboard": "M3.5 6.5h17v11h-17Z M7 10h.01 M10 10h.01 M13 10h.01 M16 10h.01 M8 14h8",
        "pause": "M8.5 5.5V18.5 M15.5 5.5V18.5",
        "play": "M8 5.5L18.5 12L8 18.5Z",
        "info": "M12 3a9 9 0 1 0 0.01 0Z M12 11v5.5 M12 7.8V8"
    })
    readonly property var filled: ({ "star": true, "drop": false })
}
