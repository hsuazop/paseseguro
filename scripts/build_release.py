"""Package deployment source, excluding credentials, environments and user data."""
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ('accounts', 'accesos', 'colonias', 'comunidad', 'core', 'facturacion',
           'myproject', 'reportes', 'reservas', 'residentes', 'templates', 'visitas', 'docs')
SUFFIXES = {'.py', '.html', '.css', '.js', '.json', '.svg', '.png', '.md', '.txt'}
files = [ROOT / 'manage.py', ROOT / 'requirements.txt']
for folder in FOLDERS:
    files.extend(path for path in (ROOT / folder).rglob('*') if path.is_file()
                 and not path.is_symlink() and path.suffix in SUFFIXES
                 and '__pycache__' not in path.parts and not path.name.startswith('.'))
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
output = ROOT / 'outputs' / 'deploy'
output.mkdir(parents=True, exist_ok=True)
archive = output / f'paseseguro-{stamp}.tar.gz'
with tarfile.open(archive, 'w:gz') as package:
    for path in sorted(files):
        package.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
metadata = {'release': stamp, 'archive': str(archive),
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'files': [path.relative_to(ROOT).as_posix() for path in sorted(files)]}
(output / 'release.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps({'archive': str(archive), 'files': len(files), 'sha256': metadata['sha256']}))
