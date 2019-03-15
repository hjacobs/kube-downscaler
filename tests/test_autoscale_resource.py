import json
import pykube
import pytest
import logging

from datetime import datetime
from unittest.mock import MagicMock

from kube_downscaler.scaler import autoscale_resource, EXCLUDE_ANNOTATION, ORIGINAL_REPLICAS_ANNOTATION, DOWNTIME_REPLICAS_ANNOTATION


@pytest.fixture
def resource():
    res = MagicMock()
    res.kind = 'MockResource'
    res.namespace = 'mock'
    res.name = 'res-1'
    res.annotations = {}
    return res


def test_swallow_exception(resource, caplog):
    caplog.set_level(logging.ERROR)
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': 'invalid-timestamp!'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    assert resource.replicas == 1
    resource.update.assert_not_called()
    # check that the failure was logged
    msg = "Failed to process MockResource mock/res-1 : time data 'invalid-timestamp!' does not match format '%Y-%m-%dT%H:%M:%SZ'"
    assert caplog.record_tuples == [
        ('kube_downscaler.scaler', logging.ERROR, msg)
    ]


def test_exclude(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: 'true'}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    assert resource.replicas == 1
    resource.update.assert_not_called()
    assert ORIGINAL_REPLICAS_ANNOTATION not in resource.annotations


def test_dry_run(resource):
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, dry_run=True, now=now, grace_period=0, downtime_replicas=0)
    assert resource.replicas == 0
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '1'
    # dry run will update the object properties, but won't call the Kubernetes API (update)
    resource.update.assert_not_called()


def test_grace_period(resource):
    resource.annotations = {}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    # resource was only created 1 minute ago, grace period is 5 minutes
    autoscale_resource(resource, 'never', 'always', False, dry_run=False, now=now, grace_period=300, downtime_replicas=0)
    assert resource.replicas == 1
    assert resource.annotations == {}
    resource.update.assert_not_called()


def test_downtime_always(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '1'


def test_downtime_interval(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'always', False, False, now, 0, 0)
    assert resource.replicas == 0
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '1'


def test_forced_uptime(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.replicas = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'always', True, False, now, 0, 0)
    assert resource.replicas == 1
    resource.update.assert_not_called()


def test_scale_up(resource):
    resource.annotations = {EXCLUDE_ANNOTATION: 'false', ORIGINAL_REPLICAS_ANNOTATION: "3"}
    resource.replicas = 0
    now = datetime.strptime('2018-10-23T15:00:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'never', False, False, now, 0, 0)
    assert resource.replicas == 3
    resource.update.assert_called_once()


def test_downtime_replicas_annotation_invalid(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: 'x'}
    resource.replicas = 2
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downtime_replicas_annotation_valid(resource):
    resource.annotations = {DOWNTIME_REPLICAS_ANNOTATION: '1'}
    resource.replicas = 2
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    assert resource.replicas == 1
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '2'


def test_downtime_replicas_invalid(resource):
    resource.replicas = 2
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, "x")
    assert resource.replicas == 2
    resource.update.assert_not_called()


def test_downtime_replicas_valid(resource):
    resource.replicas = 2
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 1)
    assert resource.replicas == 1
    resource.update.assert_called_once()


def test_set_annotation():
    api = MagicMock()
    api.config.namespace = 'myns'
    resource = pykube.StatefulSet(api, {'metadata': {'name': 'foo', 'creationTimestamp': '2019-03-15T21:55:00Z'}, 'spec': {}})
    resource.replicas = 1
    now = datetime.strptime('2019-03-15T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    autoscale_resource(resource, 'never', 'always', False, False, now, 0, 0)
    api.patch.assert_called_once()
    patch_data = json.loads(api.patch.call_args[1]['data'])
    # ensure the original replicas annotation is send to the server
    assert patch_data == {"metadata": {"name": "foo", "creationTimestamp": "2019-03-15T21:55:00Z",
                          'annotations': {ORIGINAL_REPLICAS_ANNOTATION: '1'}}, "spec": {"replicas": 0}}
