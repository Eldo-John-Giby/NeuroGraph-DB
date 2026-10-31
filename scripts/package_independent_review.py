#!/usr/bin/env python3
"""Create a public-source review pack without local credentials or private reports."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / 'output/review'
out.mkdir(parents=True, exist_ok=True)
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
archive = out / 'NeuroGraph_DB_Review_Pack.zip'
subprocess.run(['git', 'archive', '--format=zip', '--prefix=NeuroGraph-DB/', '-o', str(archive), 'HEAD'], cwd=root, check=True)
with zipfile.ZipFile(archive, 'a', compression=zipfile.ZIP_DEFLATED) as pack:
    for name in pack.namelist():
        path = Path(name)
        if any(part in {'.deployment', 'output', 'tmp', 'submission-private', '.aws', '.vercel'} for part in path.parts):
            raise SystemExit('Unexpected private path in source snapshot: ' + name)
        if path.name.startswith('.env') and not path.name.endswith('.env.example'):
            raise SystemExit('Unexpected environment file: ' + name)
    start = 'INDEPENDENT REVIEW START HERE\n\nSource commit: ' + sha + '\n\nRead NeuroGraph-DB/docs/review/INDEPENDENT_REVIEW.md. It contains the complete review request, reading map and evidence boundaries. Supply the original course rubric separately. Screenshots of the authenticated workflows are in docs/submission/assets. A live browser review requires a separately authorized demo account; no passwords are included.\n\nThe archive includes public source and published benchmark evidence, not raw datasets, trained weights, production data, private cover identifiers or cloud credentials. An external review has not already been performed.\n'
    pack.writestr('REVIEW_START_HERE.txt', start)
    entries = {n: hashlib.sha256(pack.read(n)).hexdigest() for n in pack.namelist() if not n.endswith('/')}
    pack.writestr('REVIEW_MANIFEST.json', json.dumps({'source_commit': sha, 'files_sha256': entries}, indent=2) + '\n')
with zipfile.ZipFile(archive) as pack:
    assert pack.testzip() is None
print(json.dumps({'path': str(archive), 'source_commit': sha, 'bytes': archive.stat().st_size, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}, indent=2))
