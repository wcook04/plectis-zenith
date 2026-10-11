"""Identity mapping establishes the frozen replay baseline."""
import json
import sys
rows = json.load(sys.stdin)
json.dump([row['probability'] for row in rows], sys.stdout)
