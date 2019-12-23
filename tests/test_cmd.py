from kube_downscaler.cmd import get_parser


def test_parse_args():
    parser = get_parser()
    config = parser.parse_args(["--dry-run"])

    assert config.dry_run
