"""Recoverable commit of accepted raw inputs and official CSVs; single writer only.

The journal is local and ignored by the publication allowlist. Each replacement is
atomic; the set is not. An interrupted intent rolls back before fetching/rebuild.
"""
import base64
import json
import os
from pathlib import Path
import tempfile


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', delete=False) as fh:
            temporary = fh.name
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def journal_path(raw_path):
    return Path(str(raw_path) + '.commit.json')


def _bytes(value):
    return None if value is None else base64.b64decode(value, validate=True)


def _complete(path):
    atomic_write(path, b'{"version":1,"state":"complete"}\n')


def recover(raw_path, allowed_paths):
    """Restore exact preimages, refusing unknown targets or third-party edits."""
    journal = journal_path(raw_path)
    if not journal.exists():
        return False
    intent = json.loads(journal.read_text())
    if intent.get('version') != 1 or intent.get('state') not in {'pending', 'complete'}:
        raise ValueError('Invalid cache commit journal')
    if intent['state'] == 'complete':
        return False
    allowed = {str(Path(p).resolve()) for p in allowed_paths}
    records = intent['files']
    paths = [record['path'] for record in records]
    if not records or len(paths) != len(set(paths)) or not set(paths) <= allowed:
        raise ValueError('Cache commit journal target outside accepted outputs')
    # Check every target before restoring any; an external edit is not ours to undo.
    for record in records:
        path = Path(record['path'])
        current = path.read_bytes() if path.exists() else None
        if current not in (_bytes(record['before']), _bytes(record['after'])):
            raise RuntimeError('Cache recovery found a third-party change')
    for record in records:
        path = Path(record['path'])
        before = _bytes(record['before'])
        if before is None:
            if path.exists():
                path.unlink()
        elif not path.exists() or path.read_bytes() != before:
            atomic_write(path, before)
    _complete(journal)
    return True


def commit(raw_path, raw_content, csv_updates):
    """Persist intent first; on any write failure restore the prior business set."""
    if not csv_updates:
        atomic_write(raw_path, raw_content)
        return
    updates = dict(csv_updates)
    updates[str(raw_path)] = raw_content
    records = []
    for target, after in updates.items():
        path = Path(target).resolve()
        before = path.read_bytes() if path.exists() else None
        records.append({'path': str(path), 'before': None if before is None else
                        base64.b64encode(before).decode(), 'after': base64.b64encode(after).decode()})
    journal = journal_path(raw_path)
    atomic_write(journal, json.dumps({'version': 1, 'state': 'pending', 'files': records}).encode())
    try:
        for record in records:
            atomic_write(record['path'], _bytes(record['after']))
        _complete(journal)
    except Exception:
        recover(raw_path, [record['path'] for record in records])
        raise
