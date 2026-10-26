"""Exercise the widget updater with local archives and substitute services."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile


@unittest.skipUnless(all(shutil.which(tool) for tool in ("bash", "jq", "tar", "unzip", "xz")),
                     "Widget tests need existing Bash, jq, tar, unzip, and xz.")
class WidgetUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="apdatifier-widget-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in ("bash", "dirname", "readlink", "grep", "sed", "cat", "find", "head", "uniq", "jq",
                     "mkdir", "rm", "mktemp", "mv", "tr", "paste", "seq", "basename", "tar", "unzip", "xz", "date"):
            self.bin.joinpath(tool).symlink_to(shutil.which(tool))
        self.stub("sleep", "#!/bin/sh\nexit 0\n")
        self.stub("tput", "#!/bin/sh\nexit 0\n")
        self.stub("column", "#!/bin/sh\ncat\n")
        self.config = self.root / "config"
        self.config.mkdir()
        self.config.joinpath("config.conf").write_text('termFont="false"\nrestartShell="false"\nwidgetConfirmation="false"\n')
        self.log = self.root / "installed.jsonl"
        self.archive = self.root / "package.download"
        self.write_archive()
        self.env = dict(os.environ, PATH=str(self.bin), TMPDIR=str(self.root), TERM="dumb",
                        APDATIFIER_CONFIG_DIR=str(self.config), APDATIFIER_CACHE_DIR=str(self.root / "cache"),
                        XDG_LOCAL_HOME=str(self.root / "local"), APDATIFIER_TEST_ARCHIVE=str(self.archive),
                        APDATIFIER_TEST_INSTALL_LOG=str(self.log))
        self.stub("curl", r'''#!/usr/bin/python3
import os, pathlib, shutil, sys
args = sys.argv[1:]
output, url = pathlib.Path(args[args.index('-o') + 1]), args[args.index('--url') + 1]
if 'api.kde-look.org' in url:
    contents = ''.join('<content details="summary"><id>' + identifier + '</id><name>' + name + '</name>'
        '<version>2.13.0</version><typeid>705</typeid><download_version1>2.13.0</download_version1>'
        '<downloadlink1>https://example.invalid/archive' + identifier + '</downloadlink1></content>'
        for identifier, name in [('2196105', 'Example One'), ('2196106', 'Example Two')])
    output.write_text('<ocs><meta><statuscode>100</statuscode><totalitems>2</totalitems></meta><data>' + contents + '</data></ocs>')
elif os.environ.get('APDATIFIER_TEST_HTTP_ERROR') == 'true' or (os.environ.get('APDATIFIER_TEST_SECOND_FAIL') == 'true' and url.endswith('2196106')):
    output.write_text('<html>HTTP failure</html>')
    sys.exit(22 if '--fail' in args else 0)
else:
    shutil.copyfile(os.environ['APDATIFIER_TEST_ARCHIVE'], output)
''')
        self.stub("xmllint", r'''#!/usr/bin/python3
import re, sys, xml.etree.ElementTree as ET
try:
    tree = ET.parse(sys.argv[-1])
except (OSError, ET.ParseError):
    sys.exit(1)
if '--xpath' not in sys.argv:
    sys.exit(0)
query = sys.argv[sys.argv.index('--xpath') + 1]
contents = tree.findall('.//content')
if query.startswith('//content[@details='):
    print(''.join(ET.tostring(item, encoding='unicode') for item in contents), end='')
elif query.startswith('//content[id='):
    identifier = re.search(r"id='([^']+)'", query)[1]
    print(''.join(ET.tostring(child, encoding='unicode') for item in contents if item.findtext('id') == identifier for child in item), end='')
elif query.startswith('string(//ocs/meta/'):
    print(tree.findtext('./meta/' + query.split('/')[-1].rstrip(')'), ''), end='')
else:
    field = query.split('/')[-1].rstrip(')')
    selector = re.search(r'text\(\)=[\'"]([^\'"]+)[\'"]', query)
    key = 'name' if query.startswith('string(//name[') else 'id'
    print(next((item.findtext(field, '') for item in contents if selector and item.findtext(key) == selector[1]), ''), end='')
''')
        self.stub("kpackagetool6", r'''#!/usr/bin/python3
import json, os, pathlib, sys
args = sys.argv[1:]
metadata = json.loads((pathlib.Path(args[args.index('-u') + 1]) / 'metadata.json').read_text())
with open(os.environ['APDATIFIER_TEST_INSTALL_LOG'], 'a') as stream:
    stream.write(json.dumps({'args': args, 'metadata': metadata}) + '\n')
sys.exit(int(os.environ.get('APDATIFIER_TEST_INSTALL_EXIT', '0')))
''')
        self.script = Path(__file__).resolve().parents[1] / "package/contents/tools/sh/widgets"

    def stub(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o700)

    def write_archive(self, kind="tar", metadata=True, valid_json=True, enabled=None):
        values = {"KPackageStructure": "Plasma/Applet", "KPlugin": {"Id": "org.example.widget", "Version": "1"}}
        if enabled is not None:
            values['KPlugin']['EnabledByDefault'] = enabled
        content = json.dumps(values).encode()
        if not valid_json:
            content = b"{invalid JSON"
        name = "widget/metadata.json" if metadata else "widget/README"
        if kind == "zip":
            with zipfile.ZipFile(self.archive, "w") as archive:
                archive.writestr(name, content)
        else:
            with tarfile.open(self.archive, "w:xz") as archive:
                item = tarfile.TarInfo(name)
                item.size = len(content)
                archive.addfile(item, io.BytesIO(content))

    def run_widget(self, *args, input=None):
        stream = {'stdin': subprocess.DEVNULL} if input is None else {'input': input}
        return subprocess.run(["bash", str(self.script), *args], env=self.env,
                              **stream, capture_output=True, text=True, timeout=15)

    def assert_not_installed(self, result, expected):
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(list(self.root.glob('apdatifier-widgets.*')))

    def test_tar_xz_works_without_bsdtar(self):
        result = self.run_widget("upgrade", "2196105", "example-one")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.log.exists(), result.stdout + result.stderr)
        installed = json.loads(self.log.read_text())
        self.assertEqual(installed['metadata']['KPlugin']['Version'], '2.13.0')

    def test_zip_works_without_bsdtar(self):
        self.write_archive("zip")
        result = self.run_widget("upgrade", "2196105", "example-one")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.log.exists())

    def test_http_error_stops_before_unpacking_or_installation(self):
        self.env['APDATIFIER_TEST_HTTP_ERROR'] = 'true'
        self.assert_not_installed(self.run_widget("upgrade", "2196105", "example-one"), 1)

    def test_invalid_archive_does_not_report_success(self):
        self.archive.write_text('<html>Unexpected server response</html>')
        self.assert_not_installed(self.run_widget("upgrade", "2196105", "example-one"), 2)

    def test_missing_metadata_is_distinct_from_invalid_json(self):
        for metadata, valid, code in ((False, True, 3), (True, False, 4)):
            with self.subTest(metadata=metadata, valid_json=valid):
                self.write_archive(metadata=metadata, valid_json=valid)
                self.assert_not_installed(self.run_widget("upgrade", "2196105", "example-one"), code)

    def test_installer_failure_is_not_hidden_by_cleanup(self):
        self.env['APDATIFIER_TEST_INSTALL_EXIT'] = '42'
        self.assertEqual(self.run_widget("upgrade", "2196105", "example-one").returncode, 42)
        self.assertTrue(self.log.exists())

    def test_missing_dependency_returns_127(self):
        self.bin.joinpath('jq').unlink()
        self.assert_not_installed(self.run_widget("upgrade", "2196105", "example-one"), 127)

    def test_missing_extractors_returns_127(self):
        self.bin.joinpath('tar').unlink()
        self.bin.joinpath('unzip').unlink()
        self.assert_not_installed(self.run_widget("upgrade", "2196105", "example-one"), 127)

    def test_existing_bsdtar_path_still_works(self):
        marker = self.root / 'bsdtar-used'
        self.env['APDATIFIER_TEST_BSDTAR_LOG'] = str(marker)
        self.stub('bsdtar', '#!/bin/sh\nprintf used > "$APDATIFIER_TEST_BSDTAR_LOG"\nexec tar "$@"\n')
        result = self.run_widget('upgrade', '2196105', 'example-one')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.log.exists())
        self.assertTrue(marker.exists())

    def test_terminal_lifecycle_records_archive_failure(self):
        self.archive.write_text('<html>Not an archive</html>')
        result = subprocess.run(['bash', str(self.script.with_name('upgrade')), 'widget-pkg',
                                 '--transaction', 'widget-archive-failure', '2196105', 'example-one'],
                                env=self.env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=15)
        self.assert_not_installed(result, 1)
        state = json.loads((Path(self.env['APDATIFIER_CACHE_DIR']) / 'upgrade-state.json').read_text())
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['stages'][-1]['backend'], 'widgets')
        self.assertEqual(state['stages'][-1]['code'], 2)

    def test_bulk_failure_is_not_hidden_by_another_success(self):
        local = Path(self.env['XDG_LOCAL_HOME']) / 'plasma/plasmoids'
        for directory, name in (('one', 'Example One'), ('two', 'Example Two')):
            folder = local / directory
            folder.mkdir(parents=True)
            (folder / 'metadata.json').write_text(json.dumps({'KPackageStructure': 'Plasma/Applet',
                'KPlugin': {'Name': name, 'Version': '1', 'Description': 'Fixture', 'Authors': [], 'Icon': ''}}))
        self.env['APDATIFIER_TEST_SECOND_FAIL'] = 'true'
        result = self.run_widget('upgradeAll')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def installed_widget(self, version='1', structure='Plasma/Applet'):
        folder = Path(self.env['XDG_LOCAL_HOME']) / 'plasma/plasmoids/org.example.One'
        folder.mkdir(parents=True, exist_ok=True)
        folder.joinpath('metadata.json').write_text(json.dumps({'KPackageStructure': structure,
            'KPlugin': {'Name':'Example One', 'Version':version, 'Description':'', 'Authors':[], 'Icon':''}}))
        return folder

    def test_discovery_and_installed_list_preserve_native_identity(self):
        folder = self.installed_widget()
        result = self.run_widget('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['nativeId'], folder.name)
        self.assertEqual(data[0]['uid'], 'widgets:'+folder.name)
        self.assertEqual(data[0]['VO'], '1')
        self.assertEqual(data[0]['VN'], '2.13.0')
        self.assertEqual(data[0]['AU'], '?')
        result = self.run_widget('list')
        data = json.loads('['+result.stdout.rstrip().rstrip(',')+']')
        self.assertEqual(data[0]['nativeId'], folder.name)
        self.assertEqual(data[0]['VO'], '1')

    def test_empty_current_and_invalid_local_metadata_are_not_updates(self):
        self.assertEqual(json.loads(self.run_widget('check').stdout), [])
        folder = self.installed_widget('2.13.0')
        self.assertEqual(json.loads(self.run_widget('check').stdout), [])
        folder.joinpath('metadata.json').write_text('{broken')
        self.assertEqual(json.loads(self.run_widget('check').stdout), [])

    def test_api_pagination_and_package_types(self):
        folder = self.installed_widget()
        original = self.bin.joinpath('curl').read_text()
        self.stub('curl', original.replace('<totalitems>2</totalitems>', '<totalitems>101</totalitems>'))
        self.assertEqual(len(json.loads(self.run_widget('check').stdout)), 1)
        for identifier, structure in [('715','Plasma/Wallpaper'),('719','KWin/Effect'),('720','KWin/Script')]:
            with self.subTest(structure=structure):
                self.stub('curl', original.replace('<typeid>705</typeid>',f'<typeid>{identifier}</typeid>'))
                result = self.run_widget('check')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)[0]['TP'], structure)
                self.assertEqual(json.loads(folder.joinpath('metadata.json').read_text())['KPackageStructure'], structure)

    def test_api_failure_codes_never_become_an_empty_success(self):
        self.installed_widget()
        original = self.bin.joinpath('curl').read_text()
        for code in ('200','403'):
            with self.subTest(code=code):
                self.stub('curl', original.replace('<statuscode>100</statuscode>',f'<statuscode>{code}</statuscode>'))
                result = self.run_widget('check')
                self.assertEqual(result.returncode, 1)
                self.assertIn('Unable check widgets', result.stderr)
        self.stub('curl', '#!/bin/sh\nexit 22\n')
        result = self.run_widget('check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Failed to retrieve data', result.stderr)

    def test_later_api_page_failure_is_not_a_partial_success(self):
        self.installed_widget()
        original = self.bin.joinpath('curl').read_text().replace('<totalitems>2</totalitems>', '<totalitems>101</totalitems>')
        for failure in ('http', 'status'):
            with self.subTest(failure=failure):
                handler = ("if '--parallel' in args:\n"
                           + ("    sys.exit(22)\n" if failure == 'http' else
                              "    pathlib.Path(args[args.index('-o')+1]).write_text('<ocs><meta><statuscode>403</statuscode></meta></ocs>')\n    sys.exit(0)\n"))
                self.stub('curl', original.replace('args = sys.argv[1:]\n', 'args = sys.argv[1:]\n'+handler))
                result = self.run_widget('check')
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertFalse(self.log.exists())

    def test_bulk_confirmation_can_cancel_then_install(self):
        self.installed_widget()
        with self.config.joinpath('config.conf').open('a') as stream:
            stream.write('widgetConfirmation="true"\n')
        result = self.run_widget('upgradeAll', input='n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log.exists())
        result = self.run_widget('upgradeAll', input='invalid\ny\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_apdatifier_archive_keeps_default_tray_visibility(self):
        self.write_archive(enabled=False)
        with self.config.joinpath('config.conf').open('a') as stream:
            stream.write('trayEnabledByDefault="true"\n')
        result = self.run_widget('upgrade','2196105','apdatifier')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(self.log.read_text())['metadata']['KPlugin']['EnabledByDefault'])


if __name__ == '__main__':
    unittest.main()
