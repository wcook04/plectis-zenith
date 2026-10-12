"""Offline authored synthetic daily snapshots for the native progression controller."""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import json
from types import SimpleNamespace
from .demo import synthetic,write,sha,LANES
from tools.observations.derived import run as calculate

class DayCalendar:
    def is_session(self, value):
        date.fromisoformat(str(value)); return True
    def next_session(self,value):
        return datetime.combine(date.fromisoformat(str(value))+timedelta(days=1),datetime.min.time())
    def sessions_in_range(self,start,end):
        first,last=date.fromisoformat(start),date.fromisoformat(end)
        return [datetime.combine(first+timedelta(days=i),datetime.min.time()) for i in range((last-first).days+1)]
    def session_close(self,value):
        day=value.date() if isinstance(value,datetime) else value if isinstance(value,date) else date.fromisoformat(str(value))
        stamp=datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc).replace(hour=12)
        return SimpleNamespace(to_pydatetime=lambda:stamp)

def calendar_for(start,end): return DayCalendar()

def snapshot(dataset,issue_date,output):
    directory=Path(output)
    if directory.exists(): raise ValueError('Snapshot output must be new')
    anchor=calendar_for('','').session_close(issue_date).to_pydatetime().isoformat()
    # Each day is freshly generated from disclosed authored rules, never copied from observations.
    manifest=json.loads((Path(dataset)/'source-manifest.json').read_text())
    origin=date.fromisoformat(manifest['start_date']); offset=(date.fromisoformat(str(issue_date))-origin).days
    for lane in LANES:
        payload=synthetic(lane,anchor,bool(offset%2))
        write(directory/'artifacts'/f'global_{lane}_feed.json',payload)
    derived=calculate({},run_dir=directory);derived.update(id='global_derived_feed',status='success')
    derived['metadata'].update(as_of=anchor,timestamp_iso=anchor)
    write(directory/'artifacts/global_derived_feed.json',derived)
    write(directory/'runtime_context.json',{'as_of':anchor,'time_anchor':anchor,'subject_group':'feeds','synthetic_fixture':True})
    files={str(p.relative_to(directory)):sha(p.read_bytes()) for p in sorted((directory/'artifacts').glob('*.json'))}
    write(directory/'artifact-manifest.json',{'files':files,'data_origin':'authored_synthetic'})
    return {'issue_at_utc':anchor,'observation_at_utc':anchor,'snapshot_sha256':sha(json.dumps(files,sort_keys=True).encode())}
