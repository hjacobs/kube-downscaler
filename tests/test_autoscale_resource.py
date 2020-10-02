import json
import logging
from datetime import datetime
from datetime import timezone
from unittest.mock import MagicMock

import pykube
import pytest
from pykube import Deployment
from pykube import HorizontalPodAutoscaler

from kube_downscaler.resources.stack import Stack
from kube_downscaler.scaler import autoscale_resource
from kube_downscaler.scaler import DOWNSCALE_PERIOD_ANNOTATION
from kube_downscaler.scaler import DOWNTIME_REPLICAS_ANNOTATION
from kube_downscaler.scaler import EXCLUDE_ANNOTATION
from kube_downscaler.scaler import EXCLUDE_UNTIL_ANNOTATION
from kube_downscaler.scaler import ORIGINAL_REPLICAS_ANNOTATION
from kube_downscaler.scaler import UPSCALE_PERIOD_ANNOTATION


@pytest.fixture
def resource():
    res = MagicMock()
    res.kind = "MockResource"
    res.namespace = "mock"
    res.name = "res-1"
    res.annotations = {}
    return res


def test_swallow_exception(monkeypatch, resource, caplog):
    caplog.set_level(logging.ERROR)
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "invalid-timestamp!"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 1
    resource.update.assert_not_called()
    # check that the failure was logged
    msg = "Failed to process MockResource mock/res-1: time data 'invalid-timestamp!' does not match any format (%Y-%m-%dT%H:%M:%SZ, %Y-%m-%dT%H:%M, %Y-%m-%d %H:%M, %Y-%m-%d)"
    assert caplog.record_tuples == [("kube_downscaler.scaler", logging.ERROR, msg)]


def test_swallow_exception_with_event(monkeypatch, resource, caplog):
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.add_event", MagicMock(return_value=None)
    )
    caplog.set_level(logging.ERROR)
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "invalid-timestamp!"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "never",
        "always",
        False,
        False,
        now,
        0,
        0,
        enable_events=True,
    )
    assert resource.replicas == 1
    resource.update.assert_not_called()
    # check that the failure was logged
    msg = "Failed to process MockResource mock/res-1: time data 'invalid-timestamp!' does not match any format (%Y-%m-%dT%H:%M:%SZ, %Y-%m-%dT%H:%M, %Y-%m-%d %H:%M, %Y-%m-%d)"
    assert caplog.record_tuples == [("kube_downscaler.scaler", logging.ERROR, msg)]


def test_exclude(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "true"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 1
    resource.update.assert_not_called()
    assert ORIGINAL_REPLICAS_ANNOTATION not in resource.annotations


def test_exclude_until_invalid_time(resource, caplog):
    caplog.set_level(logging.WARNING)
    resource.annotations = {EXCLUDE_UNTIL_ANNOTATION: "some-invalid-timestamp"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "never",
        "always",
        forced_uptime=False,
        dry_run=True,
        now=now,
    )
    assert resource.replicas == 0
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"
    # dry run will update the object properties, but won't call the Kubernetes API (update)
    resource.update.assert_not_called()

    # check that the warning was logged
    msg = "Invalid annotation value for 'downscaler/exclude-until' on mock/res-1: time data 'some-invalid-timestamp' does not match any format (%Y-%m-%dT%H:%M:%SZ, %Y-%m-%dT%H:%M, %Y-%m-%d %H:%M, %Y-%m-%d)"
    assert caplog.record_tuples == [("kube_downscaler.scaler", logging.WARNING, msg)]


def test_dry_run(resource):
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "never",
        "always",
        False,
        dry_run=True,
        enable_events=False,
        now=now,
        grace_period=0,
        downtime_replicas=0,
    )
    assert resource.replicas == 0
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"
    # dry run will update the object properties, but won't call the Kubernetes API (update)
    resource.update.assert_not_called()


def test_grace_period(resource):
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    # resource was only created 1 minute ago, grace period is 5 minutes
    autoscale_resource(
        resource,
        "never",
        "never",
        "never",
        "always",
        False,
        dry_run=False,
        enable_events=False,
        now=now,
        grace_period=300,
        downtime_replicas=0,
    )
    assert resource.replicas == 1
    assert resource.annotations == {}
    resource.update.assert_not_called()


def test_downtime_always(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"


def test_downtime_interval(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "Mon-Fri 07:30-20:30 Europe/Berlin",
        "always",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"


def test_forced_uptime(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "Mon-Fri 07:30-20:30 Europe/Berlin",
        "always",
        True,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 1
    resource.update.assert_not_called()


def test_autoscale_bad_resource():
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    try:
        autoscale_resource(
            None, "never", "never", "never", "always", False, False, now, 0, 0
        )
        raise AssertionError("Failed to error out with a bad resource")
    except Exception:
        pass


def test_scale_up(resource):
    resource.annotations = {
        EXCLUDE_ANNOTATION: "false",
        ORIGINAL_REPLICAS_ANNOTATION: "3",
    }
    resource.replicas = 0
    now = datetime.strptime("2018-10-23T15:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "Mon-Fri 07:30-20:30 Europe/Berlin",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 3
    resource.update.assert_called_once()


def test_scale_up_downtime_replicas_annotation(resource):
    """Cli argument downtime-replicas is 1, but for 1 specific deployment we want 0."""
    resource.annotations = {
        DOWNTIME_REPLICAS_ANNOTATION: "0",
        ORIGINAL_REPLICAS_ANNOTATION: "1",
    }
    resource.replicas = 0
    now = datetime.strptime("2018-10-23T15:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "never",
        "Mon-Fri 07:30-20:30 Europe/Berlin",
        "never",
        False,
        False,
        now,
        0,
        1,
    )
    assert resource.replicas == 1
    resource.update.assert_called_once()


def test_downtime_replicas_annotation_invalid(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: "x"}
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downtime_replicas_annotation_valid(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: "1"}
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 1
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "2"


def test_downtime_replicas_invalid(resource):
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, "x"
    )
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downtime_replicas_valid(resource):
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 1
    )
    assert resource.replicas == 1
    resource.update.assert_called_once()


def test_set_annotation():
    api = MagicMock()
    api.config.namespace = "myns"
    resource = pykube.StatefulSet(
        api,
        {
            "metadata": {"name": "foo", "creationTimestamp": "2019-03-15T21:55:00Z"},
            "spec": {},
        },
    )
    resource.replicas = 1
    now = datetime.strptime("2019-03-15T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    api.patch.assert_called_once()
    patch_data = json.loads(api.patch.call_args[1]["data"])
    # ensure the original replicas annotation is send to the server
    assert patch_data == {
        "metadata": {
            "name": "foo",
            "creationTimestamp": "2019-03-15T21:55:00Z",
            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: "1"},
        },
        "spec": {"replicas": 0},
    }


def test_downscale_always(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "always", "always", "never", False, False, now, 0, 0
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"


def test_downscale_period(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "Mon-Fri 20:30-24:00 Europe/Berlin",
        "always",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "1"


def test_downscale_period_overlaps(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: "1"}
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "Mon-Fri 20:30-24:00 Europe/Berlin",
        "Mon-Fri 20:30-24:00 Europe/Berlin",
        "always",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downscale_period_not_match(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: "1"}
    resource.replicas = 2
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "Mon-Fri 07:30-10:00 Europe/Berlin",
        "always",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downscale_period_resource_overrides_never(resource):
    resource.annotations = {
        DOWNSCALE_PERIOD_ANNOTATION: "Mon-Fri 20:30-24:00 Europe/Berlin"
    }
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "always", "never", False, False, now, 0, 0
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()


def test_downscale_period_resource_overrides_namespace(resource):
    resource.annotations = {
        DOWNSCALE_PERIOD_ANNOTATION: "Mon-Fri 20:30-24:00 Europe/Berlin"
    }
    resource.replicas = 1
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "never",
        "Mon-Fri 22:00-24:00 Europe/Berlin",
        "always",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 0
    resource.update.assert_called_once()


def test_upscale_period_resource_overrides_never(resource):
    resource.annotations = {
        UPSCALE_PERIOD_ANNOTATION: "Mon-Fri 20:30-24:00 Europe/Berlin",
        ORIGINAL_REPLICAS_ANNOTATION: 1,
    }
    resource.replicas = 0
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "always", "never", False, False, now, 0, 0
    )
    assert resource.replicas == 1
    resource.upd


def test_upscale_period_resource_overrides_namespace(resource):
    resource.annotations = {
        UPSCALE_PERIOD_ANNOTATION: "Mon-Fri 20:30-24:00 Europe/Berlin",
        ORIGINAL_REPLICAS_ANNOTATION: 1,
    }
    resource.replicas = 0
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource,
        "Mon-Fri 22:00-24:00 Europe/Berlin",
        "never",
        "always",
        "never",
        False,
        False,
        now,
        0,
        0,
    )
    assert resource.replicas == 1
    resource.upd


def test_downscale_stack_deployment_ignored():
    resource = MagicMock()
    resource.kind = Deployment.kind
    resource.version = Deployment.version
    resource.namespace = "mock"
    resource.name = "res-1"
    resource.metadata = {
        "creationTimestamp": "2018-10-23T21:55:00Z",
        "ownerReferences": [{"apiVersion": Stack.version, "kind": Stack.kind}],
    }
    resource.replicas = 1
    resource.annotations = {}

    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 0
    )
    assert resource.replicas == 1
    resource.update.assert_not_called()
    assert ORIGINAL_REPLICAS_ANNOTATION not in resource.annotations


def test_downscale_replicas_not_zero(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: "false"}
    resource.replicas = 3
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    resource.metadata = {"creationTimestamp": "2018-10-23T21:55:00Z"}
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 1
    )
    assert resource.replicas == 1
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "3"
    autoscale_resource(
        resource, "never", "never", "never", "always", False, False, now, 0, 1
    )
    assert resource.replicas == 1
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == "3"
    resource.update.assert_called_once()


def test_downscale_stack_with_autoscaling():
    stack = Stack(
        None,
        {
            "metadata": {
                "name": "my-stack",
                "namespace": "my-ns",
                "creationTimestamp": "2018-10-23T21:55:00Z",
            },
            "spec": {"horizontalPodAutoscaler": {"maxReplicas": 4}},
        },
    )

    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    assert stack.replicas == 4
    autoscale_resource(
        stack,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        forced_uptime=False,
        dry_run=True,
        now=now,
    )
    assert stack.replicas == 0


def test_upscale_stack_with_autoscaling():
    stack = Stack(
        None,
        {
            "metadata": {
                "name": "my-stack",
                "namespace": "my-ns",
                "creationTimestamp": "2018-10-23T21:55:00Z",
                "annotations": {ORIGINAL_REPLICAS_ANNOTATION: 4},
            },
            "spec": {"autoscaler": {"maxReplicas": 4}, "replicas": 0},
        },
    )

    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    assert stack.replicas == 0
    autoscale_resource(
        stack,
        upscale_period="never",
        downscale_period="never",
        default_uptime="always",
        default_downtime="never",
        forced_uptime=False,
        dry_run=True,
        enable_events=False,
        now=now,
    )
    assert stack.obj["spec"]["replicas"] is None
    assert stack.replicas == 4
    assert stack.annotations[ORIGINAL_REPLICAS_ANNOTATION] is None


def test_downscale_hpa_with_autoscaling():
    hpa = HorizontalPodAutoscaler(
        None,
        {
            "metadata": {
                "name": "my-hpa",
                "namespace": "my-ns",
                "creationTimestamp": "2018-10-23T21:55:00Z",
                "annotations": {DOWNTIME_REPLICAS_ANNOTATION: str(1)},
            },
            "spec": {"minReplicas": 4},
        },
    )
    now = datetime.strptime("2018-10-23T21:56:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    autoscale_resource(
        hpa,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        forced_uptime=False,
        dry_run=True,
        now=now,
    )
    assert hpa.obj["spec"]["minReplicas"] == 1
    assert hpa.obj["metadata"]["annotations"][ORIGINAL_REPLICAS_ANNOTATION] == str(4)


def test_upscale_hpa_with_autoscaling():
    hpa = HorizontalPodAutoscaler(
        None,
        {
            "metadata": {
                "name": "my-hpa",
                "namespace": "my-ns",
                "creationTimestamp": "2018-10-23T21:55:00Z",
                "annotations": {
                    DOWNTIME_REPLICAS_ANNOTATION: str(1),
                    ORIGINAL_REPLICAS_ANNOTATION: str(4),
                },
            },
            "spec": {"minReplicas": 1},
        },
    )
    now = datetime.strptime("2018-10-23T22:15:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    autoscale_resource(
        hpa,
        upscale_period="never",
        downscale_period="never",
        default_uptime="always",
        default_downtime="never",
        forced_uptime=False,
        dry_run=True,
        now=now,
    )
    assert hpa.obj["spec"]["minReplicas"] == 4
    assert hpa.obj["metadata"]["annotations"][ORIGINAL_REPLICAS_ANNOTATION] is None
