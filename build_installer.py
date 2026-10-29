"""Build the Cloud Engine Windows installer with a local Inno Setup compiler."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'build/installer-tools/InnoSetup/ISCC.exe')
    parser.add_argument('--source',type=Path,default=ROOT/'releases/Current/CloudEngine.exe')
    parser.add_argument('--output',type=Path,default=ROOT/'releases/Current')
    parser.add_argument('--verify-installer',action='store_true',help='Isolated QA build: workspace shortcuts, no uninstall registry entry')
    args=parser.parse_args()
    source=args.source.resolve(); output=args.output.resolve()
    if not args.compiler.is_file() or not source.is_file():
        parser.error('Compiler or engine EXE does not exist')
    output.mkdir(parents=True,exist_ok=True)
    command=[str(args.compiler.resolve()),'/Qp','/DEngineSource='+str(source),'/DSetupOutput='+str(output)]
    if args.verify_installer: command.append('/DVerifyInstaller=1')
    command.append(str(ROOT/'installer/CloudEngine.iss'))
    subprocess.run(command,check=True,cwd=ROOT)
    from engine import __version__
    name='CloudEngine-Installer-Verification.exe' if args.verify_installer else f'CloudEngine-{__version__}-Setup.exe'
    result=output/name
    from installer_bootstrap import wrap_setup
    wrap_setup(result,ROOT)
    manifest={'product':'Cloud Engine','version':__version__,'interface':'classic',
              'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'installer':name,'installer_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),
              'installer_revision':3,'verification_build':args.verify_installer}
    result.with_suffix('.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(result)


if __name__=='__main__': main()
