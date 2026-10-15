"""A local fixture tool: provider execution and external data acquisition are absent."""
from pathlib import Path
import json

def run(config, run_dir=None, **kwargs):
    data = config.get('data', config)
    fixture = data.get('fixture')
    if not fixture:
        return {'metadata': {'status':'failure', 'error':'Explicit local observation fixture required'}, 'data': {}}
    return json.loads(Path(fixture).read_text())
