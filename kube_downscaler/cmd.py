import os

import argparse


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', help='Dry run mode: do not change anything, just print what would be done',
                        action='store_true')
    parser.add_argument('--debug', '-d', help='Debug mode: print more information', action='store_true')
    parser.add_argument('--once', help='Run loop only once and exit', action='store_true')
    parser.add_argument('--interval', type=int, help='Loop interval (default: 30s)', default=30)
    parser.add_argument('--namespace', help='Namespace')
    parser.add_argument('--kind', choices=['deployment', 'statefulset', 'stackset'], nargs='+', default=['deployment'],
                        help='Downscale resources of this kind (default: deployment)')
    parser.add_argument('--grace-period', type=int,
                        help='Grace period in seconds for deployments before scaling down (default: 15min)',
                        default=900)
    parser.add_argument('--default-uptime', help='Default time range to scale up for (default: always)',
                        default=os.getenv('DEFAULT_UPTIME', 'always'))
    parser.add_argument('--default-downtime', help='Default time range to scale down for (default: never)',
                        default=os.getenv('DEFAULT_DOWNTIME', 'never'))
    parser.add_argument('--exclude-namespaces', help='Exclude namespaces from downscaling (default: kube-system)',
                        default=os.getenv('EXCLUDE_NAMESPACES', 'kube-system'))
    parser.add_argument('--exclude-deployments',
                        help='Exclude specific deployments from downscaling (default: kube-downscaler,downscaler)',
                        default=os.getenv('EXCLUDE_DEPLOYMENTS', 'kube-downscaler,downscaler'))
    parser.add_argument('--exclude-statefulsets',
                        help='Exclude specific statefulsets from downscaling',
                        default=os.getenv('EXCLUDE_STATEFULSETS', ''))
    return parser
