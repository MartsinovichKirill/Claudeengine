import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from build_exe import build

class OnefileBootstrapTests(unittest.TestCase):
    def test_windows_onefile_is_wrapped_after_successful_build(self):
        with tempfile.TemporaryDirectory(dir='build') as output,patch('build_exe.ensure_pyinstaller',return_value=True),patch('build_exe.subprocess.call',return_value=0),patch('launcher_build.wrap_onefile',return_value=0) as wrap,patch('builtins.print'):
            self.assertEqual(build(root=str(Path.cwd()),output=output,onefile=True),0)
            wrap.assert_called_once()
            self.assertEqual(wrap.call_args.args[0],Path(output)/'CloudEngine.exe')

if __name__=='__main__':unittest.main()
