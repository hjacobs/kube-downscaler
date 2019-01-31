import os

import datetime
import pykube
import pytz
import re

WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

TIME_SPEC_PATTERN = re.compile(r'^([a-zA-Z]{3})-([a-zA-Z]{3}) (\d\d):(\d\d)-(\d\d):(\d\d) (?P<tz>[a-zA-Z/_]+)$')


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
        tz = pytz.timezone(match.group('tz'))
        local_time = tz.fromutc(time.replace(tzinfo=tz))
        day_from = WEEKDAYS.index(match.group(1).upper())
        day_to = WEEKDAYS.index(match.group(2).upper())
        day_matches = day_from <= local_time.weekday() <= day_to
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
        config = pykube.KubeConfig.from_file((('KUBECONFIG' in os.environ) and os.environ['KUBECONFIG']) or os.path.expanduser('~/.kube/config'))
    api = pykube.HTTPClient(config)
    return api
