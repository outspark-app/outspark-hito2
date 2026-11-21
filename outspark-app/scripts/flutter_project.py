#!/usr/bin/env python3
"""Reproducible Flutter checks/build, including SDKs with Unicode LSP path bugs."""
import argparse
import fcntl
import hashlib
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'build'])
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--api', default='/api')
    parser.add_argument('--landing', default='/')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    flutter = shutil.which('flutter')
    if not flutter:
        parser.error('Flutter SDK no está disponible en PATH.')
    identity = hashlib.sha256(str(root).encode()).hexdigest()[:12]
    cache = Path.home()/'.cache/outspark'/identity
    cache.mkdir(parents=True, exist_ok=True)
    with (cache/'workspace.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        work = root
        if not str(root).isascii():
            work = cache/'project'
            work.mkdir(exist_ok=True)
            for name in ['lib', 'test', 'web', 'assets']:
                target = work/name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(root/name, target)
            for name in ['pubspec.yaml', 'pubspec.lock', 'analysis_options.yaml']:
                shutil.copy2(root/name, work/name)
            print('Verificación sobre copia ASCII con fuentes idénticas:', work, flush=True)
        manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder in ['lib', 'test', 'web', 'assets']
                    for p in (root/folder).rglob('*') if p.is_file()}
        for relative, digest in manifest.items():
            if hashlib.sha256((work/relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError('La copia de fuentes no coincide: '+relative)
        fingerprint = hashlib.sha256((work/'pubspec.yaml').read_bytes()+(work/'pubspec.lock').read_bytes()).hexdigest()
        stamp = cache/'dependencies.sha256'
        if not (work/'.dart_tool/package_config.json').exists() or not stamp.exists() or stamp.read_text()!=fingerprint:
            subprocess.run([flutter, 'pub', 'get'], cwd=work, check=True)
            stamp.write_text(fingerprint)
        commands = [[flutter, 'analyze', '--no-pub'], [flutter, 'test', '--no-pub']] if args.action=='check' else [[
            flutter, 'build', 'web', '--no-pub', '--base-href=/app/', '--no-web-resources-cdn',
            '--dart-define=DEMO_MODE='+str(args.demo).lower(),
            '--dart-define=API_BASE_URL='+args.api,
            '--dart-define=LANDING_URL='+args.landing,
        ]]
        for command in commands:
            subprocess.run(command, cwd=work, check=True)
        if args.action=='build':
            target = root/'dist/client'
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(work/'build/web', target)
            subprocess.run(['node', str(root/'scripts/prepare-sites-build.mjs')], cwd=root, check=True)
        evidence = {'source_sha256':manifest, 'action':args.action, 'source':str(root), 'workspace':str(work)}
        import json
        (cache/'last-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__=='__main__':
    main()
