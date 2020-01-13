import datetime
import logging
import pykube
from typing import FrozenSet

from kube_downscaler import helper
from pykube import Deployment, StatefulSet, CronJob
from kube_downscaler.resources.stack import Stack

logger = logging.getLogger(__name__)
ORIGINAL_REPLICAS_ANNOTATION = "downscaler/original-replicas"
FORCE_UPTIME_ANNOTATION = "downscaler/force-uptime"
UPSCALE_PERIOD_ANNOTATION = "downscaler/upscale-period"
DOWNSCALE_PERIOD_ANNOTATION = "downscaler/downscale-period"
EXCLUDE_ANNOTATION = "downscaler/exclude"
UPTIME_ANNOTATION = "downscaler/uptime"
DOWNTIME_ANNOTATION = "downscaler/downtime"
DOWNTIME_REPLICAS_ANNOTATION = "downscaler/downtime-replicas"


def within_grace_period(deploy, grace_period: int, now: datetime.datetime):
    creation_time = datetime.datetime.strptime(
        deploy.metadata["creationTimestamp"], "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=datetime.timezone.utc)
    delta = now - creation_time
    return delta.total_seconds() <= grace_period


def pods_force_uptime(api, namespace: str):
    """Returns True if there are any running pods which require the deployments to be scaled back up"""
    for pod in pykube.Pod.objects(api).filter(namespace=(namespace or pykube.all)):
        if pod.obj.get("status", {}).get("phase") in ("Succeeded", "Failed"):
            continue
        if pod.annotations.get(FORCE_UPTIME_ANNOTATION, "").lower() == "true":
            logger.info("Forced uptime because of %s/%s", pod.namespace, pod.name)
            return True
    return False


def is_stack_deployment(resource: pykube.objects.NamespacedAPIObject) -> bool:
    if resource.kind == Deployment.kind and resource.version == Deployment.version:
        for owner_ref in resource.metadata.get("ownerReferences", []):
            if (
                owner_ref["apiVersion"] == Stack.version
                and owner_ref["kind"] == Stack.kind
            ):
                return True
    return False


def ignore_resource(resource: pykube.objects.NamespacedAPIObject) -> bool:
    # Ignore deployments managed by stacks, we will downscale the stack instead
    if is_stack_deployment(resource):
        return True

    # any value different from "false" will ignore the resource (to be on the safe side)
    return resource.annotations.get(EXCLUDE_ANNOTATION, "false").lower() != "false"


def autoscale_resource(
    resource: pykube.objects.NamespacedAPIObject,
    upscale_period: str,
    downscale_period: str,
    default_uptime: str,
    default_downtime: str,
    forced_uptime: bool,
    dry_run: bool,
    now: datetime.datetime,
    grace_period: int,
    downtime_replicas: int,
    namespace_excluded=False,
):
    try:
        exclude = namespace_excluded or ignore_resource(resource)
        original_replicas = resource.annotations.get(ORIGINAL_REPLICAS_ANNOTATION)
        downtime_replicas = int(
            resource.annotations.get(DOWNTIME_REPLICAS_ANNOTATION, downtime_replicas)
        )

        if exclude and not original_replicas:
            logger.debug(
                "%s %s/%s was excluded",
                resource.kind,
                resource.namespace,
                resource.name,
            )
        else:
            ignore = False

            upscale_period = resource.annotations.get(
                UPSCALE_PERIOD_ANNOTATION, upscale_period
            )
            downscale_period = resource.annotations.get(
                DOWNSCALE_PERIOD_ANNOTATION, downscale_period
            )
            if forced_uptime or (exclude and original_replicas):
                uptime = "forced"
                downtime = "ignored"
                is_uptime = True
            elif upscale_period != "never" or downscale_period != "never":
                uptime = upscale_period
                downtime = downscale_period
                if helper.matches_time_spec(now, uptime) and helper.matches_time_spec(
                    now, downtime
                ):
                    logger.debug("Upscale and downscale periods overlap, do nothing")
                    ignore = True
                elif helper.matches_time_spec(now, uptime):
                    is_uptime = True
                elif helper.matches_time_spec(now, downtime):
                    is_uptime = False
                else:
                    ignore = True
                logger.debug(
                    "Periods checked: upscale=%s, downscale=%s, ignore=%s, is_uptime=%s",
                    upscale_period,
                    downscale_period,
                    ignore,
                    is_uptime,
                )
            else:
                uptime = resource.annotations.get(UPTIME_ANNOTATION, default_uptime)
                downtime = resource.annotations.get(
                    DOWNTIME_ANNOTATION, default_downtime
                )
                is_uptime = helper.matches_time_spec(
                    now, uptime
                ) and not helper.matches_time_spec(now, downtime)

            if resource.kind == "CronJob":
                suspended = resource.obj["spec"]["suspend"]
                replicas = 0 if suspended else 1
                logger.debug(
                    "%s %s/%s is %s (original: %s, uptime: %s)",
                    resource.kind,
                    resource.namespace,
                    resource.name,
                    "suspended" if suspended else "not suspended",
                    "suspended" if original_replicas == 0 else "not suspended",
                    uptime,
                )
            else:
                replicas = resource.replicas
                logger.debug(
                    "%s %s/%s has %s replicas (original: %s, uptime: %s)",
                    resource.kind,
                    resource.namespace,
                    resource.name,
                    replicas,
                    original_replicas,
                    uptime,
                )
            update_needed = False

            if (
                not ignore
                and is_uptime
                and replicas == downtime_replicas
                and original_replicas
                and int(original_replicas) > 0
            ):

                if resource.kind == "CronJob":
                    resource.obj["spec"]["suspend"] = False
                    resource.obj["spec"]["startingDeadlineSeconds"] = 0
                    logger.info(
                        "Unsuspending %s %s/%s (uptime: %s, downtime: %s)",
                        resource.kind,
                        resource.namespace,
                        resource.name,
                        uptime,
                        downtime,
                    )
                else:
                    resource.replicas = int(original_replicas)
                    logger.info(
                        "Scaling up %s %s/%s from %s to %s replicas (uptime: %s, downtime: %s)",
                        resource.kind,
                        resource.namespace,
                        resource.name,
                        replicas,
                        original_replicas,
                        uptime,
                        downtime,
                    )
                resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = None
                update_needed = True
            elif (
                not ignore
                and not is_uptime
                and replicas > 0
                and replicas > int(downtime_replicas)
            ):
                target_replicas = int(
                    resource.annotations.get(
                        DOWNTIME_REPLICAS_ANNOTATION, downtime_replicas
                    )
                )
                if within_grace_period(resource, grace_period, now):
                    logger.info(
                        "%s %s/%s within grace period (%ds), not scaling down (yet)",
                        resource.kind,
                        resource.namespace,
                        resource.name,
                        grace_period,
                    )
                else:

                    if resource.kind == "CronJob":
                        resource.obj["spec"]["suspend"] = True
                        logger.info(
                            "Suspending %s %s/%s (uptime: %s, downtime: %s)",
                            resource.kind,
                            resource.namespace,
                            resource.name,
                            uptime,
                            downtime,
                        )
                    else:
                        resource.replicas = target_replicas
                        logger.info(
                            "Scaling down %s %s/%s from %s to %s replicas (uptime: %s, downtime: %s)",
                            resource.kind,
                            resource.namespace,
                            resource.name,
                            replicas,
                            target_replicas,
                            uptime,
                            downtime,
                        )
                    resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = str(replicas)
                    update_needed = True
            if update_needed:
                if dry_run:
                    logger.info(
                        "**DRY-RUN**: would update %s %s/%s",
                        resource.kind,
                        resource.namespace,
                        resource.name,
                    )
                else:
                    resource.update()
    except Exception as e:
        logger.exception(
            "Failed to process %s %s/%s : %s",
            resource.kind,
            resource.namespace,
            resource.name,
            str(e),
        )


def autoscale_resources(
    api,
    kind,
    namespace: str,
    exclude_namespaces: FrozenSet[str],
    exclude_names: FrozenSet[str],
    upscale_period: str,
    downscale_period: str,
    default_uptime: str,
    default_downtime: str,
    forced_uptime: bool,
    dry_run: bool,
    now: datetime.datetime,
    grace_period: int,
    downtime_replicas: int,
):
    for resource in kind.objects(api, namespace=(namespace or pykube.all)):
        if resource.namespace in exclude_namespaces or resource.name in exclude_names:
            logger.debug(
                "Resource %s was excluded (either resource itself or namespace %s are excluded)",
                resource.name,
                namespace,
            )
            continue

        # Override defaults with (optional) annotations from Namespace
        namespace_obj = pykube.Namespace.objects(api).get_by_name(resource.namespace)

        excluded = (
            namespace_obj.annotations.get(EXCLUDE_ANNOTATION, "false").lower()
            != "false"
        )

        default_uptime_for_namespace = namespace_obj.annotations.get(
            UPTIME_ANNOTATION, default_uptime
        )
        default_downtime_for_namespace = namespace_obj.annotations.get(
            DOWNTIME_ANNOTATION, default_downtime
        )
        default_downtime_replicas_for_namespace = int(
            namespace_obj.annotations.get(
                DOWNTIME_REPLICAS_ANNOTATION, downtime_replicas
            )
        )
        upscale_period_for_namespace = namespace_obj.annotations.get(
            UPSCALE_PERIOD_ANNOTATION, upscale_period
        )
        downscale_period_for_namespace = namespace_obj.annotations.get(
            DOWNSCALE_PERIOD_ANNOTATION, downscale_period
        )
        forced_uptime_for_namespace = namespace_obj.annotations.get(
            FORCE_UPTIME_ANNOTATION, forced_uptime
        )

        autoscale_resource(
            resource,
            upscale_period_for_namespace,
            downscale_period_for_namespace,
            default_uptime_for_namespace,
            default_downtime_for_namespace,
            forced_uptime_for_namespace,
            dry_run,
            now,
            grace_period,
            default_downtime_replicas_for_namespace,
            namespace_excluded=excluded,
        )


def scale(
    namespace: str,
    upscale_period: str,
    downscale_period: str,
    default_uptime: str,
    default_downtime: str,
    include_resources: FrozenSet[str],
    exclude_namespaces: FrozenSet[str],
    exclude_deployments: FrozenSet[str],
    exclude_statefulsets: FrozenSet[str],
    exclude_cronjobs: FrozenSet[str],
    dry_run: bool,
    grace_period: int,
    downtime_replicas: int,
):
    api = helper.get_kube_api()

    now = datetime.datetime.now(datetime.timezone.utc)
    forced_uptime = pods_force_uptime(api, namespace)

    if "deployments" in include_resources:
        autoscale_resources(
            api,
            Deployment,
            namespace,
            exclude_namespaces,
            exclude_deployments,
            upscale_period,
            downscale_period,
            default_uptime,
            default_downtime,
            forced_uptime,
            dry_run,
            now,
            grace_period,
            downtime_replicas,
        )
    if "statefulsets" in include_resources:
        autoscale_resources(
            api,
            StatefulSet,
            namespace,
            exclude_namespaces,
            exclude_statefulsets,
            upscale_period,
            downscale_period,
            default_uptime,
            default_downtime,
            forced_uptime,
            dry_run,
            now,
            grace_period,
            downtime_replicas,
        )
    if "stacks" in include_resources:
        autoscale_resources(
            api,
            Stack,
            namespace,
            exclude_namespaces,
            exclude_statefulsets,
            upscale_period,
            downscale_period,
            default_uptime,
            default_downtime,
            forced_uptime,
            dry_run,
            now,
            grace_period,
            downtime_replicas,
        )
    if "cronjobs" in include_resources:
        autoscale_resources(
            api,
            CronJob,
            namespace,
            exclude_namespaces,
            exclude_cronjobs,
            upscale_period,
            downscale_period,
            default_uptime,
            default_downtime,
            forced_uptime,
            dry_run,
            now,
            grace_period,
            downtime_replicas,
        )
