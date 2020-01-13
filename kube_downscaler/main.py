#!/usr/bin/env python3

import time

import logging

from kube_downscaler import __version__, cmd, shutdown
from kube_downscaler.scaler import scale

logger = logging.getLogger("downscaler")


def main(args=None):
    parser = cmd.get_parser()
    args = parser.parse_args(args)

    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
    )

    config_str = ", ".join(f"{k}={v}" for k, v in sorted(vars(args).items()))
    logger.info(f"Downscaler v{__version__} started with {config_str}")

    if args.dry_run:
        logger.info("**DRY-RUN**: no downscaling will be performed!")

    return run_loop(
        args.once,
        args.namespace,
        args.include_resources,
        args.upscale_period,
        args.downscale_period,
        args.default_uptime,
        args.default_downtime,
        args.exclude_namespaces,
        args.exclude_deployments,
        args.exclude_statefulsets,
        args.exclude_cronjobs,
        args.grace_period,
        args.interval,
        args.dry_run,
        args.downtime_replicas,
    )


def run_loop(
    run_once,
    namespace,
    include_resources,
    upscale_period,
    downscale_period,
    default_uptime,
    default_downtime,
    exclude_namespaces,
    exclude_deployments,
    exclude_statefulsets,
    exclude_cronjobs,
    grace_period,
    interval,
    dry_run,
    downtime_replicas,
):
    handler = shutdown.GracefulShutdown()
    while True:
        try:
            scale(
                namespace,
                upscale_period,
                downscale_period,
                default_uptime,
                default_downtime,
                include_resources=frozenset(include_resources.split(",")),
                exclude_namespaces=frozenset(exclude_namespaces.split(",")),
                exclude_deployments=frozenset(exclude_deployments.split(",")),
                exclude_statefulsets=frozenset(exclude_statefulsets.split(",")),
                exclude_cronjobs=frozenset(exclude_cronjobs.split(",")),
                dry_run=dry_run,
                grace_period=grace_period,
                downtime_replicas=downtime_replicas,
            )
        except Exception as e:
            logger.exception("Failed to autoscale : %s", e)
        if run_once or handler.shutdown_now:
            return
        with handler.safe_exit():
            time.sleep(interval)
