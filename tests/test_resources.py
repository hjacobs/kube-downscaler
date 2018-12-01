from unittest.mock import MagicMock

from pykube.objects import NamespacedAPIObject

from kube_downscaler.resources.deployment import Deployment
from kube_downscaler.resources.stackset import StackSet
from kube_downscaler.resources.statefulset import StatefulSet


def test_deployment():
    api_mock = MagicMock(spec=NamespacedAPIObject, name="APIMock")
    scalable_mock = {'spec': {'replicas': 3}}
    api_mock.obj = MagicMock(name="APIObjMock")
    d = Deployment(api_mock, scalable_mock)
    r = d.get_replicas()
    assert r == 3

    d.set_replicas(10)
    assert scalable_mock['spec']['replicas'] == 10


def test_statefulset():
    api_mock = MagicMock(spec=NamespacedAPIObject, name="APIMock")
    scalable_mock = {'spec': {'replicas': 3}}
    api_mock.obj = MagicMock(name="APIObjMock")
    d = StatefulSet(api_mock, scalable_mock)
    r = d.get_replicas()
    assert r == 3
    d.set_replicas(10)
    assert scalable_mock['spec']['replicas'] == 10


def test_stackset():
    api_mock = MagicMock(spec=NamespacedAPIObject, name="APIMock")
    scalable_mock = {'spec': {'stackTemplate': {'spec': {'replicas': 3}}}}
    api_mock.obj = MagicMock(name="APIObjMock")
    d = StackSet(api_mock, scalable_mock)
    r = d.get_replicas()
    assert r == 3
    d.set_replicas(10)
    assert scalable_mock['spec']['stackTemplate']['spec']['replicas'] == 10
