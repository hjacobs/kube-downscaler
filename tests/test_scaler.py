import json
from unittest.mock import MagicMock

from kube_downscaler.scaler import (
    scale,
    ORIGINAL_REPLICAS_ANNOTATION,
    EXCLUDE_ANNOTATION,
    DOWNTIME_REPLICAS_ANNOTATION,
)


def test_scaler_always_up(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {"name": "deploy-1", "namespace": "ns-1"},
                        "spec": {"replicas": 1},
                    }
                ]
            }
        elif url == "statefulsets":
            data = {"items": []}
        elif url == "stacks":
            data = {"items": []}
        elif url == "cronjobs":
            data = {"items": []}
        elif url == "namespaces/ns-1":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["statefulsets", "deployments", "stacks", "cronjobs"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="always",
        default_downtime="never",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    api.patch.assert_not_called()


def test_scaler_namespace_excluded(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "sysdep-1",
                            "namespace": "system-ns",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"replicas": 1},
                    },
                    {
                        "metadata": {
                            "name": "deploy-2",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"replicas": 2},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=["system-ns"],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1

    # make sure that deploy-2 was updated (namespace of sysdep-1 was excluded)
    patch_data = {
        "metadata": {
            "name": "deploy-2",
            "namespace": "default",
            "creationTimestamp": "2019-03-01T16:38:00Z",
            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: "2"},
        },
        "spec": {"replicas": 0},
    }
    assert api.patch.call_args[1]["url"] == "deployments/deploy-2"
    assert json.loads(api.patch.call_args[1]["data"]) == patch_data


def test_scaler_namespace_excluded_via_annotation(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "ns-1",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"replicas": 1},
                    },
                    {
                        "metadata": {
                            "name": "deploy-2",
                            "namespace": "ns-2",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"replicas": 2},
                    },
                ]
            }
        elif url == "namespaces/ns-1":
            data = {"metadata": {"annotations": {"downscaler/exclude": "true"}}}
        elif url == "namespaces/ns-2":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1

    # make sure that deploy-2 was updated (deploy-1 was excluded via annotation on ns-1)
    patch_data = {
        "metadata": {
            "name": "deploy-2",
            "namespace": "ns-2",
            "creationTimestamp": "2019-03-01T16:38:00Z",
            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: "2"},
        },
        "spec": {"replicas": 0},
    }
    assert api.patch.call_args[1]["url"] == "deployments/deploy-2"
    assert json.loads(api.patch.call_args[1]["data"]) == patch_data


def test_scaler_down_to(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )
    SCALE_TO = 1

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                            "annotations": {DOWNTIME_REPLICAS_ANNOTATION: SCALE_TO},
                        },
                        "spec": {"replicas": 5},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "deployments/deploy-1"
    assert json.loads(api.patch.call_args[1]["data"])["spec"]["replicas"] == SCALE_TO


def test_scaler_down_to_upscale(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )
    SCALE_TO = 1
    ORIGINAL = 3

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                            "annotations": {
                                DOWNTIME_REPLICAS_ANNOTATION: SCALE_TO,
                                ORIGINAL_REPLICAS_ANNOTATION: ORIGINAL,
                            },
                        },
                        "spec": {"replicas": SCALE_TO},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="always",
        default_downtime="never",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "deployments/deploy-1"
    assert json.loads(api.patch.call_args[1]["data"])["spec"]["replicas"] == ORIGINAL
    assert not json.loads(api.patch.call_args[1]["data"])["metadata"]["annotations"][
        ORIGINAL_REPLICAS_ANNOTATION
    ]


def test_scaler_upscale_on_exclude(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )
    ORIGINAL_REPLICAS = 2

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "default",
                            "annotations": {
                                EXCLUDE_ANNOTATION: "true",
                                ORIGINAL_REPLICAS_ANNOTATION: ORIGINAL_REPLICAS,
                            },
                        },
                        "spec": {"replicas": 0},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "deployments/deploy-1"
    assert (
        json.loads(api.patch.call_args[1]["data"])["spec"]["replicas"]
        == ORIGINAL_REPLICAS
    )
    assert not json.loads(api.patch.call_args[1]["data"])["metadata"]["annotations"][
        ORIGINAL_REPLICAS_ANNOTATION
    ]


def test_scaler_upscale_on_exclude_namespace(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )
    ORIGINAL_REPLICAS = 2

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "default",
                            "annotations": {
                                ORIGINAL_REPLICAS_ANNOTATION: ORIGINAL_REPLICAS,
                            },
                        },
                        "spec": {"replicas": 0},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {"metadata": {"annotations": {EXCLUDE_ANNOTATION: "true"}}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "deployments/deploy-1"
    assert (
        json.loads(api.patch.call_args[1]["data"])["spec"]["replicas"]
        == ORIGINAL_REPLICAS
    )
    assert not json.loads(api.patch.call_args[1]["data"])["metadata"]["annotations"][
        ORIGINAL_REPLICAS_ANNOTATION
    ]


def test_scaler_always_upscale(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {"name": "deploy-1", "namespace": "ns-1"},
                        "spec": {"replicas": 1},
                    }
                ]
            }
        elif url == "statefulsets":
            data = {"items": []}
        elif url == "stacks":
            data = {"items": []}
        elif url == "namespaces/ns-1":
            data = {"metadata": {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["statefulsets", "deployments", "stacks"])
    scale(
        namespace=None,
        upscale_period="always",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    api.patch.assert_not_called()


def test_scaler_namespace_annotation_replicas(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )
    SCALE_TO = 3

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "deployments":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "deploy-1",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"replicas": 5},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {
                "metadata": {"annotations": {"downscaler/downtime-replicas": SCALE_TO}}
            }
            # data = {'metadata': {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["deployments"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "deployments/deploy-1"
    assert json.loads(api.patch.call_args[1]["data"])["spec"]["replicas"] == SCALE_TO


def test_scaler_cronjob_suspend(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "cronjobs":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "cronjob-1",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                        },
                        "spec": {"suspend": False},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {
                "metadata": {"annotations": {"downscaler/uptime": "never"}}
            }
            # data = {'metadata': {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["cronjobs"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "cronjobs/cronjob-1"

    patch_data = {
        "metadata": {
            "name": "cronjob-1",
            "namespace": "default",
            "creationTimestamp": "2019-03-01T16:38:00Z",
            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: "1"},
        },
        "spec": {"suspend": True},
    }
    assert json.loads(api.patch.call_args[1]["data"]) == patch_data


def test_scaler_cronjob_unsuspend(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr(
        "kube_downscaler.scaler.helper.get_kube_api", MagicMock(return_value=api)
    )

    def get(url, version, **kwargs):
        if url == "pods":
            data = {"items": []}
        elif url == "cronjobs":
            data = {
                "items": [
                    {
                        "metadata": {
                            "name": "cronjob-1",
                            "namespace": "default",
                            "creationTimestamp": "2019-03-01T16:38:00Z",
                            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: "1"},
                        },
                        "spec": {"suspend": True},
                    },
                ]
            }
        elif url == "namespaces/default":
            data = {
                "metadata": {"annotations": {
                    "downscaler/uptime": "always",
                    "downscaler/downtime": "never"
                }}
            }
            # data = {'metadata': {}}
        else:
            raise Exception(f"unexpected call: {url}, {version}, {kwargs}")

        response = MagicMock()
        response.json.return_value = data
        return response

    api.get = get

    include_resources = frozenset(["cronjobs"])
    scale(
        namespace=None,
        upscale_period="never",
        downscale_period="never",
        default_uptime="never",
        default_downtime="always",
        include_resources=include_resources,
        exclude_namespaces=[],
        exclude_deployments=[],
        exclude_statefulsets=[],
        exclude_cronjobs=[],
        dry_run=False,
        grace_period=300,
        downtime_replicas=0,
    )

    assert api.patch.call_count == 1
    assert api.patch.call_args[1]["url"] == "cronjobs/cronjob-1"

    patch_data = {
        "metadata": {
            "name": "cronjob-1",
            "namespace": "default",
            "creationTimestamp": "2019-03-01T16:38:00Z",
            "annotations": {ORIGINAL_REPLICAS_ANNOTATION: None},
        },
        "spec": {
            "suspend": False,
            "startingDeadlineSeconds": 0,
        },
    }
    assert json.loads(api.patch.call_args[1]["data"]) == patch_data
