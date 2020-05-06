import os.path
import re
from unittest.mock import MagicMock

import pytest

from kube_downscaler.main import main


@pytest.fixture
def kubeconfig(tmpdir):
    kubeconfig = tmpdir.join("kubeconfig")
    kubeconfig.write(
        """
apiVersion: v1
clusters:
- cluster: {server: 'https://localhost:9443'}
  name: test
contexts:
- context: {cluster: test}
  name: test
current-context: test
kind: Config
    """
    )
    return kubeconfig


def test_main(kubeconfig, monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda x: str(kubeconfig))

    mock_scale = MagicMock()
    monkeypatch.setattr("kube_downscaler.main.scale", mock_scale)

    main(["--dry-run", "--once"])

    mock_scale.assert_called_once()


def test_main_continue_on_failure(kubeconfig, monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda x: str(kubeconfig))

    mock_shutdown = MagicMock()
    mock_handler = MagicMock()
    mock_handler.shutdown_now = False
    mock_shutdown.GracefulShutdown.return_value = mock_handler

    calls = []

    def mock_scale(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise Exception("scale fails on first run")
        elif len(calls) == 2:
            mock_handler.shutdown_now = True

    monkeypatch.setattr("kube_downscaler.main.scale", mock_scale)
    monkeypatch.setattr("kube_downscaler.main.shutdown", mock_shutdown)

    main(["--dry-run", "--interval=0"])

    assert len(calls) == 2


def test_main_exclude_namespaces(kubeconfig, monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda x: str(kubeconfig))

    mock_scale = MagicMock()
    monkeypatch.setattr("kube_downscaler.main.scale", mock_scale)

    main(["--dry-run", "--once", "--exclude-namespaces=foo,.*-infra-.*"])

    mock_scale.assert_called_once()
    assert mock_scale.call_args.kwargs["exclude_namespaces"] == frozenset(
        [re.compile("foo"), re.compile(".*-infra-.*")]
    )
