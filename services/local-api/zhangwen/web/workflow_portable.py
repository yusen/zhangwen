"""Normalize only a portable copy of verified historical structure references."""
import copy
import json

from .workflow_models import digest, structure_digest
from .workflow_review import records


def checkpoint(value, structure):
    data=copy.deepcopy(value)
    aliases={v['revision']:(digest(v['result']),structure_digest(v['result'])) for v in (structure or {}).get('versions',[])}
    previous_records=records(data)

    def reference(ref):
        if not ref: return
        checksums=aliases.get(ref['revision'])
        # Invalid references remain invalid and are rejected by ProjectSnapshot.
        if checksums and ref['checksum'] in checksums: ref['checksum']=checksums[1]

    def baseline(ref):
        reference(ref.get('structure'))
        ref['fingerprint']=digest({k:v for k,v in ref.items() if k!='fingerprint'})

    for run in data['runs']: baseline(run['baseline'])
    for change in data.get('changes',[]):
        baseline(change['baseline'])
        for task in change['tasks']: reference(task.get('structure'))
    current_records=records(data)
    for message in data['messages']:
        if message['role']!='assistant': continue
        payload=json.loads(message['content'])
        source=(payload.get('review') or {}).get('source')
        if not source: continue
        old=copy.deepcopy(source)
        baseline(source['baseline'])
        if source['records']==previous_records: source['records']=current_records
        if source!=old: message['content']=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
    return data
