from datetime import datetime
from datetime import timedelta
from datetime import timezone

from pykube import Deployment

from kube_downscaler.scaler import within_grace_period

ANNOTATION_NAME = "my-deployment-time"


def test_within_grace_period_creation_time():
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
                    ANNOTATION_NAME: deployment_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                },
            }
        },
    )
    assert within_grace_period(
        deploy, 900, now, deployment_time_annotation=ANNOTATION_NAME
    )
    assert not within_grace_period(
        deploy, 180, now, deployment_time_annotation=ANNOTATION_NAME
    )


def test_within_grace_period_without_deployment_time_annotation():
    now = datetime.now(timezone.utc)
    creation_time = now - timedelta(days=7)

    # without annotation set
    deploy = Deployment(
        None,
        {
            "metadata": {
                "creationTimestamp": creation_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        },
    )
    assert not within_grace_period(
        deploy, 900, now, deployment_time_annotation=ANNOTATION_NAME
    )
    assert not within_grace_period(
        deploy, 180, now, deployment_time_annotation=ANNOTATION_NAME
    )


def test_within_grace_period_wrong_deployment_time_annotation():
    now = datetime.now(timezone.utc)
    creation_time = now - timedelta(days=7)

    deploy = Deployment(
        None,
        {
            "metadata": {
                # name & namespace must be set as it will be logged (warning message)
                "name": "my-deploy",
                "namespace": "my-ns",
                "creationTimestamp": creation_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "annotations": {ANNOTATION_NAME: "some-invalid-value"},
            }
        },
    )
    assert not within_grace_period(
        deploy, 900, now, deployment_time_annotation=ANNOTATION_NAME
    )
    assert not within_grace_period(
        deploy, 180, now, deployment_time_annotation=ANNOTATION_NAME
    )
