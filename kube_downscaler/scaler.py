import collections
import datetime
import logging
from typing import FrozenSet
from typing import Optional

import pykube
from pykube import CronJob
from pykube import Deployment
from pykube import HorizontalPodAutoscaler
from pykube import Namespace
from pykube import StatefulSet
from pykube.objects import NamespacedAPIObject

from kube_downscaler import helper
from kube_downscaler.helper import matches_time_spec
from kube_downscaler.resources.stack import Stack

ORIGINAL_REPLICAS_ANNOTATION = "downscaler/original-replicas"
FORCE_UPTIME_ANNOTATION = "downscaler/force-uptime"
UPSCALE_PERIOD_ANNOTATION = "downscaler/upscale-period"
DOWNSCALE_PERIOD_ANNOTATION = "downscaler/downscale-period"
EXCLUDE_ANNOTATION = "downscaler/exclude"
EXCLUDE_UNTIL_ANNOTATION = "downscaler/exclude-until"
UPTIME_ANNOTATION = "downscaler/uptime"
DOWNTIME_ANNOTATION = "downscaler/downtime"
DOWNTIME_REPLICAS_ANNOTATION = "downscaler/downtime-replicas"

RESOURCE_CLASSES = [Deployment, StatefulSet, Stack, CronJob, HorizontalPodAutoscaler]

TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]

logger = logging.getLogger(__name__)


def parse_time(timestamp: str) -> datetime.datetime:
    for fmt in TIMESTAMP_FORMATS:
        try:
            dt = datetime.datetime.strptime(timestamp, fmt)
        except ValueError:
            pass
        else:
            return dt.replace(tzinfo=datetime.timezone.utc)
    raise ValueError(
        f"time data '{timestamp}' does not match any format ({', '.join(TIMESTAMP_FORMATS)})"
    )


def within_grace_period(
    resource,
    grace_period: int,
    now: datetime.datetime,
    deployment_time_annotation: Optional[str] = None,
):
    update_time = parse_time(resource.metadata["creationTimestamp"])

    if deployment_time_annotation:
        annotations = resource.metadata.get("annotations", {})
        deployment_time = annotations.get(deployment_time_annotation)
        if deployment_time:
            try:
                update_time = max(update_time, parse_time(deployment_time))
            except ValueError as e:
                logger.warning(
                    f"Invalid {deployment_time_annotation} in {resource.namespace}/{resource.name}: {e}"
                )
    delta = now - update_time
    return delta.total_seconds() <= grace_period


def pods_force_uptime(api, namespace: str):
    """Return True if there are any running pods which require the deployments to be scaled back up."""
    for pod in pykube.Pod.objects(api).filter(namespace=(namespace or pykube.all)):
        if pod.obj.get("status", {}).get("phase") in ("Succeeded", "Failed"):
            continue
        if pod.annotations.get(FORCE_UPTIME_ANNOTATION, "").lower() == "true":
            logger.info(f"Forced uptime because of {pod.namespace}/{pod.name}")
            return True
    return False


def is_stack_deployment(resource: NamespacedAPIObject) -> bool:
    if resource.kind == Deployment.kind and resource.version == Deployment.version:
        for owner_ref in resource.metadata.get("ownerReferences", []):
            if (
                owner_ref["apiVersion"] == Stack.version
                and owner_ref["kind"] == Stack.kind
            ):
                return True
    return False


def ignore_resource(resource: NamespacedAPIObject, now: datetime.datetime) -> bool:
    # Ignore deployments managed by stacks, we will downscale the stack instead
    if is_stack_deployment(resource):
        return True

    # any value different from "false" will ignore the resource (to be on the safe side)
    if resource.annotations.get(EXCLUDE_ANNOTATION, "false").lower() != "false":
        return True

    exclude_until = resource.annotations.get(EXCLUDE_UNTIL_ANNOTATION)
    if exclude_until:
        try:
            until_ts = parse_time(exclude_until)
        except ValueError as e:
            logger.warning(
                f"Invalid annotation value for '{EXCLUDE_UNTIL_ANNOTATION}' on {resource.namespace}/{resource.name}: {e}"
            )
            # we will ignore the invalid timestamp and treat the resource as not excluded
            return False
        if now < until_ts:
            return True

    return False


def get_replicas(
    resource: NamespacedAPIObject, original_replicas: Optional[int], uptime: str
) -> int:
    if resource.kind == "CronJob":
        suspended = resource.obj["spec"]["suspend"]
        replicas = 0 if suspended else 1
        state = "suspended" if suspended else "not suspended"
        original_state = "suspended" if original_replicas == 0 else "not suspended"
        logger.debug(
            f"{resource.kind} {resource.namespace}/{resource.name} is {state} (original: {original_state}, uptime: {uptime})"
        )
    elif resource.kind == "HorizontalPodAutoscaler":
        replicas = resource.obj["spec"]["minReplicas"]
        logger.debug(
            f"{resource.kind} {resource.namespace}/{resource.name} has {replicas} minReplicas (original: {original_replicas}, uptime: {uptime})"
        )
    else:
        replicas = resource.replicas
        logger.debug(
            f"{resource.kind} {resource.namespace}/{resource.name} has {replicas} replicas (original: {original_replicas}, uptime: {uptime})"
        )
    return replicas


def scale_up(
    resource: NamespacedAPIObject,
    replicas: int,
    original_replicas: int,
    uptime,
    downtime,
):
    if resource.kind == "CronJob":
        resource.obj["spec"]["suspend"] = False
        logger.info(
            f"Unsuspending {resource.kind} {resource.namespace}/{resource.name} (uptime: {uptime}, downtime: {downtime})"
        )
    elif resource.kind == "HorizontalPodAutoscaler":
        resource.obj["spec"]["minReplicas"] = original_replicas
        logger.info(
            f"Scaling up {resource.kind} {resource.namespace}/{resource.name} from {replicas} to {original_replicas} minReplicas (uptime: {uptime}, downtime: {downtime})"
        )
    else:
        resource.replicas = original_replicas
        logger.info(
            f"Scaling up {resource.kind} {resource.namespace}/{resource.name} from {replicas} to {original_replicas} replicas (uptime: {uptime}, downtime: {downtime})"
        )
    resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = None


def scale_down(
    resource: NamespacedAPIObject, replicas: int, target_replicas: int, uptime, downtime
):

    if resource.kind == "CronJob":
        resource.obj["spec"]["suspend"] = True
        logger.info(
            f"Suspending {resource.kind} {resource.namespace}/{resource.name} (uptime: {uptime}, downtime: {downtime})"
        )
    elif resource.kind == "HorizontalPodAutoscaler":
        resource.obj["spec"]["minReplicas"] = target_replicas
        logger.info(
            f"Scaling down {resource.kind} {resource.namespace}/{resource.name} from {replicas} to {target_replicas} minReplicas (uptime: {uptime}, downtime: {downtime})"
        )
    else:
        resource.replicas = target_replicas
        logger.info(
            f"Scaling down {resource.kind} {resource.namespace}/{resource.name} from {replicas} to {target_replicas} replicas (uptime: {uptime}, downtime: {downtime})"
        )
    resource.annotations[ORIGINAL_REPLICAS_ANNOTATION] = str(replicas)


def get_annotation_value_as_int(
    resource: NamespacedAPIObject, annotation_name: str
) -> Optional[int]:
    value = resource.annotations.get(annotation_name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(
            f"Could not read annotation '{annotation_name}' as integer: {e}"
        )


def autoscale_resource(
    resource: NamespacedAPIObject,
    upscale_period: str,
    downscale_period: str,
    default_uptime: str,
    default_downtime: str,
    forced_uptime: bool,
    dry_run: bool,
    now: datetime.datetime,
    grace_period: int = 0,
    downtime_replicas: int = 0,
    namespace_excluded=False,
    deployment_time_annotation: Optional[str] = None,
):
    try:
        exclude = namespace_excluded or ignore_resource(resource, now)
        original_replicas = get_annotation_value_as_int(
            resource, ORIGINAL_REPLICAS_ANNOTATION
        )
        downtime_replicas_from_annotation = get_annotation_value_as_int(
            resource, DOWNTIME_REPLICAS_ANNOTATION
        )
        if downtime_replicas_from_annotation is not None:
            downtime_replicas = downtime_replicas_from_annotation

        if exclude and not original_replicas:
            logger.debug(
                f"{resource.kind} {resource.namespace}/{resource.name} was excluded"
            )
        else:
            ignore = False
            is_uptime = True

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
                if matches_time_spec(now, uptime) and matches_time_spec(now, downtime):
                    logger.debug("Upscale and downscale periods overlap, do nothing")
                    ignore = True
                elif matches_time_spec(now, uptime):
                    is_uptime = True
                elif matches_time_spec(now, downtime):
                    is_uptime = False
                else:
                    ignore = True
                logger.debug(
                    f"Periods checked: upscale={upscale_period}, downscale={downscale_period}, ignore={ignore}, is_uptime={is_uptime}"
                )
            else:
                uptime = resource.annotations.get(UPTIME_ANNOTATION, default_uptime)
                downtime = resource.annotations.get(
                    DOWNTIME_ANNOTATION, default_downtime
                )
                is_uptime = matches_time_spec(now, uptime) and not matches_time_spec(
                    now, downtime
                )

            replicas = get_replicas(resource, original_replicas, uptime)
            update_needed = False

            if (
                not ignore
                and is_uptime
                and replicas == downtime_replicas
                and original_replicas
                and original_replicas > 0
            ):

                scale_up(resource, replicas, original_replicas, uptime, downtime)
                update_needed = True
            elif (
                not ignore
                and not is_uptime
                and replicas > 0
                and replicas > downtime_replicas
            ):
                if within_grace_period(
                    resource, grace_period, now, deployment_time_annotation
                ):
                    logger.info(
                        f"{resource.kind} {resource.namespace}/{resource.name} within grace period ({grace_period}s), not scaling down (yet)"
                    )
                else:
                    scale_down(resource, replicas, downtime_replicas, uptime, downtime)
                    update_needed = True
            if update_needed:
                if dry_run:
                    logger.info(
                        f"**DRY-RUN**: would update {resource.kind} {resource.namespace}/{resource.name}"
                    )
                else:
                    resource.update()
    except Exception as e:
        logger.exception(
            f"Failed to process {resource.kind} {resource.namespace}/{resource.name}: {e}"
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
    deployment_time_annotation: Optional[str] = None,
):
    resources_by_namespace = collections.defaultdict(list)
    for resource in kind.objects(api, namespace=(namespace or pykube.all)):
        if resource.name in exclude_names:
            logger.debug(
                f"{resource.kind} {resource.namespace}/{resource.name} was excluded (name matches exclusion list)"
            )
            continue
        resources_by_namespace[resource.namespace].append(resource)

    for current_namespace, resources in sorted(resources_by_namespace.items()):

        if current_namespace in exclude_namespaces:
            logger.debug(
                f"Namespace {current_namespace} was excluded (exclusion list matches)"
            )
            continue

        logger.debug(
            f"Processing {len(resources)} {kind.endpoint} in namespace {current_namespace}.."
        )

        # Override defaults with (optional) annotations from Namespace
        namespace_obj = Namespace.objects(api).get_by_name(current_namespace)

        excluded = ignore_resource(namespace_obj, now)

        default_uptime_for_namespace = namespace_obj.annotations.get(
            UPTIME_ANNOTATION, default_uptime
        )
        default_downtime_for_namespace = namespace_obj.annotations.get(
            DOWNTIME_ANNOTATION, default_downtime
        )
        default_downtime_replicas_for_namespace = get_annotation_value_as_int(
            namespace_obj, DOWNTIME_REPLICAS_ANNOTATION
        )
        if default_downtime_replicas_for_namespace is None:
            default_downtime_replicas_for_namespace = downtime_replicas

        upscale_period_for_namespace = namespace_obj.annotations.get(
            UPSCALE_PERIOD_ANNOTATION, upscale_period
        )
        downscale_period_for_namespace = namespace_obj.annotations.get(
            DOWNSCALE_PERIOD_ANNOTATION, downscale_period
        )
        forced_uptime_value_for_namespace = str(
            namespace_obj.annotations.get(FORCE_UPTIME_ANNOTATION, forced_uptime)
        )
        if forced_uptime_value_for_namespace.lower() == "true":
            forced_uptime_for_namespace = True
        elif forced_uptime_value_for_namespace.lower() == "false":
            forced_uptime_for_namespace = False
        elif forced_uptime_value_for_namespace:
            forced_uptime_for_namespace = matches_time_spec(
                now, forced_uptime_value_for_namespace
            )
        else:
            forced_uptime_for_namespace = False

        for resource in resources:
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
                deployment_time_annotation=deployment_time_annotation,
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
    dry_run: bool,
    grace_period: int,
    downtime_replicas: int = 0,
    deployment_time_annotation: Optional[str] = None,
):
    api = helper.get_kube_api()

    now = datetime.datetime.now(datetime.timezone.utc)
    forced_uptime = pods_force_uptime(api, namespace)

    for clazz in RESOURCE_CLASSES:
        plural = clazz.endpoint
        if plural in include_resources:
            autoscale_resources(
                api,
                clazz,
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
                deployment_time_annotation,
            )
