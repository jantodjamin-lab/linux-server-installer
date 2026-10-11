"""Derive fresh-VM fault jobs ONLY from successful actual smoke evidence."""
import json
from pathlib import Path
import sys


def matrix(root):
    jobs=[]
    for profile in ('APP','DB','APP+DB'):
        files=list((Path(root)/('layer3-'+profile)).glob('**/case-000/artifacts/result.json'))
        if len(files)!=1:raise ValueError('missing-unique-smoke-evidence: '+profile)
        result=json.loads(files[0].read_text())
        count=result.get('journal_events')
        if result.get('status')!='PASS' or result.get('fault_event')!=0 or result.get('profile')!=profile:
            raise ValueError('invalid-smoke-evidence: '+profile)
        if type(count) is not int or not 1<=count<=80:raise ValueError('invalid-event-count: '+profile)
        jobs.extend({'profile':profile,'event':event} for event in range(1,count+1))
    return {'include':jobs}


if __name__=='__main__':
    print(json.dumps(matrix(sys.argv[1]),separators=(',',':')))
