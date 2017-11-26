#!/usr/bin/env python3

import argparse
import logging
import os
import re
import time

import pykube

FACTORS = {
    'm': 1 / 1000,
    'K': 1000,
    'M': 1000**2,
    'G': 1000**3,
    'T': 1000**4,
    'P': 1000**5,
    'E': 1000**6,
    'Ki': 1024,
    'Mi': 1024**2,
    'Gi': 1024**3,
    'Ti': 1024**4,
    'Pi': 1024**5,
    'Ei': 1024**6
}

RESOURCE_PATTERN = re.compile('^(\d*)(\D*)$')

RESOURCES = ['cpu', 'memory', 'pods']

logger = logging.getLogger('downscaler')


STATS = {}


def parse_resource(v: str):
    '''Parse Kubernetes resource string'''
    match = RESOURCE_PATTERN.match(v)
    factor = FACTORS.get(match.group(2), 1)
    return int(match.group(1)) * factor


def get_kube_api():
    try:
        config = pykube.KubeConfig.from_service_account()
    except FileNotFoundError:
        # local testing
        config = pykube.KubeConfig.from_file(os.path.expanduser('~/.kube/config'))
    api = pykube.HTTPClient(config)
    return api


def autoscale(exclude_namespaces: set, dry_run: bool=False):
    api = get_kube_api()

    deployments = pykube.Deployment.objects(api, namespace=pykube.all)
    for deploy in deployments:

        if deploy.namespace not in exclude_namespaces:
            print(deploy.name)
            replicas = deploy.obj['spec']['replicas']
            print(replicas)
            if replicas > 0:
                deploy.annotations['downscaler/original-replicas'] = str(replicas)
                deploy.obj['spec']['replicas'] = 0
                deploy.update()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', help='Dry run mode: do not change anything, just print what would be done',
                        action='store_true')
    parser.add_argument('--debug', '-d', help='Debug mode: print more information', action='store_true')
    parser.add_argument('--once', help='Run loop only once and exit', action='store_true')
    parser.add_argument('--interval', type=int, help='Loop interval (default: 60s)', default=60)
    parser.add_argument('--exclude-namespaces', nargs='*', help='', default=['kube-system'])
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG if args.debug else logging.INFO)

    if args.dry_run:
        logger.info('**DRY-RUN**: no downscaling will be performed!')

    while True:
        try:
            autoscale(args.exclude_namespaces, dry_run=args.dry_run)
        except Exception:
            logger.exception('Failed to autoscale')
        if args.once:
            return
        time.sleep(args.interval)
