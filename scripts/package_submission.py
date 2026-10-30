#!/usr/bin/env python3
"""Package the reviewed report with a credential-free committed source snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=root/'output/submission');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
review=json.loads((root/'docs/submission/evidence/document-review.json').read_text())
reports=[out/'NeuroGraph_DB_Final_Report.pdf',out/'NeuroGraph_DB_Final_Report.docx']
for f in reports:
 if hashlib.sha256(f.read_bytes()).hexdigest()!=review['sha256'][f.name]:raise SystemExit('Report has changed after its visual review: '+f.name)
paths=subprocess.run(['git','ls-files'],cwd=root,text=True,capture_output=True,check=True).stdout.splitlines()
for name in paths:
 parts=Path(name).parts
 if any(x in parts for x in ('.deployment','output','tmp','submission-private')) or (Path(name).name.startswith('.env') and not name.endswith('.env.example')) or Path(name).suffix in ('.dump','.backup','.pem','.key'):
  raise SystemExit('Unsafe file in committed source: '+name)
sha=subprocess.run(['git','rev-parse','HEAD'],cwd=root,text=True,capture_output=True,check=True).stdout.strip()
source=out/'NeuroGraph_DB_Source.zip'
subprocess.run(['git','archive','--format=zip','--prefix=NeuroGraph-DB/','-o',str(source),'HEAD'],cwd=root,check=True)
with zipfile.ZipFile(source) as archive:
 assert archive.testzip() is None
history=subprocess.run(['git','log','--format=%h %ad %s','--date=short'],cwd=root,text=True,capture_output=True,check=True).stdout
(out/'GIT_HISTORY.txt').write_text(history)
guide='''NEUROGRAPH DATABASE SYSTEMS LAB SUBMISSION

Primary document: NeuroGraph_DB_Final_Report.pdf
Editable document: NeuroGraph_DB_Final_Report.docx
Source snapshot: NeuroGraph_DB_Source.zip
Current source commit: '''+sha+'''

Live app: https://frontend-three-snowy-10.vercel.app
Controlled model comparison: https://frontend-three-snowy-10.vercel.app/benchmarks
Public team source: https://github.com/Eldo-John-Giby/NeuroGraph-DB
Private course source: https://github.com/Avaneeshchavan/neurograph-db-submission

Evidence/ contains the schema, ERD source, dictionary, rubric matrix, screenshots,
CI/test/recovery evidence, and a faculty demo guide. GIT_HISTORY.txt records
progressive commit history. Main and dev branches are available on GitHub.

Share the faculty RESEARCHER login separately and privately. No password,
private key, cloud token or native database dump is included in this ZIP.
Benchmark_results.csv and Benchmark_report.json contain the controlled results.
The four architectures use the same chronological train/validation/test split.
The older experiments are historical records, excluded from the matched ranking.
Concatenation has the highest three-seed mean; NeuroGraph has the highest
seed-42 macro F1. Neither result establishes universal superiority.

NeuroGraph_DB_ML_Artifacts.zip is a separate private reproduction companion.
It contains checkpoints, prediction arrays and the sealed serving bundle;
raw source reviews and pretrained encoder weights are obtained separately.
See docs/benchmarks/README.md in the source for fingerprints and commands.
The live application already has its verified bundles installed.

The course handout specifies no submission destination. This package has not
been emailed or uploaded to a course portal. Use the faculty's prescribed
portal or channel when it is known. Faculty approval and final portal handover
follow the course's prescribed process.

Bonus evidence: successful GitHub Actions, automated testing and audit logging.
Custom domain and Docker Hub publication are not claimed. See the normalization
section for the explicit physical provenance redundancy qualification.
'''
(out/'SUBMISSION_GUIDE.txt').write_text(guide)
files=reports+[source,out/'GIT_HISTORY.txt',out/'SUBMISSION_GUIDE.txt']
entries={f.name:f for f in files}
entries['Benchmark_results.csv']=root/'docs/benchmarks/results.csv'
entries['Benchmark_report.json']=root/'docs/benchmarks/comparison.json'
for f in (root/'docs/submission').rglob('*'):
 if f.is_file():entries['Evidence/'+str(f.relative_to(root/'docs/submission'))]=f
manifest={'source_commit':sha,'report_pages':review['pages'],'files':{name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for name,f in entries.items()}}
(out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
package=out/'NeuroGraph_DB_Final_Submission.zip'
with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
 for name,f in entries.items():archive.write(f,name)
 archive.write(out/'MANIFEST.json','MANIFEST.json')
with zipfile.ZipFile(package) as archive:assert archive.testzip() is None
print(json.dumps({'package':str(package),'bytes':package.stat().st_size,'source_commit':sha,'report_pages':review['pages'],'entries':len(entries)+1},indent=2))
