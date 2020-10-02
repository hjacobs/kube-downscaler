from unittest.mock import MagicMock

import pytest
from pykube.query import Query

from kube_downscaler import helper


@pytest.fixture
def resource():
    res = MagicMock()
    res.kind = "MockResource"
    res.namespace = "mock"
    res.name = "res-1"
    res.annotations = {}
    res.metadata = {"uid": "id-1"}
    return res


@pytest.fixture
def event():
    res = MagicMock()
    res.kind = "Event"
    res.namespace = "mock"
    res.name = "event-1"
    res.message = "test message"
    res.obj = {"count": 1, "message": "test message"}
    res.annotations = {}
    return res


def test_add_event_update_existing(monkeypatch, resource, event):
    query = Query(resource.api, event, resource.namespace)
    monkeypatch.setattr("pykube.query.Query.get_or_none", MagicMock(return_value=event))
    monkeypatch.setattr("pykube.objects.Event.objects", MagicMock(return_value=query))
    e = helper.add_event(resource, "test message", "reason", "Normal", False)
    assert e.obj["count"] == 2
    event.update.assert_called_once()


def test_create_event(monkeypatch, resource, event):
    monkeypatch.setattr("pykube.objects.Event.create", MagicMock(return_value=event))
    e = helper.create_event(resource, "test message", "reason", "Normal", False)
    assert e.obj["count"] == 1
    event.update.assert_not_called()


def test_add_event(monkeypatch, resource, event):
    monkeypatch.setattr("pykube.objects.Event.create", MagicMock(return_value=event))
    e = helper.add_event(resource, "test message", "reason", "Normal", False)
    assert e.obj["count"] == 1
    event.update.assert_not_called()
