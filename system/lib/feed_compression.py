"""Generic feed observations remain complete in reasoning context.

The compact_feeds profile projects redundant acquisition metadata separately;
this seam never selects or drops observation rows.
"""
def compress_reasoning_feed_envelope(repo_root, dep_id, envelope):
    return envelope
