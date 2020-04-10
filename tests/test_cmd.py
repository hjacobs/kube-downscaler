import pytest

from kube_downscaler.cmd import check_include_resources
from kube_downscaler.cmd import get_parser


def test_parse_args():
    parser = get_parser()
    config = parser.parse_args(["--dry-run"])

    assert config.dry_run


def test_check_include_resources():
    assert check_include_resources("deployments,cronjobs") == "deployments,cronjobs"


def test_check_include_resources_invalid():
    with pytest.raises(Exception) as excinfo:
        check_include_resources("deployments,foo")
    assert (
        "--include-resources argument should contain a subset of [cronjobs, deployments, horizontalpodautoscalers, stacks, statefulsets]"
        in str(excinfo.value)
    )
