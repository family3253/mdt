from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

case_id = "CASE-DEPLOY-CHECK-001"

print(client.get('/health').json())
print(client.post('/cases/open', json={
    'case_id': case_id,
    'patient_summary': {'chief_complaint': '发热', 'suspected_source': '肺部'},
    'danger_flag': False
}).json())

for ev in [
    {
        'case_id': case_id,
        'round_no': 1,
        'event_type': 'agent_opinion',
        'speaker': 'mdt-id',
        'specialty': 'infectious_disease',
        'payload': {'claim': '经验性覆盖MDR-GNB，24h复评'},
        'confidence': 0.8
    },
    {
        'case_id': case_id,
        'round_no': 1,
        'event_type': 'agent_opinion',
        'speaker': 'mdt-pharm',
        'specialty': 'clinical_pharmacy',
        'payload': {'claim': '按eGFR调整剂量，监测肾毒性'},
        'confidence': 0.82
    },
    {
        'case_id': case_id,
        'round_no': 2,
        'event_type': 'consensus_updated',
        'speaker': 'mdt-orchestrator',
        'specialty': 'mdt',
        'payload': {'status': 'majority', 'recommendation': '覆盖+剂量分层+复评'}
    }
]:
    print(client.post('/events', json=ev).json()['accepted'])

res = client.get(f'/cases/{case_id}/events').json()
print('events_count=', res['count'])
print('last_event=', res['events'][-1]['event_type'], res['events'][-1]['speaker'])
