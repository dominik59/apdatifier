"""Utility behavior with local feeds, private databases, and fake installers."""

import json
from pathlib import Path
import shutil

from shell_fixtures import ShellCase


class UtilityTests(ShellCase):
    def test_versions_cache_combination_and_identifier_mapping(self):
        self.cache.joinpath('updates.json_2').write_text('second')
        self.cache.joinpath('updates.json_1').write_text('first')
        combined = self.cache / 'combined'
        combined.write_text('obsolete')
        result = self.function('''clearVer 'v1--02.beta.3'
compareVer 1.02 1.2; printf 'equal:%s\\n' "$?"
compareVer 1.2 1.2.1; printf 'older:%s\\n' "$?"
compareVer 2.0 1.9; printf 'newer:%s\\n' "$?"
combineFiles "$cacheDir/combined"
printf 'pkg-a\\npkg-b\\n' | oneLine
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1.02.3', result.stdout)
        self.assertIn('equal:0', result.stdout)
        self.assertIn('older:2', result.stdout)
        self.assertIn('newer:1', result.stdout)
        self.assertIn('pkg-a pkg-b', result.stdout)
        self.assertEqual(combined.read_text(), 'firstsecond')
        self.assertFalse(list(self.cache.glob('updates.json_*')))
        record = self.scripts.joinpath('widgets-id').read_text().splitlines()[0].split()
        result = self.function(f'getId {record[0]}; getId {record[1]}')
        self.assertIn(record[0], result.stdout)
        self.assertIn(record[1], result.stdout)

    def test_desktop_icons_ignore_duplicates_and_missing_values(self):
        desktop = self.root / 'usr/share/applications'
        desktop.mkdir(parents=True)
        desktop.joinpath('one.desktop').write_text('[Desktop Entry]\nIcon=fixture-icon\n')
        desktop.joinpath('empty.desktop').write_text('[Desktop Entry]\nName=Empty\n')
        records = f'pkg-one {desktop}/one.desktop\npkg-one {desktop}/one.desktop\npkg-two {desktop}/empty.desktop\n'
        self.stub('pacman', f'print({records!r}, end="")')
        result = self.run_script('utils', 'getIcons', 'pkg-one', 'pkg-two')
        self.assertEqual(result.stdout.strip(), 'pkg-one fixture-icon')

    def test_private_database_sync_preserves_native_paths_and_reports_failure(self):
        system = self.root / 'system-db/local'
        system.mkdir(parents=True)
        self.stub('pacman-conf', 'print(root/"system-db")')
        self.stub('fakeroot', 'sys.exit(1 if root.joinpath("sync-failure").exists() else 0)')
        database = self.cache / 'db'
        database.mkdir()
        database.joinpath('db.lck').touch()
        result = self.function('dbPath="$cacheDir/db"; sync_dbs')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(database.joinpath('local').resolve(), system)
        self.assertFalse(database.joinpath('db.lck').exists())
        self.assertIn('--dbpath', self.calls('fakeroot')[0])
        self.root.joinpath('sync-failure').touch()
        result = self.function('dbPath="$cacheDir/db"; sync_dbs')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Failed to synchronize', result.stderr)

    def test_installed_versions_and_terminal_capability_fallback(self):
        self.stub('pacman', 'print("pkg-one 1.2")')
        self.stub('flatpak', '''if args[0] == 'list':
    print('org.example.Terminal' if '--columns=application' in args else 'Example\\t2\\tcommit')
else:
    print('[Application]\\ncommand=konsole\\n[Session Bus Policy]\\norg.freedesktop.Flatpak=talk')''')
        self.stub('fwupdmgr', 'print(json.dumps({"Devices":[{"Vendor":"Vendor","Name":"Device","Version":"3"}]}))')
        self.settings(arch='true', flatpak='true', fwupd='true')
        result = self.run_script('utils', 'currentVersions')
        data = json.loads(result.stdout)
        self.assertEqual([p['VO'] for p in data], ['1.2', '2commit', '3'])
        self.scripts.parent.joinpath('backends.py').write_text('raise SystemExit(1)\n')
        result = self.run_script('utils', 'checkPkgs')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('flatpak://org.example.Terminal/konsole', result.stdout)

    def feed_stubs(self, feeds):
        self.root.joinpath('feeds.json').write_text(json.dumps(feeds))
        self.stub('curl', '''feeds = json.loads(root.joinpath('feeds.json').read_text())
outputs = [args[i+1] for i,v in enumerate(args) if v == '-o']
urls = [args[i+1] for i,v in enumerate(args) if v == '--url']
for output,url in zip(outputs,urls): pathlib.Path(output).write_text(feeds[url])''')
        self.stub('xmllint', '''import re, xml.etree.ElementTree as ET
try: tree = ET.parse(args[-1]).getroot()
except (ET.ParseError, OSError): sys.exit(1)
if '--xpath' not in args: sys.exit(0)
query = args[args.index('--xpath')+1]
if query == 'name(/*)': print(tree.tag, end=''); sys.exit(0)
kind, expression = query.split('(',1)
expression = expression[:-1].lstrip('/')
expression = expression.split('/',1)[1] if '/' in expression else '.'
if kind == 'count': print(len(tree.findall(expression)), end=''); sys.exit(0)
if '/@' in expression:
    expression, attribute = expression.rsplit('/@',1)
    element = tree.find(expression)
    print(element.get(attribute,'') if element is not None else '', end='')
else: print(tree.findtext(expression,''), end='')''')

    def test_rss_atom_merge_limits_duplicates_and_feed_edits(self):
        rss = '<rss><channel><title>RSS</title>{}</channel></rss>'
        def item(title, link):
            return f'<item><title>{title}</title><link>{link}</link><pubDate>2026-10-20T12:00:00Z</pubDate></item>'
        atom = '<feed xmlns="urn:atom"><title>Atom</title><entry><title>Atom article</title><updated>2026-10-21T12:00:00Z</updated><link href="https://fixture.invalid/a"/></entry></feed>'
        self.feed_stubs({'https://fixture.invalid/rss':rss.format(item('First','https://fixture.invalid/1')+item('Second','https://fixture.invalid/2')+item('Limited','https://fixture.invalid/3')),
                         'https://fixture.invalid/atom':atom})
        self.cache.joinpath('news.json').write_text('invalid old cache')
        result = self.run_script('utils', 'rss', 'https://fixture.invalid/rss', 'https://fixture.invalid/atom')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['article'], 'Atom article')
        self.feed_stubs({'https://fixture.invalid/rss':rss.format(item('Second','https://fixture.invalid/2'))})
        result = self.run_script('utils', 'rss', 'https://fixture.invalid/rss')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p['link'] for p in json.loads(result.stdout)}, {'https://fixture.invalid/2','https://fixture.invalid/a'})
        self.assertFalse(self.root.joinpath('apdatifier').exists())

    def test_partial_feed_failure_keeps_independent_articles_and_returns_error(self):
        self.feed_stubs({'https://fixture.invalid/bad':'<broken', 'https://fixture.invalid/empty':'<rss><channel/></rss>'})
        original = [{'title':'Old', 'article':'Keep', 'timestamp':1, 'link':'https://fixture.invalid/old'}]
        self.cache.joinpath('news.json').write_text(json.dumps(original))
        result = self.run_script('utils', 'rss', 'https://fixture.invalid/bad', 'https://fixture.invalid/empty')
        self.assertEqual(result.returncode, 1)
        self.assertIn('https://fixture.invalid/bad', result.stderr)
        self.assertEqual(json.loads(result.stdout), original)

    def test_removal_confirmation_and_system_installation_guard(self):
        self.run_script('init')
        self.stub('kpackagetool6', 'pass')
        result = self.function('systemWide=0; uninstall', input='n\n\n')
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.config.exists())
        self.assertFalse(self.calls('kpackagetool6'))
        result = self.function('systemWide=1; checkSetup', input='\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn('installed system-wide', result.stdout)
        result = self.function('systemWide=0; uninstall', input='invalid\ny\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.local.joinpath('knotifications6/apdatifier.notifyrc').exists())
        self.assertIn('-r', self.calls('kpackagetool6')[0])

    def development_installer(self):
        self.stub('curl', 'print(json.dumps({"sha":"1234567890abcdef"}))')
        self.stub('git', '''if args[0] == 'clone':
    package = pathlib.Path.cwd()/'apdatifier/package'
    assert package.is_relative_to(root)
    package.mkdir(parents=True)
    package.joinpath('metadata.json').write_text(json.dumps({'KPlugin':{'Description':'old'}}))
    package.joinpath('translate').mkdir()
    package.joinpath('translate/build').write_text('printf translations\\n')''')
        self.stub('kpackagetool6', '''import tarfile
archive = pathlib.Path(args[args.index('-u')+1])
with tarfile.open(archive) as source:
    root.joinpath('installed-metadata.json').write_bytes(source.extractfile('./metadata.json').read())''')
        self.stub('restart-fixture', 'pass')
        self.settings(trayEnabledByDefault='true', restartCommand='restart-fixture')

    def test_development_install_uses_private_clone_and_records_metadata(self):
        self.development_installer()
        result = self.function('systemWide=0; install_devel', input='n\ny\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.root.joinpath('installed-metadata.json').read_text())
        self.assertEqual(data['KPlugin']['Description'], 'github commit: 1234567')
        self.assertTrue(data['KPlugin']['EnabledByDefault'])
        self.assertTrue(self.calls('restart-fixture'))
        self.assertFalse(list(self.root.glob('tmp*/apdatifier')))

    def test_development_clone_checkout_and_missing_tool_keep_failure_codes(self):
        self.stub('curl', 'print(json.dumps({"sha":"1234567890"}))')
        for stage, code in [('clone', 42), ('sparse-checkout', 43)]:
            with self.subTest(stage=stage):
                self.stub('git', f'''if args[0] == {stage!r}: sys.exit({code})
if args[0] == 'clone': pathlib.Path('apdatifier').mkdir()''')
                result = self.function('systemWide=0; install_devel', input='\n')
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertFalse(self.calls('kpackagetool6'))
        self.bin.joinpath('git').unlink()
        result = self.function('systemWide=0; install_devel', input='\n')
        self.assertEqual(result.returncode, 127, result.stdout + result.stderr)

    def test_archive_and_installer_failure_do_not_restart_the_desktop(self):
        for stage, code in [('tar', 54), ('kpackagetool6', 53)]:
            with self.subTest(stage=stage):
                self.development_installer()
                self.log.unlink(missing_ok=True)
                self.stub(stage, f'sys.exit({code})')
                result = self.function('systemWide=0; install_devel', input='n\ny\n\n')
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertFalse(self.calls('restart-fixture'))
                if stage == 'tar':
                    self.assertFalse(self.calls('kpackagetool6'))
                    self.bin.joinpath('tar').unlink()
                    self.bin.joinpath('tar').symlink_to(shutil.which('tar'))

    def test_failed_uninstall_preserves_the_installer_exit_code(self):
        self.run_script('init')
        self.stub('kpackagetool6', 'sys.exit(55)')
        result = self.function('systemWide=0; uninstall', input='y\n\n')
        self.assertEqual(result.returncode, 55, result.stdout + result.stderr)

    def test_development_restart_failure_keeps_its_exit_code(self):
        self.development_installer()
        self.stub('restart-fixture', 'sys.exit(56)')
        result = self.function('systemWide=0; install_devel', input='n\ny\n\n')
        self.assertEqual(result.returncode, 56, result.stdout + result.stderr)

    def test_current_development_version_and_stable_cancel_start_no_installer(self):
        self.stub('git', 'pass')
        self.stub('curl', 'print(json.dumps({"sha":"1234567890"}))')
        self.applet.joinpath('metadata.json').write_text(json.dumps({'KPlugin':{'Description':'github commit: 1234567'}}))
        result = self.function('systemWide=0; install_devel', input='\n')
        self.assertIn('Up to date', result.stdout)
        self.assertFalse(self.calls('git'))
        self.applet.joinpath('metadata.json').write_text(json.dumps({'KPlugin':{'Description':'Package Update Notifier'}}))
        result = self.function('systemWide=0; install_stable', input='n\n\n')
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.calls('kpackagetool6'))
