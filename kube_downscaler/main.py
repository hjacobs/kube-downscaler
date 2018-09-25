#!/usr/bin/env python3

import argparse
import contextlib
import datetime
import logging
import os
import re
import signal
import sys
import time
from typing import FrozenSet

import pykube
import pytz
from pykube.mixins import ReplicatedMixin, ScalableMixin
from pykube.objects import NamespacedAPIObject

WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

TIME_SPEC_PATTERN = re.compile(r'^([a-zA-Z]{3})-([a-zA-Z]{3}) (\d\d):(\d\d)-(\d\d):(\d\d) (?P<tz>[a-zA-Z/_]+)$')

ORIGINAL_REPLICAS_ANNOTATION = 'downscaler/original-replicas'

logger = logging.getLogger('downscaler')


class Deployment(NamespacedAPIObject, ReplicatedMixin, ScalableMixin):
    '''
    Use latest workloads API version (apps/v1), pykube is stuck with old version
    '''

    version = "apps/v1"
    endpoint = "deployments"
    kind = "Deployment"


class Statefulset(NamespacedAPIObject, ReplicatedMixin, ScalableMixin):
    '''
    Use latest workloads API version (apps/v1), pykube is stuck with old version
    '''

    version = "apps/v1"
    endpoint = "statefulsets"
    kind = "StatefulSet"


def matches_time_spec(time: datetime.datetime, spec: str):
    if spec.lower() == 'always':
        return True
    elif spec.lower() == 'never':
        return False
    for spec_ in spec.split(','):
        spec_ = spec_.strip()
        match = TIME_SPEC_PATTERN.match(spec_)
        if not match:
            raise ValueError(
                f'Time spec value "{spec}" does not match format (Mon-Fri 06:30-20:30 Europe/Berlin)')
        day_from = WEEKDAYS.index(match.group(1).upper())
        day_to = WEEKDAYS.index(match.group(2).upper())
        day_matches = day_from <= time.weekday() <= day_to
        tz = pytz.timezone(match.group('tz'))
        local_time = tz.fromutc(time.replace(tzinfo=tz))
        local_time_minutes = local_time.hour * 60 + local_time.minute
        minute_from = int(match.group(3)) * 60 + int(match.group(4))
        minute_to = int(match.group(5)) * 60 + int(match.group(6))
        time_matches = minute_from <= local_time_minutes < minute_to
        if day_matches and time_matches:
            return True
    return False


def get_kube_api():
    try:
        config = pykube.KubeConfig.from_service_account()
    except FileNotFoundError:
        # local testing
        config = pykube.KubeConfig.from_file(os.path.expanduser('~/.kube/config'))
    api = pykube.HTTPClient(config)
    return api


def within_grace_period(deploy, grace_period: int):
    creation_time = datetime.datetime.strptime(deploy.metadata['creationTimestamp'], '%Y-%m-%dT%H:%M:%SZ')
    now = datetime.datetime.utcnow()
    delta = now - creation_time
    return delta.total_seconds() <= grace_period


def pods_force_uptime(api, namespace: str):
    """Returns True if there are any running pods which require the deployments to be scaled back up"""
    for pod in pykube.Pod.objects(api).filter(namespace=(namespace or pykube.all)):
        if pod.obj.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
            continue
        if pod.annotations.get('downscaler/force-uptime') == 'true':
            logger.info('Forced uptime because of %s/%s', pod.namespace, pod.name)
            return True
    return False


def autoscale_resource(resource: pykube.objects.NamespacedAPIObject,
                       default_uptime: str, default_downtime: str, forced_uptime: bool, dry_run: bool,
                       now: datetime.datetime, grace_period: int):
    try:
        # any value different from "false" will ignore the resource (to be on the safe side)
        exclude = resource.annotations.get('downscaler/exclude', 'false') != 'false'
        if exclude:
            logger.debug('%s %s/%s was excluded', resource.kind, resource.namespace, resource.name)
        else:
            replicas = resource.obj['spec']['replicas']

            if forced_uptime:
                uptime = "forced"
                downtime = "ignored"
                is_uptime = True
            else:
                uptime = resource.annotations.get('downscaler/uptime', default_uptime)
                downtime = resource.annotations.get('downscaler/downtime', default_downtime)
                is_uptime = matches_time_spec(now, uptime) and not matches_time_spec(now, downtime)

            original_replicas = resource.annotations.get(ORIGINAL_REPLICAS_ANNOTATION)
            logger.debug('%s %s/%s has %s replicas (original: %s, uptime: %s)',
                         resource.kind, resource.namespace, resource.name, replicas, original_replicas, uptime)
            update_needed = False
            if is_uptime and replicas == 0 and original_replicas and int(original_replicas) > 0:
                logger.info('Scaling up %s %s/%s from %s to %s replicas (uptime: %s, downtime: %s)',
                            resource.kind, resource.namespace, resource.name, replicas, original_replicas,
                            uptime, downtime)
                resource.obj['spec']['replicas'] = int(original_replicas)
                resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = None
                update_needed = True
            elif not is_uptime and replicas > 0:
                if within_grace_period(resource, grace_period):
                    logger.info('%s %s/%s within grace period (%ds), not scaling down (yet)',
                                resource.kind, resource.namespace, resource.name, grace_period)
                else:
                    target_replicas = 0
                    logger.info('Scaling down %s %s/%s from %s to %s replicas (uptime: %s, downtime: %s)',
                                resource.kind, resource.namespace, resource.name, replicas, target_replicas,
                                uptime, downtime)
                    resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = str(replicas)
                    resource.obj['spec']['replicas'] = target_replicas
                    update_needed = True
            if update_needed:
                if dry_run:
                    logger.info('**DRY-RUN**: would update %s %s/%s', resource.kind, resource.namespace, resource.name)
                else:
                    resource.update()
    except Exception:
        logger.exception('Failed to process %s %s/%s', resource.kind, resource.namespace, resource.name)


def autoscale_resources(api, kind, namespace: str,
                        exclude_namespaces: FrozenSet[str], exclude_names: FrozenSet[str],
                        default_uptime: str, default_downtime: str, forced_uptime: bool, dry_run: bool,
                        now: datetime.datetime, grace_period: int):
    for resource in kind.objects(api, namespace=(namespace or pykube.all)):
        if resource.namespace in exclude_namespaces or resource.name in exclude_names:
            continue
        autoscale_resource(resource, default_uptime, default_downtime, forced_uptime, dry_run, now, grace_period)


def autoscale(namespace: str, default_uptime: str, default_downtime: str, kinds: FrozenSet[str],
              exclude_namespaces: FrozenSet[str],
              exclude_deployments: FrozenSet[str],
              exclude_statefulsets: FrozenSet[str],
              dry_run: bool, grace_period: int):
    api = get_kube_api()

    now = datetime.datetime.utcnow()
    forced_uptime = pods_force_uptime(api, namespace)

    if 'deployment' in kinds:
        autoscale_resources(api, Deployment, namespace, exclude_namespaces, exclude_deployments,
                            default_uptime, default_downtime, forced_uptime, dry_run, now, grace_period)
    if 'statefulset' in kinds:
        autoscale_resources(api, Statefulset, namespace, exclude_namespaces, exclude_statefulsets,
                            default_uptime, default_downtime, forced_uptime, dry_run, now, grace_period)


class GracefulShutdown:
    shutdown_now = False
    safe_to_exit = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.shutdown_now = True
        if self.safe_to_exit:
            sys.exit(0)

    @contextlib.contextmanager
    def safe_exit(self):
        self.safe_to_exit = True
        yield
        self.safe_to_exit = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', help='Dry run mode: do not change anything, just print what would be done',
                        action='store_true')
    parser.add_argument('--debug', '-d', help='Debug mode: print more information', action='store_true')
    parser.add_argument('--once', help='Run loop only once and exit', action='store_true')
    parser.add_argument('--interval', type=int, help='Loop interval (default: 30s)', default=30)
    parser.add_argument('--namespace', help='Namespace')
    parser.add_argument('--kind', choices=['deployment', 'statefulset'], nargs='+', default=['deployment'],
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

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.DEBUG if args.debug else logging.INFO)

    handler = GracefulShutdown()

    logger.info('Downscaler started with config: %s', args)

    if args.dry_run:
        logger.info('**DRY-RUN**: no downscaling will be performed!')

    while True:
        try:
            autoscale(args.namespace, args.default_uptime, args.default_downtime,
                      kinds=frozenset(args.kind),
                      exclude_namespaces=frozenset(args.exclude_namespaces.split(',')),
                      exclude_deployments=frozenset(args.exclude_deployments.split(',')),
                      exclude_statefulsets=frozenset(args.exclude_statefulsets.split(',')),
                      dry_run=args.dry_run, grace_period=args.grace_period)
        except Exception:
            logger.exception('Failed to autoscale')
        if args.once or handler.shutdown_now:
            return
        with handler.safe_exit():
            time.sleep(args.interval)
