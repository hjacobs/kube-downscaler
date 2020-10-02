import datetime
import logging
import re
from typing import Match

import pykube
import pytz

logger = logging.getLogger(__name__)

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

TIME_SPEC_PATTERN = re.compile(
    r"^([a-zA-Z]{3})-([a-zA-Z]{3}) (\d\d):(\d\d)-(\d\d):(\d\d) (?P<tz>[a-zA-Z/_]+)$"
)
_ISO_8601_TIME_SPEC_PATTERN = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2})"
ABSOLUTE_TIME_SPEC_PATTERN = re.compile(
    r"^{0}-{0}$".format(_ISO_8601_TIME_SPEC_PATTERN)
)


def matches_time_spec(time: datetime.datetime, spec: str):
    if spec.lower() == "always":
        return True
    elif spec.lower() == "never":
        return False
    for spec_ in spec.split(","):
        spec_ = spec_.strip()
        recurring_match = TIME_SPEC_PATTERN.match(spec_)
        if recurring_match is not None and _matches_recurring_time_spec(
            time, recurring_match
        ):
            return True
        absolute_match = ABSOLUTE_TIME_SPEC_PATTERN.match(spec_)
        if absolute_match and _matches_absolute_time_spec(time, absolute_match):
            return True
        if not recurring_match and not absolute_match:
            raise ValueError(
                f'Time spec value "{spec_}" does not match format ("Mon-Fri 06:30-20:30 Europe/Berlin" or "2019-01-01T00:00:00+00:00-2019-01-02T12:34:56+00:00")'
            )
    return False


def _matches_recurring_time_spec(time: datetime.datetime, match: Match):
    tz = pytz.timezone(match.group("tz"))
    local_time = tz.fromutc(time.replace(tzinfo=tz))
    day_from = WEEKDAYS.index(match.group(1).upper())
    day_to = WEEKDAYS.index(match.group(2).upper())
    if day_from > day_to:
        # wrap around, e.g. Sun-Fri (makes sense for countries with work week starting on Sunday)
        day_matches = local_time.weekday() >= day_from or local_time.weekday() <= day_to
    else:
        # e.g. Mon-Fri
        day_matches = day_from <= local_time.weekday() <= day_to
    local_time_minutes = local_time.hour * 60 + local_time.minute
    minute_from = int(match.group(3)) * 60 + int(match.group(4))
    minute_to = int(match.group(5)) * 60 + int(match.group(6))
    time_matches = minute_from <= local_time_minutes < minute_to
    return day_matches and time_matches


def _matches_absolute_time_spec(time: datetime.datetime, match: Match):
    time_from = datetime.datetime.fromisoformat(match.group(1))
    time_to = datetime.datetime.fromisoformat(match.group(2))
    return time_from <= time <= time_to


def get_kube_api():
    config = pykube.KubeConfig.from_env()
    api = pykube.HTTPClient(config)
    return api


def add_event(resource, message: str, reason: str, event_type: str, dry_run: bool):
    event = (
        pykube.objects.Event.objects(resource.api)
        .filter(
            namespace=resource.namespace,
            field_selector={
                "involvedObject.uid": resource.metadata.get("uid"),
                "reason": reason,
                "type": event_type,
            },
        )
        .get_or_none()
    )
    if event and event.obj["message"] == message:
        now = datetime.datetime.utcnow()
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        event.obj["count"] = event.obj["count"] + 1
        event.obj["lastTimestamp"] = timestamp
        try:
            event.update()
            return event
        except Exception as e:
            logger.error(f"Could not update event {event.obj}: {e}")
        return

    return create_event(resource, message, reason, event_type, dry_run)


def create_event(resource, message: str, reason: str, event_type: str, dry_run: bool):
    now = datetime.datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    event = pykube.Event(
        resource.api,
        {
            "metadata": {
                "namespace": resource.namespace,
                "generateName": "kube-downscaler-",
            },
            "type": event_type,
            "count": 1,
            "firstTimestamp": timestamp,
            "lastTimestamp": timestamp,
            "reason": reason,
            "involvedObject": {
                "apiVersion": resource.version,
                "name": resource.name,
                "namespace": resource.namespace,
                "kind": resource.kind,
                "resourceVersion": resource.metadata.get("resourceVersion"),
                # https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#uids
                "uid": resource.metadata.get("uid"),
            },
            "message": message,
            "source": {"component": "kube-downscaler"},
        },
    )
    if not dry_run:
        try:
            event.create()
            return event
        except Exception as e:
            logger.error(f"Could not create event {event.obj}: {e}")
