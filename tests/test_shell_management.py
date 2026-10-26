"""Drive the actual legacy menu through a pseudo-terminal and recorded commands."""

import shutil

from shell_fixtures import ShellCase


class ManagementTests(ShellCase):
    def setUp(self):
        super().setUp()
        self.settings(termFont='true')
        self.stub('pacman', '''if args[0] == '-Qqe': print('pkg-one')
elif args[0] == '-Qqtd': print('pkg-orphan')
elif args[0] == '-Qq': print('pkg-one\\npkg-orphan\\npkg-dependency')
elif args[0].startswith('-Q') or args[0] == '-Slq': print('pkg-one\\npkg-two')''')
        self.stub('paru', "if args[0].startswith('-Q') or args[0] == '-Slq': print('pkg-one\\npkg-two')")
        self.stub('sudo', 'pass')
        self.stub('fzf', "sys.stdin.read(); print(root.joinpath('selection').read_text(), end='')")
        self.root.joinpath('selection').write_text('pkg-one\npkg-two\n')
        self.stub('flatpak', "if args[0] == 'list': print('org.example.One\\tExample One\\norg.example.Two\\tExample Two')")
        self.stub('curl', 'print(json.dumps(["org.example.One","org.example.Two"]))')
        self.package_cache = self.root / 'package-cache'
        self.package_cache.mkdir()
        self.stub('pacman-conf', 'print(root/"package-cache")')
        real_find = shutil.which('find')
        self.stub('find', f'''if args[0] == '/usr/lib': print(root/'python3.13'); sys.exit(0)
safe = [v for v in args if not v.startswith('/') or pathlib.Path(v).is_relative_to(root)]
os.execv({real_find!r}, ['find', *safe])''')

    def submenu(self, top, header, choice='1', *, extra=(), pause=True):
        steps = [('Management', str(top)), (header, choice), *extra]
        if pause:
            steps.append(('Press Enter to return menu', '\n'))
        steps += [(header, 'h'), ('Management', 'q')]
        result = self.interact('management', ['--legacy', 'arch'], steps)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def test_navigation_help_wraparound_and_small_terminal(self):
        result = self.interact('management', ['--legacy', 'arch'],
                              [('Management','?'), ('select','k'), ('Recent installs','j'),
                               ('Management','\x1b[B'), ('Management','\x1b[A'), ('Management','q')])
        self.assertEqual(result.returncode, 0)
        result = self.interact('management', ['--legacy','arch'], [('Terminal too small','q')], rows=5)
        self.assertEqual(result.returncode, 0)

    def test_install_remove_explicit_and_orphan_lists_route_selected_packages(self):
        for top,header,choice,action in [
            (1,'Search all available packages','1','-Syu'),
            (2,'View installed packages','1','-Rsn'),
            (3,'Show packages you installed directly','1','-Rsn'),
            (3,'Show packages you installed directly','2','-Rsn'),
            (4,'Dependencies that are no longer needed','1','-Rsn'),
        ]:
            with self.subTest(top=top,choice=choice):
                self.log.unlink(missing_ok=True)
                self.submenu(top,header,choice)
                self.assertIn(['pacman',action,'pkg-one','pkg-two'], self.calls('sudo'))

    def test_orphan_removal_and_empty_selection_do_not_mix_actions(self):
        self.submenu(4,'Dependencies that are no longer needed','2')
        self.assertIn(['pacman','-Rsn','pkg-orphan'], self.calls('sudo'))
        self.root.joinpath('selection').write_text('')
        self.log.unlink()
        self.submenu(1,'Search all available packages',pause=False)
        self.assertFalse(self.calls('sudo'))

    def test_cache_cleanup_requires_confirmation_and_preserves_quoted_directory(self):
        directory = self.package_cache / 'cache with spaces'
        directory.mkdir()
        directory.joinpath('entry').touch()
        self.submenu(6,'Remove cached files to free disk space','1',
                     extra=[('Remove these directories?','n\n')])
        self.assertTrue(directory.exists())
        self.submenu(6,'Remove cached files to free disk space','2',
                     extra=[('Remove these directories?','y\n')])
        self.assertFalse(directory.exists())
        self.assertIn(['pacman','-Scc'], self.calls('sudo'))
        self.assertIn(['pacman','-Sc'], self.calls('sudo'))

    def test_cached_downgrade_passes_only_selected_existing_archive(self):
        archive = self.package_cache / 'pkg-one.pkg.tar.zst'
        archive.touch()
        self.root.joinpath('selection').write_text(archive.name+'\n')
        result = self.interact('management', ['--legacy','arch'],
                              [('Management','5'), ('Press Enter to return menu','\n'), ('Management','q')])
        self.assertEqual(result.returncode, 0)
        self.assertIn(['pacman','-U',str(archive)], self.calls('sudo'))

    def test_missing_dependency_restores_the_menu(self):
        self.bin.joinpath('fzf').unlink()
        result = self.submenu(1,'Search all available packages')
        self.assertIn('fzf', result.stdout)
        self.assertFalse(self.calls('sudo'))

    def test_flatpak_install_remove_unused_and_native_identifiers(self):
        self.root.joinpath('selection').write_text('org.example.One\n')
        self.submenu(1,'Search all available packages','2')
        self.assertIn(['install','org.example.One'], self.calls('flatpak'))
        self.settings(flatpakRemoveUnused='true')
        self.root.joinpath('selection').write_text('org.example.One\tExample One\n')
        self.submenu(2,'View installed packages','2')
        self.assertIn(['uninstall','org.example.One'], self.calls('flatpak'))
        self.assertIn(['uninstall','--unused'], self.calls('flatpak'))

    def test_rebuild_selection_and_missing_helper_have_distinct_results(self):
        self.settings(aur='true', wrapper='paru')
        self.submenu(7,'Select packages that need reinstall','1')
        self.assertIn(['-S','--rebuild','pkg-one','pkg-two'], self.calls('paru'))
        self.settings()
        self.bin.joinpath('paru').unlink()
        result = self.submenu(7,'Select packages that need reinstall','2')
        self.assertIn('yay/paru/pikaur', result.stdout)

    def test_detected_rebuild_can_be_confirmed_or_canceled(self):
        self.settings(aur='true', wrapper='paru')
        self.submenu(7,'Select packages that need reinstall','2', extra=[('Resume?','y\n')])
        self.assertIn(['-S','--rebuild','-'], self.calls('paru'))
        self.log.unlink()
        self.submenu(7,'Select packages that need reinstall','2', extra=[('Resume?','n\n')])
        self.assertNotIn(['-S','--rebuild','-'], self.calls('paru'))

    def test_recent_history_keeps_installed_package_statuses(self):
        self.root.joinpath('pacman.log').write_text(''.join(
            f'[2026-10-20T12:00:00+0000] [ALPM] installed {name} (1)\n'
            for name in ('pkg-one','pkg-orphan','pkg-dependency','removed')))
        result = self.interact('management', ['--legacy','arch'],
                              [('Management','9'), ('Press Enter to return menu','\n'), ('Management','q')])
        for expected in ('pkg-one','pkg-orphan','pkg-dependency','Orphaned dependency','Installed as a dependency'):
            self.assertIn(expected,result.stdout)
        self.assertNotIn('removed', result.stdout)

    def test_hidden_options_and_flatpak_only_entry(self):
        self.settings(mngHideFlatpak='true', mngHideHeaders='true', mngHideNums='true', mngHideHelp='true')
        self.root.joinpath('selection').write_text('')
        result = self.interact('management', ['--legacy','arch'],
                              [('Browse available','1'), ('Browse available','q')])
        self.assertEqual(result.returncode, 0)
        result = self.run_script('management','--legacy','flatpak',input='3\n')
        self.assertEqual(result.returncode, 0)
