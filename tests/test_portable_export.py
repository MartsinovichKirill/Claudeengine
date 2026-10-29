import json,tempfile,unittest,os
from pathlib import Path
from portable_export import export_portable
from portable_export import filesystem_path

class PortableExportTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Win32 extended paths')
    def test_deep_runtime_license_and_deep_export_folder(self):
        with tempfile.TemporaryDirectory(dir=filesystem_path(Path('build').resolve())) as tmp:
            root=Path(str(tmp).removeprefix('\\\\?\\')).resolve();project=root/'Проект игры';project.mkdir()
            (project/'main.scene').write_text('{}')
            (project/'project.json').write_text(json.dumps({'main_scene':'main.scene'}))
            template=root/'runtime'/'Application'/('runtime-'+'a'*60)/'player-template'
            internal=filesystem_path(template/'_internal');internal.mkdir(parents=True)
            filesystem_path(template/'CloudPlayer.exe').write_bytes(b'player')
            relative=Path('numpy-2.5.4.dist-info/licenses/numpy/_core/src/common/pythoncapi-compat')
            license=internal/relative/'LICENSE.txt';license.parent.mkdir(parents=True);license.write_text('License retained')
            output=root/('export-'+'b'*60)/('nested-'+'c'*50)
            result=Path(export_portable(project,output,'CloudGame',template))
            copied=filesystem_path(result/'_internal'/relative/'LICENSE.txt')
            self.assertGreater(len(str(copied)),260)
            self.assertEqual(copied.read_text(),'License retained')
            self.assertFalse(str(result).startswith('\\\\?\\'))
            self.assertTrue(filesystem_path(result/'CloudGame.exe').is_file())
    def test_exports_game_without_build_tools(self):
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            root=Path(tmp);project=root/'project';project.mkdir();(project/'main.scene').write_text('{}')
            (project/'project.json').write_text(json.dumps({'main_scene':'main.scene'}))
            (project/'.secret').write_text('exclude')
            template=root/'template';template.mkdir();(template/'_internal').mkdir();(template/'CloudPlayer.exe').write_bytes(b'player')
            result=Path(export_portable(project,root/'out','MyGame',template))
            self.assertTrue((result/'MyGame.exe').is_file())
            self.assertTrue((result/'_internal/game_data/project.json').is_file())
            self.assertFalse((result/'_internal/game_data/.secret').exists())
            with self.assertRaises(ValueError):export_portable(project,root/'out','MyGame',template)
    def test_refuses_missing_player(self):
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            root=Path(tmp);(root/'main.scene').write_text('{}');(root/'project.json').write_text(json.dumps({'main_scene':'main.scene'}))
            with self.assertRaises(ValueError):export_portable(root,root.parent/'unused-output','MyGame',root/'missing')

if __name__=='__main__':unittest.main()
