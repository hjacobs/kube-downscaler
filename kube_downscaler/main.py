#!/usr/bin/env python3

import argparse
import datetime
import pytz
import logging
import os
import re
import time

import pykube

WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

TIME_SPEC_PATTERN = re.compile('^([a-zA-Z]{3})-([a-zA-Z]{3}) (\d\d):(\d\d)-(\d\d):(\d\d) (?P<tz>[a-zA-Z/]+)$')

logger = logging.getLogger('downscaler')


def matches_time_spec(time: datetime.datetime, spec: str):
    if spec.lower() == 'always':
        return True
    elif spec.lower() == 'never':
        return False
    for spec_ in spec.split(','):
        spec_ = spec_.strip()
        match = TIME_SPEC_PATTERN.match(spec_)
        if not match:
            raise ValueError('Time spec value "{}" does not match format (Mon-Fri 06:30-20:30 Europe/Berlin)'.format(spec))
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


def autoscale(default_uptime: str, default_downtime: str, exclude_namespaces: set, exclude_deployments: set, dry_run: bool=False):
    api = get_kube_api()

    now = datetime.datetime.utcnow()

    deployments = pykube.Deployment.objects(api, namespace=pykube.all)
    for deploy in deployments:

        try:
            # any value different from "false" will ignore the deployment (to be on the safe side)
            exclude = deploy.annotations.get('downscaler/exclude', 'false') != 'false'
            exclude = exclude or deploy.name in exclude_deployments or deploy.namespace in exclude_namespaces
            if exclude:
                logger.debug('Deployment %s/%s was excluded', deploy.namespace, deploy.name)
            else:
                replicas = deploy.obj['spec']['replicas']
                uptime = deploy.annotations.get('downscaler/uptime', default_uptime)
                downtime = deploy.annotations.get('downscaler/downtime', default_downtime)
                is_uptime = matches_time_spec(now, uptime) and not matches_time_spec(now, downtime)

                original_replicas = deploy.annotations.get('downscaler/original-replicas')
                logger.debug('Deployment %s/%s has %s replicas (original: %s, uptime: %s)',
                             deploy.namespace, deploy.name, replicas, original_replicas, uptime)
                update_needed = False
                if is_uptime and replicas == 0 and original_replicas:
                    logger.info('Scaling up deployment %s/%s from %s to %s replicas (uptime: %s, downtime: %s)',
                                deploy.namespace, deploy.name, replicas, original_replicas, uptime, downtime)
                    deploy.obj['spec']['replicas'] = int(original_replicas)
                    update_needed = True
                elif not is_uptime and replicas > 0:
                    logger.info('Scaling down deployment %s/%s from %s to %s replicas (uptime: %s, downtime: %s)',
                                deploy.namespace, deploy.name, original_replicas, replicas, uptime, downtime)
                    deploy.annotations['downscaler/original-replicas'] = str(replicas)
                    deploy.obj['spec']['replicas'] = 0
                    update_needed = True
                if update_needed:
                    if dry_run:
                        logger.info('**DRY-RUN**: would update deployment %s/%s', deploy.namespace, deploy.name)
                    else:
                        deploy.update()
        except Exception:
            logger.exception('Failed to process deployment %s/%s', deploy.namespace, deploy.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', help='Dry run mode: do not change anything, just print what would be done',
                        action='store_true')
    parser.add_argument('--debug', '-d', help='Debug mode: print more information', action='store_true')
    parser.add_argument('--once', help='Run loop only once and exit', action='store_true')
    parser.add_argument('--interval', type=int, help='Loop interval (default: 300s)', default=300)
    parser.add_argument('--default-uptime', help='Default time range to scale up for (default: always)',
                        default=os.getenv('DEFAULT_UPTIME', 'always'))
    parser.add_argument('--default-downtime', help='Default time range to scale down for (default: never)',
                        default=os.getenv('DEFAULT_DOWNTIME', 'never'))
    parser.add_argument('--exclude-namespaces', help='Exclude namespaces from downscaling (default: kube-system)',
                        default=os.getenv('EXCLUDE_NAMESPACES', 'kube-system'))
    parser.add_argument('--exclude-deployments', help='Exclude specific deployments from downscaling (default: kube-downscaler,downscaler)',
                        default=os.getenv('EXCLUDE_DEPLOYMENTS', 'kube-downscaler,downscaler'))
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG if args.debug else logging.INFO)

    if args.dry_run:
        logger.info('**DRY-RUN**: no downscaling will be performed!')

    while True:
        try:
            autoscale(args.default_uptime, args.default_downtime, args.exclude_namespaces.split(','), args.exclude_deployments.split(','), dry_run=args.dry_run)
        except Exception:
            logger.exception('Failed to autoscale')
        if args.once:
            return
        time.sleep(args.interval)
