"""Read explicit numeric observation rows without interpreting acquisition clocks."""
def _iter_value_rows(payload):
    data = payload.get('data', payload)
    if isinstance(data, dict):
        for row in data.get('observations', []):
            if isinstance(row, dict):
                yield row


def _load_value_index(payload):
    result = {}
    for row in _iter_value_rows(payload):
        target = row.get('target_id')
        observed = row.get('observed_at')
        if target and observed:
            result.setdefault(target, {})[observed] = row.get('value')
    return result
