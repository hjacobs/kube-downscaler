#!/usr/bin/env python3

import time

import logging

from kube_downscaler import cmd, shutdown
from kube_downscaler.scaler import scale

logger = logging.getLogger('downscaler')


def main():
    parser = cmd.get_parser()
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.DEBUG if args.debug else logging.INFO)

    logger.info('Downscaler started with config: %s', args)

    if args.dry_run:
        logger.info('**DRY-RUN**: no downscaling will be performed!')

    return run_loop(args.once, args.namespace, args.kind, args.default_uptime, args.default_downtime,
                    args.exclude_namespaces, args.exclude_deployments, args.exclude_statefulsets, args.grace_period,
                    args.interval, args.dry_run)


def run_loop(run_once, namespace, kinds, default_uptime, default_downtime, exclude_namespaces, exclude_deployments,
             exclude_statefulsets, grace_period, interval, dry_run):
    handler = shutdown.GracefulShutdown()
    while True:
        try:
            scale(namespace, default_uptime, default_downtime,
                  kinds=frozenset(kinds),
                  exclude_namespaces=frozenset(exclude_namespaces.split(',')),
                  exclude_deployments=frozenset(exclude_deployments.split(',')),
                  exclude_statefulsets=frozenset(exclude_statefulsets.split(',')),
                  dry_run=dry_run, grace_period=grace_period)
        except Exception as e:
            logger.exception('Failed to autoscale : %s', e)
        if run_once or handler.shutdown_now:
            return
        with handler.safe_exit():
            time.sleep(interval)
