from pathlib import Path
import os
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent
def build():
    compiler = shlex.split(os.environ.get('CC', 'gcc'), posix=os.name != 'nt')
    sources = ['noise', 'biomes', 'layers', 'biomenoise', 'generator', 'finders', 'util', 'quadbase']
    name = 'city-engine.exe' if os.name == 'nt' else 'city-engine'
    command = compiler + ['-O2', '-fwrapv', '-Ivendor/cubiomes', 'engine.c']
    command += [f'vendor/cubiomes/{s}.c' for s in sources]
    subprocess.run(command + ['-lm', '-o', name], cwd=ROOT, check=True)
if __name__ == '__main__':
    build()
