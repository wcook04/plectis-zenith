# Witness-preserving continuation learner

This is a portable, offline result from the maintained
[`research/continuation_learning.py`](../../../research/continuation_learning.py)
and [`scripts/demo_continuation_learning.py`](../../../scripts/demo_continuation_learning.py).
The learner is an adapted ordinary rational-linear diagnostic from Zenith
progress return 02. The eight native configurations and their challenge panels
are authored fixtures adapted from that return, not independent applications.
No model, account, network connection, or archived return directory is needed.

From the repository root, with Python 3.11 or later:

```sh
python3 -B - <<'PY'
import json, subprocess, sys
from pathlib import Path
saved = json.loads(Path('examples/continuation-memory/witness-preserving-v1/results.json').read_text())
replay = json.loads(subprocess.check_output(
    [sys.executable, '-B', 'scripts/demo_continuation_learning.py', '--native']))
assert replay['minimal_witness'] == saved['minimal_witness']
assert replay['native_panel']['rows'] == saved['native_panel']['rows']
assert replay['native_panel']['development_words'] == saved['native_panel']['development_words']
assert replay['native_panel']['short_words'] == saved['native_panel']['short_words']
assert replay['native_panel']['longer_words'] == saved['native_panel']['longer_words']
print('finite results match; archived Python/SQLite:',
      saved['native_panel']['python'], saved['native_panel']['sqlite'])
PY
```

The saved run used Python 3.13.7 and SQLite 3.53.4. Runtime-version metadata
will differ on other installations, and SQLite behavior may differ; an exact
byte comparison is meaningful only with a matching runtime. `manifest.json`
binds the saved result and current reproducible source bytes. Run the focused
regressions with `python3 -B -m pytest -q tests/test_continuation_learning.py`
after installing this repository's test dependencies.

The corrected witness-cold learner finishes all eight development fits with
11,395 acquisition source calls. A generic, experience-free singleton-question
bank finishes the same eight fits with 11,379 calls, saving 16 on deque-4 and
tying every other target. Thus these results show **no acquired-question gain**
over a competent ordinary control. The small unary deque reproduction fits in
ten source calls with five rational-linear coordinates; a one-integer nonlinear
counter is simpler. Later panels reveal misses: UTF-8 scores 4,903/4,913 on
short words, SQLite rowid 190/192 and AUTOINCREMENT 191/192 on longer words.
Finite panels certify none of these programs universally. Source calls above
count acquisition only; later scoring calls are separate and are not pooled
with the conformance campaign.
