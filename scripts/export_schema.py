#!/usr/bin/env python3
"""Export the current ORM schema, complete ERD and field dictionary without database data."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import Base
import app.models
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import dialect

root = Path(__file__).resolve().parents[1]
out = root / 'docs/submission'
out.mkdir(parents=True, exist_ok=True)
tables = []
for t in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
    cols = []
    for c in t.columns:
        cols.append({'name':c.name,'type':str(c.type.compile(dialect=dialect())), 'nullable':c.nullable,
                     'pk':c.primary_key,'foreign_keys':[str(f.target_fullname) for f in c.foreign_keys],
                     'default':str(c.server_default.arg) if c.server_default else None})
    constraints = []
    for c in t.constraints:
        if isinstance(c,CheckConstraint): constraints.append({'kind':'CHECK','name':c.name,'expression':str(c.sqltext)})
        if isinstance(c,UniqueConstraint): constraints.append({'kind':'UNIQUE','name':c.name,'columns':[x.name for x in c.columns]})
    indexes = [{'name':i.name,'columns':[str(x.name) for x in i.columns],'unique':i.unique} for i in t.indexes]
    tables.append({'name':t.name,'columns':cols,'constraints':constraints,'indexes':sorted(indexes,key=lambda x:x['name'])})
(out/'schema.json').write_text(json.dumps({'table_count':len(tables),'tables':tables},indent=2)+'\n')
erd=['# Complete relational entity relationship diagram','','Generated from `backend/app/models.py`. Every application table is included. Alembic owns physical migrations.','','```mermaid','erDiagram']
for t in tables:
    pk=[c['name'] for c in t['columns'] if c['pk']]
    assert pk,t['name']
    for c in t['columns']:
        for fk in c['foreign_keys']:
            parent=fk.split('.')[0]
            erd.append(f"    {parent.upper()} {'o|' if c['nullable'] else '||'}--o{{ {t['name'].upper()} : {c['name']}")
    erd.append(f"    {t['name'].upper()} {{")
    for c in t['columns']:
        key=' PK' if c['pk'] else ' FK' if c['foreign_keys'] else ''
        erd.append(f"        {c['type'].split('(')[0].lower().replace(' ','_')} {c['name']}{key}")
    erd.append('    }')
erd+=['```','','A table with a composite primary key uses the full key shown. Optional actors use SET NULL; provenance references use RESTRICT. A child-to-parent relationship expresses one parent per row; it does not imply that the parent must have a child.']
(out/'ERD.md').write_text('\n'.join(erd)+'\n')
dd=['# Current relational schema and data dictionary','','This generated dictionary describes all '+str(len(tables))+' SQLAlchemy application tables. `alembic_version` is migration bookkeeping, not a domain entity. Views are derived relations, not additional base tables.','']
for t in tables:
    dd+=['## '+t['name'],'','| Column | PostgreSQL type | Null | Key or default |','|---|---|---|---|']
    for c in t['columns']:
        rules=(['PK'] if c['pk'] else [])+['FK '+f for f in c['foreign_keys']]+(['default '+c['default']] if c['default'] else [])
        dd.append(f"| `{c['name']}` | {c['type']} | {'Yes' if c['nullable'] else 'No'} | {'; '.join(rules) or '-'} |")
    dd+=['','Constraints:']+[f"- {c['kind']} {c.get('expression', ', '.join(c.get('columns',[])))}" for c in t['constraints']]
    dd+=['','Indexes:']+[f"- {i['name']}: {', '.join(i['columns'])}{' (unique)' if i['unique'] else ''}" for i in t['indexes']]+['']
(out/'DATA_DICTIONARY.md').write_text('\n'.join(dd).rstrip()+'\n')
print(json.dumps({'tables':len(tables),'foreign_key_columns':sum(bool(c['foreign_keys']) for t in tables for c in t['columns']),'primary_keys_in_every_table':True}))
