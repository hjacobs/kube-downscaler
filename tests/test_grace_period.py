from datetime import datetime, timedelta
from kube_downscaler.main import Deployment, within_grace_period


def test_within_grace_period():
    now = datetime.utcnow()
    ts = now - timedelta(minutes=5)
    deploy = Deployment(None, {'metadata': {'creationTimestamp': ts.strftime('%Y-%m-%dT%H:%M:%SZ')}})
    assert within_grace_period(deploy, 900)
    assert not within_grace_period(deploy, 180)
