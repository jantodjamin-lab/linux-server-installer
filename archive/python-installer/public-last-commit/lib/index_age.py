"""Read-only cached Release ages; timestamps never establish repository trust."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from sources import release_paths


def index_age(root, allow_mirrors=(), now=None):
    root = Path(root); now = now or datetime.now(timezone.utc)
    records = []
    for name in sorted(release_paths(root, allow_mirrors, enforce_policy=False)):
        path = root/'var/lib/apt/lists'/name
        if not path.is_file() or path.is_symlink():
            records.append({'index': name, 'missing': True}); continue
        dates = [datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)]
        for line in path.read_text(errors='replace').splitlines():
            if line.startswith('Date: '):
                try:
                    date = parsedate_to_datetime(line[6:])
                    if date.tzinfo is not None: dates.append(date)
                except (TypeError, ValueError, OverflowError): pass
                break
        records.append({'index': name, 'age_days': round(max(0, max((now-date).total_seconds()/86400 for date in dates)), 1)})
    stamp = root/'var/lib/apt/periodic/update-success-stamp'
    stamp_days = round(max(0, (now.timestamp()-stamp.stat().st_mtime)/86400), 1) if stamp.is_file() and not stamp.is_symlink() else None
    days = max([r['age_days'] for r in records if 'age_days' in r] + ([stamp_days] if stamp_days is not None else []), default=None)
    return {'age_days': days, 'update_success_stamp_age_days': stamp_days, 'indexes': records,
            'status': 'WARN' if days is None or days > 7 or any(r.get('missing') for r in records) else 'PASS'}
