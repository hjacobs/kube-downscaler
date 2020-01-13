from unittest.mock import MagicMock
from unittest.mock import patch

from kube_downscaler.scaler import FORCE_UPTIME_ANNOTATION
from kube_downscaler.scaler import pods_force_uptime


@patch("pykube.Pod")
@patch("pykube.HTTPClient")
def test_pods_force_uptime_non_running(c, p):
    pod1 = MagicMock()
    pod1.obj = {"status": {"phase": "Succeeded"}}
    pod1.annotations = {FORCE_UPTIME_ANNOTATION: "true"}
    pod2 = MagicMock()
    pod2.obj = {"status": {"phase": "Succeeded"}}
    pod2.annotations = {FORCE_UPTIME_ANNOTATION: "true"}
    p.objects.return_value.filter.return_value = [pod1, pod2]
    force = pods_force_uptime(c, namespace="")
    assert not force


@patch("pykube.Pod")
@patch("pykube.HTTPClient")
def test_pods_force_uptime(c, p):
    pod1 = MagicMock()
    pod1.obj = {"status": {"phase": "Running"}}
    pod1.annotations = {FORCE_UPTIME_ANNOTATION: "true"}
    p.objects.return_value.filter.return_value = [pod1]
    force = pods_force_uptime(c, namespace="")
    assert force

    pod1 = MagicMock()
    pod1.obj = {"status": {"phase": "Running"}}
    pod1.annotations = {FORCE_UPTIME_ANNOTATION: "true"}
    p.objects.return_value.filter.return_value = [pod1]
    force = pods_force_uptime(c, namespace="")
    assert force
