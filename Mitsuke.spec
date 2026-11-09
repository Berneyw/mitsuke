# -*- mode: python ; coding: utf-8 -*-
# Mitsuke build: one folder (dist\Mitsuke). The UI is Qt Quick (PySide6-Essentials): only the Qt modules and
# QML plugins it uses are kept, so the folder stays as small as Qt allows.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('winrt') + ['PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtGui',
                                                'PySide6.QtNetwork']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('gui/qml', 'gui/qml')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'PySide6.QtWidgets', 'PySide6.QtTest', 'PySide6.QtSql',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick', 'PySide6.Qt3DCore', 'PySide6.QtCharts',
              'PySide6.QtMultimedia', 'PySide6.QtPdf', 'PySide6.QtQuick3D', 'PySide6.QtDesigner',
              'PySide6.QtHelp', 'PySide6.QtXml', 'numpy'],
    noarchive=False,
    optimize=0,
)

# QML modules and Qt libraries Mitsuke never loads (they come along when the Addons wheel is installed)
UNUSED = ('Qt6Quick3D', 'Qt6Charts', 'Qt6DataVisualization', 'Qt6Graphs', 'Qt6WebEngine', 'Qt6WebView',
          'Qt6WebChannel', 'Qt6WebSockets', 'Qt6Multimedia', 'Qt6SpatialAudio', 'Qt6Location', 'Qt6Positioning',
          'Qt6Sensors', 'Qt6RemoteObjects', 'Qt6Scxml', 'Qt6StateMachine', 'Qt63D', 'Qt6Pdf', 'Qt6VirtualKeyboard',
          'Qt6TextToSpeech', 'Qt6Bluetooth', 'Qt6Nfc', 'Qt6SerialPort', 'Qt6SerialBus', 'Qt6HttpServer',
          'Qt6NetworkAuth', 'Qt6Designer', 'Qt6Help', 'Qt6Sql', 'Qt6Test', 'Qt6QuickTest', 'Qt6Quick3D',
          'Qt6QuickTimeline', 'Qt6QuickParticles', 'Qt6ShaderTools', 'Qt6Svg', 'Qt6QuickVectorImage',
          'Qt6LabsAnimation', 'Qt6LabsFolderListModel', 'Qt6LabsQmlModels', 'Qt6LabsSettings',
          'Qt6LabsSharedImage', 'Qt6LabsWavefrontMesh', 'Qt6QuickControls2Material', 'Qt6QuickControls2Universal',
          'Qt6QuickControls2Fusion', 'Qt6QuickControls2Imagine', 'Qt6QuickControls2FluentWinUI3',
          'Qt6QuickControls2WindowsStyle', 'Qt6QuickControls2IOSStyle', 'Qt6QuickControls2MacOSStyle',
          'Qt6Widgets', 'Qt6QuickWidgets', 'Qt6LabsStyleKit', 'Qt6Core5Compat', '_avif', 'Qt6PrintSupport', 'Qt6Concurrent', 'Qt6Xml', 'Qt6DBus')
QML_UNUSED = ('/Qt3D', '/QtQuick3D', '/QtCharts', '/QtDataVisualization', '/QtGraphs', '/QtWebEngine', '/QtWebView',
              '/QtWebChannel', '/QtWebSockets', '/QtMultimedia', '/QtLocation', '/QtPositioning', '/QtSensors',
              '/QtRemoteObjects', '/QtScxml', '/QtTextToSpeech', '/QtTest', '/QtQuick/VirtualKeyboard',
              '/QtQuick/Pdf', '/QtQuick/Particles', '/QtQuick/Timeline', '/QtQuick/Scene2D', '/QtQuick/Scene3D',
              '/QtQuick/LocalStorage', '/QtQuick/VectorImage', '/QtQuick/Controls/Material',
              '/QtQuick/Controls/Universal', '/QtQuick/Controls/Fusion', '/QtQuick/Controls/Imagine',
              '/QtQuick/Controls/FluentWinUI3', '/QtQuick/Controls/Windows', '/QtQuick/Controls/iOS',
              '/QtQuick/Controls/macOS', '/QtQuick/NativeStyle', '/Qt/labs', '/QtCore', '/QtNetwork',
              '/QtWebSockets', '/QtQml/StateMachine', '/QtQml/XmlListModel', '/QtQuick/Effects',
              '/QtQuick/Controls/impl/Fluent', '/translations/')


def keep(entry):
    path = entry[0].replace('\\', '/')
    name = path.rsplit('/', 1)[-1]
    if any(name.startswith(u) for u in UNUSED):
        return False
    if path.startswith('gui/') or '/qml/' not in '/' + path:     # our own QML, and non-QML files
        return '/translations/' not in '/' + path
    return not any(q in path[path.index('qml/') + 3:] for q in QML_UNUSED)


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Mitsuke',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Mitsuke',
)
