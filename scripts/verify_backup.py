#!/usr/bin/env python3
"""Native pg_dump/pg_restore drill into a newly created disposable database.

Never restores over the source database. Exported data stays in ignored .deployment/.
Run where Docker CLI can access the local PostgreSQL container.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--container',required=True);p.add_argument('--user',required=True)
p.add_argument('--database',required=True);p.add_argument('--output',type=Path,default=Path('.deployment/backup-restore.json'))
a=p.parse_args()
for v in (a.user,a.database):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',v):p.error('Use simple database identifiers')
base=['docker','exec',a.container]
def run(*args,**kwargs):
    return subprocess.run([*base,*args],check=True,capture_output=True,**kwargs).stdout

def sql(database,statement):
    return run('psql','-XAt','-v','ON_ERROR_STOP=1','-U',a.user,'-d',database,'-c',statement).decode().strip()

def counts(database):
    names=sql(database,"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    if not all(re.fullmatch(r'[a-z_][a-z0-9_]*',n) for n in names):raise RuntimeError('Unexpected table identifier')
    return {name:int(sql(database,f'SELECT count(*) FROM "{name}"')) for name in names}

out=a.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
os.chmod(out.parent,0o700)
dump=out.with_suffix('.dump')
restore='ng_restore_'+uuid.uuid4().hex[:12]
source_before=counts(a.database)
# Binary custom-format dump; it is never written into a tracked directory.
with dump.open('wb') as stream:
    os.chmod(dump,0o600)
    subprocess.run([*base,'pg_dump','-U',a.user,'-d',a.database,'-Fc','--no-owner','--no-privileges'],stdout=stream,check=True)
run('createdb','-U',a.user,restore)
try:
    with dump.open('rb') as stream:
        subprocess.run(['docker','exec','-i',a.container,'pg_restore','-U',a.user,'-d',restore,'--single-transaction','--exit-on-error','--no-owner','--no-privileges'],stdin=stream,check=True)
    restored=counts(restore)
    source_after=counts(a.database)
    if source_before != source_after or restored != source_before:raise RuntimeError('Source changed during drill or restored row counts differ')
    # Native FK checks are applied by pg_restore; this also verifies a saved prediction joins to its provenance.
    provenance=int(sql(restore,'SELECT count(*) FROM fraud_predictions p JOIN inference_runs r USING(inference_run_id) JOIN model_versions m USING(model_version_id) JOIN preprocessing_versions v USING(preprocessing_version_id) JOIN graph_snapshots g USING(graph_snapshot_id)'))
    schema=sql(restore,'SELECT version_num FROM alembic_version')
    result={'native_tools':['pg_dump -Fc','pg_restore --single-transaction --exit-on-error'], 'schema_revision':schema,'row_counts':restored,'joined_prediction_provenance_count':provenance,'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest(),'restore_isolated_from_source':True,'source_counts_unchanged':True,'all_counts_match':True,'restored_database':restore,'dump_bytes':dump.stat().st_size}
    out.write_text(json.dumps(result,indent=2)+'\n');os.chmod(out,0o600)
    print(json.dumps({k:v for k,v in result.items() if k not in ('row_counts',)},indent=2))
finally:
    # Only the throwaway database created by this invocation is removed.
    run('dropdb','-U',a.user,restore)
