"""Optional compile-only check with an already installed PyQt6.

No component is created. In particular, this never starts the applet, installs
it, or runs its Component.onCompleted hooks. PyQt6 is not a runtime dependency.
"""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile


def main():
    if importlib.util.find_spec("PyQt6") is None:
        print("SKIP: the optional development PyQt6 binding is not installed.")
        return 0
    with tempfile.TemporaryDirectory(prefix="apdatifier-qml-check-") as root:
        os.environ.update(
            QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
            QML_DISK_CACHE_PATH=root, XDG_CACHE_HOME=root, XDG_CONFIG_HOME=root,
            XDG_DATA_HOME=root, XDG_RUNTIME_DIR=root,
        )
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtQml import QQmlComponent, QQmlEngine
        app = QGuiApplication([])
        engine = QQmlEngine()
        failures = []
        files = sorted((Path(__file__).resolve().parents[1] / "package/contents").rglob("*.qml"))
        for path in files:
            component = QQmlComponent(engine)
            component.loadUrl(QUrl.fromLocalFile(str(path)), QQmlComponent.CompilationMode.PreferSynchronous)
            while component.isLoading():
                app.processEvents()
            if component.isError():
                failures.extend(error.toString() for error in component.errors())
        for error in failures:
            print(error, file=sys.stderr)
        print(f"QML compilation: {len(files)} files, {len(failures)} errors.")
        return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
