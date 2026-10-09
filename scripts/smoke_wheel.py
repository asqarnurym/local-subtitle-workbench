"""Install a built wheel into a separate environment and process with sockets blocked."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    output = args.output.resolve()
    with tempfile.TemporaryDirectory(prefix="subtitle-wheel-") as directory:
        venv = Path(directory) / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--offline",
                "--python",
                str(python),
                str(wheel),
                f"numpy=={np.__version__}",
            ],
            check=True,
        )
        code = """
import json, socket, sys
from pathlib import Path
def blocked(*args, **kwargs):
    raise RuntimeError('Network access is forbidden during installed-wheel smoke')
socket.socket = blocked
socket.create_connection = blocked
import subtitle_workbench
from subtitle_workbench.demo import generate
from subtitle_workbench.cli import main
package_path = Path(subtitle_workbench.__file__).resolve()
assert 'site-packages' in package_path.parts, package_path
root = Path(sys.argv[1])
generate(root / 'input')
exit_code = main(['--reference', str(root / 'input/reference.wav'),
                 '--target', str(root / 'input/target.wav'),
                 '--cues', str(root / 'input/cues.json'), '--output', str(root / 'output')])
assert exit_code == 0
timeline = json.loads((root / 'output/timeline.jsonld').read_text())
oracle = json.loads((root / 'input/oracle.json').read_text())
errors = [abs(clip[key] - cue[boundary])
          for cue, clip in zip(oracle['cues'], timeline['hasPart'], strict=True)
          for key, boundary in [('startOffset','start'), ('endOffset','end')]]
assert len(errors) == 12 and max(errors) <= .05, errors
print(json.dumps({'installed_package': str(package_path), 'network_guard': 'passed',
                  'max_absolute_error_ms': max(errors) * 1000}, indent=2))
"""
        subprocess.run([str(python), "-I", "-c", code, str(output)], cwd=directory, check=True)
    manifest = json.loads((output / "output/manifest.json").read_text())
    print(json.dumps({"wheel": wheel.name, "python": manifest["runtime"]["python"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
