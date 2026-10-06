"""Fictional mappings used exclusively by isolated verification processes."""

import json
from pathlib import Path


MAPPINGS = [
    {'from': '陈星河', 'to': '陈瑞恩'},
    {'from': 'chenxinghe', 'to': 'ryanchen',
     'casePairs': [{'from': 'ChenXingHe', 'to': 'RyanChen'}]},
    {'from': '云杉智科', 'to': '海岚数科'},
    {'from': 'cedarbyte', 'to': 'harborwave'},
]


def write_config(workspace):
    """Return an explicit private config path; never read a user's mappings."""
    path = Path(workspace) / 'synthetic-private-mappings.json'
    path.write_text(json.dumps({'mappings': MAPPINGS}, ensure_ascii=False) + '\n')
    path.chmod(0o600)
    return path
