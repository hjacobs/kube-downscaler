import json
from unittest.mock import MagicMock

from kube_downscaler.scaler import scale, ORIGINAL_REPLICAS_ANNOTATION


def test_scaler_always_up(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr('kube_downscaler.scaler.helper.get_kube_api', MagicMock(return_value=api))

    def get(url, version, **kwargs):
        if url == 'pods':
            data = {'items': []}
        elif url == 'deployments':
            data = {'items': [{'metadata': {'name': 'deploy-1', 'namespace': 'ns-1'}, 'spec': {'replicas': 1}}]}
        elif url == 'statefulsets':
            data = {'items': []}
        elif url == 'stacksets':
            data = {'items': []}
        elif url == 'namespaces/ns-1':
            data = {'metadata': {}}
        else:
            raise Exception(f'unexpected call: {url}, {version}, {kwargs}')

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    kinds = frozenset(['statefulset', 'deployment', 'stackset'])
    scale(namespace=None, default_uptime='always', default_downtime='never', kinds=kinds,
          exclude_namespaces=[], exclude_deployments=[], exclude_statefulsets=[], dry_run=False, grace_period=300, downtime_replicas=0)

    api.patch.assert_not_called()


def test_scaler_namespace_excluded(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr('kube_downscaler.scaler.helper.get_kube_api', MagicMock(return_value=api))

    def get(url, version, **kwargs):
        if url == 'pods':
            data = {'items': []}
        elif url == 'deployments':
            data = {'items': [
                {'metadata': {'name': 'sysdep-1', 'namespace': 'system-ns', 'creationTimestamp': '2019-03-01T16:38:00Z'}, 'spec': {'replicas': 1}},
                {'metadata': {'name': 'deploy-2', 'namespace': 'default', 'creationTimestamp': '2019-03-01T16:38:00Z'}, 'spec': {'replicas': 2}}
                ]}
        elif url == 'namespaces/default':
            data = {'metadata': {}}
        else:
            raise Exception(f'unexpected call: {url}, {version}, {kwargs}')

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    kinds = frozenset(['deployment'])
    scale(namespace=None, default_uptime='never', default_downtime='always', kinds=kinds,
          exclude_namespaces=['system-ns'], exclude_deployments=[], exclude_statefulsets=[], dry_run=False, grace_period=300, downtime_replicas=0)

    assert api.patch.call_count == 1

    # make sure that deploy-2 was updated (namespace of sysdep-1 was excluded)
    patch_data = {"metadata": {"name": "deploy-2", "namespace": "default", "creationTimestamp": "2019-03-01T16:38:00Z",
                  'annotations': {ORIGINAL_REPLICAS_ANNOTATION: '2'}}, "spec": {"replicas": 0}}
    assert api.patch.call_args[1]['url'] == 'deployments/deploy-2'
    assert json.loads(api.patch.call_args[1]['data']) == patch_data


def test_scaler_namespace_excluded_via_annotation(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr('kube_downscaler.scaler.helper.get_kube_api', MagicMock(return_value=api))

    def get(url, version, **kwargs):
        if url == 'pods':
            data = {'items': []}
        elif url == 'deployments':
            data = {'items': [
                {'metadata': {'name': 'deploy-1', 'namespace': 'ns-1', 'creationTimestamp': '2019-03-01T16:38:00Z'}, 'spec': {'replicas': 1}},
                {'metadata': {'name': 'deploy-2', 'namespace': 'ns-2', 'creationTimestamp': '2019-03-01T16:38:00Z'}, 'spec': {'replicas': 2}}
                ]}
        elif url == 'namespaces/ns-1':
            data = {'metadata': {'annotations': {'downscaler/exclude': 'true'}}}
        elif url == 'namespaces/ns-2':
            data = {'metadata': {}}
        else:
            raise Exception(f'unexpected call: {url}, {version}, {kwargs}')

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    kinds = frozenset(['deployment'])
    scale(namespace=None, default_uptime='never', default_downtime='always', kinds=kinds,
          exclude_namespaces=[], exclude_deployments=[], exclude_statefulsets=[], dry_run=False, grace_period=300, downtime_replicas=0)

    assert api.patch.call_count == 1

    # make sure that deploy-2 was updated (deploy-1 was excluded via annotation on ns-1)
    patch_data = {"metadata": {"name": "deploy-2", "namespace": "ns-2", "creationTimestamp": "2019-03-01T16:38:00Z",
                  'annotations': {ORIGINAL_REPLICAS_ANNOTATION: '2'}}, "spec": {"replicas": 0}}
    assert api.patch.call_args[1]['url'] == 'deployments/deploy-2'
    assert json.loads(api.patch.call_args[1]['data']) == patch_data


def test_scaler_down_to(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr('kube_downscaler.scaler.helper.get_kube_api', MagicMock(return_value=api))
    SCALE_TO = 1

    def get(url, version, **kwargs):
        if url == 'pods':
            data = {'items': []}
        elif url == 'deployments':
            data = {'items': [
                {
                    'metadata': {
                        'name': 'deploy-1', 'namespace': 'default', 'creationTimestamp': '2019-03-01T16:38:00Z',
                        'annotations': {'downscaler/downtime-replicas': SCALE_TO},
                    }, 'spec': {'replicas': 5}
                },
                ]}
        elif url == 'namespaces/default':
            data = {'metadata': {}}
        else:
            raise Exception(f'unexpected call: {url}, {version}, {kwargs}')

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    kinds = frozenset(['deployment'])
    scale(namespace=None, default_uptime='never', default_downtime='always', kinds=kinds,
          exclude_namespaces=[], exclude_deployments=[], exclude_statefulsets=[], dry_run=False, grace_period=300, downtime_replicas=0)

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]['url'] == 'deployments/deploy-1'
    assert json.loads(api.patch.call_args[1]['data'])["spec"]["replicas"] == SCALE_TO
