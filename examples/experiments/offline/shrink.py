"""One declared change: shrink each probability toward 0.5 by factor 0.7."""
import json
import sys
rows = json.load(sys.stdin)
json.dump([0.5 + 0.7 * (row['probability'] - 0.5) for row in rows], sys.stdout)
