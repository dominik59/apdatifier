"""Exercise delayed callbacks in Qt when an existing PyQt6 binding is available."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


PROBE = r'''
import json
import os
import sys

try:
    from PyQt6.QtCore import QMetaObject, QTimer, QUrl
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtQml import QQmlComponent, QQmlEngine
    from PyQt6.QtQuick import QQuickItem
except ImportError:
    raise SystemExit(77)

root, script, scenario = sys.argv[1:]
os.environ.update(
    QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
    XDG_CONFIG_HOME=root, XDG_CACHE_HOME=root, XDG_DATA_HOME=root,
    XDG_RUNTIME_DIR=root, QML_DISK_CACHE_PATH=root,
)
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine)
source = """
import QtQuick
import %s as JS
Item {
    id: root
    property int completed: 0
    function start() {
        JS.runLater(30, function() { root.completed++ })
    }
}
""" % json.dumps(QUrl.fromLocalFile(script).toString())
component.setData(source.encode(), QUrl.fromLocalFile(root + "/probe.qml"))
while component.isLoading():
    app.processEvents()
assert not component.isError(), [error.toString() for error in component.errors()]
owner = QQuickItem()
obj = component.create()
assert obj is not None, [error.toString() for error in component.errors()]
if scenario == "reparent":
    obj.setParentItem(owner)
QMetaObject.invokeMethod(obj, "start")
if scenario == "reparent":
    obj.setParentItem(None)
    owner.deleteLater()
engine.collectGarbage()
QTimer.singleShot(250, app.quit)
app.exec()
print(json.dumps({"completed": obj.property("completed")}))
'''


class QmlTimerTests(unittest.TestCase):
    def probe(self, scenario):
        python = Path("/usr/bin/python3")
        if not python.is_file():
            self.skipTest("System Python is unavailable for the optional PyQt6 check.")
        script = Path(__file__).resolve().parents[1] / "package/contents/tools/tools.js"
        with tempfile.TemporaryDirectory(prefix="apdatifier-qml-timer-") as root:
            result = subprocess.run(
                [str(python), "-I", "-B", "-c", PROBE, root, str(script), scenario],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
            )
        if result.returncode == 77:
            self.skipTest("The optional system PyQt6 development binding is absent.")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {"completed": 1}, result.stderr)

    def test_delayed_callback_runs_without_a_visual_parent(self):
        self.probe("parentless")

    def test_reparenting_does_not_cancel_a_pending_callback(self):
        self.probe("reparent")


if __name__ == "__main__":
    unittest.main()
