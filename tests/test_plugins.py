import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from editor.plugin_system import PluginStore, PluginHost, read_manifest


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build')
        self.root = Path(self.temp.name)
        self.store = PluginStore(self.root / 'installed')

    def tearDown(self):
        self.temp.cleanup()

    def package(self):
        folder = self.root / 'source'; folder.mkdir()
        (folder / 'plugin.json').write_text(json.dumps({'id': 'custom-test', 'name': 'Test', 'api_version': 1, 'entry': 'plugin.py'}), encoding='utf-8')
        (folder / 'plugin.py').write_text('raise RuntimeError("Installation must not execute me")', encoding='utf-8')
        return folder

    def test_ten_builtin_packages(self):
        packages = self.store.discover()
        self.assertEqual(len(packages), 10)
        self.assertTrue(all(p['builtin'] and p['enabled'] for p in packages))

    def test_install_folder_disabled_and_duplicate_preserved(self):
        source = self.package()
        self.assertEqual(self.store.install(source), 'custom-test')
        installed = self.store.root / 'custom-test' / 'plugin.py'
        original = installed.read_text()
        self.assertFalse(next(p for p in self.store.discover() if p['id'] == 'custom-test')['enabled'])
        with self.assertRaises(ValueError):
            self.store.install(source)
        self.assertEqual(installed.read_text(), original)
        self.store.set_enabled('custom-test', True)
        self.assertTrue(self.store.state()['custom-test'])

    def test_zip_and_traversal(self):
        folder = self.package()
        archive = self.root / 'plugin.zip'
        with zipfile.ZipFile(archive, 'w') as package:
            for path in folder.iterdir():
                package.write(path, 'package/' + path.name)
        self.assertEqual(self.store.install(archive), 'custom-test')
        bad = self.root / 'bad.zip'
        with zipfile.ZipFile(bad, 'w') as package:
            package.writestr('../escape.txt', 'no')
        with self.assertRaises(ValueError):
            self.store.install(bad)
        self.assertFalse((self.root / 'escape.txt').exists())

    def test_invalid_entry_and_incompatible_api(self):
        folder = self.package()
        manifest = json.loads((folder / 'plugin.json').read_text())
        manifest['entry'] = '../outside.py'
        (folder / 'plugin.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            read_manifest(folder)

    def test_custom_plugin_lifecycle(self):
        from types import SimpleNamespace
        folder = self.package()
        (folder / 'plugin.py').write_text('def setup(context):\n    context.log("setup")\n    context.add_action("Action", lambda: context.log("action"))\n    context.on_cleanup(lambda: context.log("cleanup"))\ndef teardown(context):\n    context.log("teardown")\n', encoding='utf-8')
        self.store.install(folder)
        self.store.builtin = self.root / 'no-builtins'
        messages, actions = [], []
        window = SimpleNamespace(console=SimpleNamespace(log=lambda message, level: messages.append(message)))
        class Menu:
            def addAction(self, title):
                action = SimpleNamespace(triggered=SimpleNamespace(connect=lambda callback: None), deleteLater=lambda: None)
                actions.append(action)
                return action
            def removeAction(self, action):
                actions.remove(action)
        host = PluginHost(window, Menu(), self.store)
        host.reload(); self.assertEqual(messages, [])
        self.store.set_enabled('custom-test', True); host.reload()
        self.assertEqual(len(host.loaded), 1)
        self.assertEqual(len(actions), 1)
        self.store.set_enabled('custom-test', False); host.reload()
        self.assertEqual(messages, ['setup', 'teardown', 'cleanup'])
        self.assertEqual(actions, [])


if __name__ == '__main__':
    unittest.main()
