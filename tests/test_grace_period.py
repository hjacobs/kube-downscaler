from datetime import datetime, timedelta, timezone
from pykube import Deployment
from kube_downscaler.scaler import within_grace_period


def test_within_grace_period():
    now = datetime.now(timezone.utc)
    ts = now - timedelta(minutes=5)
    deploy = Deployment(None, {'metadata': {'creationTimestamp': ts.strftime('%Y-%m-%dT%H:%M:%SZ')}})
    assert within_grace_period(deploy, 900, now)
    assert not within_grace_period(deploy, 180, now)
