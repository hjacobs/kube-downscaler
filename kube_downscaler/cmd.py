import os

import argparse

VALID_RESOURCES = frozenset(["deployments", "statefulsets", "stacks", "cronjobs"])


def check_include_resources(value):
    resources = frozenset(value.split(","))
    if not resources <= VALID_RESOURCES:
        raise argparse.ArgumentTypeError(
            f"--include-resources argument should contain a subset of [{', '.join(VALID_RESOURCES)}]"
        )
    return value


def get_parser():
    parser = argparse.ArgumentParser()
    upscale_group = parser.add_mutually_exclusive_group(required=False)
    downscalescale_group = parser.add_mutually_exclusive_group(required=False)
    parser.add_argument(
        "--dry-run",
        help="Dry run mode: do not change anything, just print what would be done",
        action="store_true",
    )
    parser.add_argument(
        "--debug", "-d", help="Debug mode: print more information", action="store_true"
    )
    parser.add_argument(
        "--once", help="Run loop only once and exit", action="store_true"
    )
    parser.add_argument(
        "--interval", type=int, help="Loop interval (default: 30s)", default=30
    )
    parser.add_argument("--namespace", help="Namespace")
    parser.add_argument(
        "--include-resources",
        type=check_include_resources,
        default="deployments",
        help="Downscale resources of this kind as comma separated list. [deployments, statefulsets, stacks] (default: deployments)",
    )
    parser.add_argument(
        "--grace-period",
        type=int,
        help="Grace period in seconds for deployments before scaling down (default: 15min)",
        default=900,
    )
    upscale_group.add_argument(
        "--upscale-period",
        help="Default time period to scale up once (default: never)",
        default=os.getenv("UPSCALE_PERIOD", "never"),
    )
    upscale_group.add_argument(
        "--default-uptime",
        help="Default time range to scale up for (default: always)",
        default=os.getenv("DEFAULT_UPTIME", "always"),
    )
    downscalescale_group.add_argument(
        "--downscale-period",
        help="Default time period to scale down once (default: never)",
        default=os.getenv("DOWNSCALE_PERIOD", "never"),
    )
    downscalescale_group.add_argument(
        "--default-downtime",
        help="Default time range to scale down for (default: never)",
        default=os.getenv("DEFAULT_DOWNTIME", "never"),
    )
    parser.add_argument(
        "--exclude-namespaces",
        help="Exclude namespaces from downscaling (default: kube-system)",
        default=os.getenv("EXCLUDE_NAMESPACES", "kube-system"),
    )
    parser.add_argument(
        "--exclude-deployments",
        help="Exclude specific deployments from downscaling (default: kube-downscaler,downscaler)",
        default=os.getenv("EXCLUDE_DEPLOYMENTS", "kube-downscaler,downscaler"),
    )
    parser.add_argument(
        "--exclude-statefulsets",
        help="Exclude specific statefulsets from downscaling",
        default=os.getenv("EXCLUDE_STATEFULSETS", ""),
    )
    parser.add_argument(
        "--exclude-cronjobs",
        help="Exclude specific cronjobs from downscaling",
        default=os.getenv("EXCLUDE_CRONJOBS", ""),
    )
    parser.add_argument(
        "--downtime-replicas",
        type=int,
        help="Default amount of replicas when downscaling (default: 0)",
        default=int(os.getenv("DOWNTIME_REPLICAS", 0)),
    )
    return parser
