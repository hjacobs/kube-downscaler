from datetime import datetime
from datetime import timedelta
from datetime import timezone

from pykube import Deployment

from kube_downscaler.scaler import within_grace_period


def test_within_grace_period():
    now = datetime.now(timezone.utc)
    ts = now - timedelta(minutes=5)
    deploy = Deployment(
        None, {"metadata": {"creationTimestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}}
    )
    assert within_grace_period(deploy, 900, now)
    assert not within_grace_period(deploy, 180, now)


def test_within_grace_period_deployment_time_annotation():
    now = datetime.now(timezone.utc)
    creation_time = now - timedelta(days=7)
    deployment_time = now - timedelta(minutes=5)
    deploy = Deployment(
        None,
        {
            "metadata": {
                "creationTimestamp": creation_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "annotations": {
                    "my-deployment-time": deployment_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                },
            }
        },
    )
    assert within_grace_period(deploy, 900, now)
    assert not within_grace_period(deploy, 180, now)
