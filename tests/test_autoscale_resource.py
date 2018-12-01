from datetime import datetime
from unittest.mock import MagicMock

from kube_downscaler.scaler import autoscale_resource, EXCLUDE_ANNOTATION, ORIGINAL_REPLICAS_ANNOTATION


def test_downtime_always():
    resource = MagicMock()
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.get_replicas.return_value = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'never', 'always', False, False, now, 0)
    resource.set_replicas.assert_called_once_with(0)
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '1'


def test_downtime_interval():
    resource = MagicMock()
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.get_replicas.return_value = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'always', False, False, now, 0)
    resource.set_replicas.assert_called_once_with(0)
    resource.update.assert_called_once()
    assert resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] == '1'


def test_forced_uptime():
    resource = MagicMock()
    resource.annotations = {EXCLUDE_ANNOTATION: 'false'}
    resource.get_replicas.return_value = 1
    now = datetime.strptime('2018-10-23T21:56:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'always', True, False, now, 0)
    resource.set_replicas.assert_not_called()
    resource.update.assert_not_called()


def test_scale_up():
    resource = MagicMock()
    resource.annotations = {EXCLUDE_ANNOTATION: 'false', ORIGINAL_REPLICAS_ANNOTATION: "3"}
    resource.get_replicas.return_value = 0
    now = datetime.strptime('2018-10-23T15:00:00Z', '%Y-%m-%dT%H:%M:%SZ')
    resource.metadata = {'creationTimestamp': '2018-10-23T21:55:00Z'}
    autoscale_resource(resource, 'Mon-Fri 07:30-20:30 Europe/Berlin', 'never', False, False, now, 0)
    resource.set_replicas.assert_called_once_with(3)
    resource.update.assert_called_once()
