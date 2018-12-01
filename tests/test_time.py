import pytest

from datetime import datetime
from kube_downscaler.helper import matches_time_spec


def test_invalid_time_spec():
    with pytest.raises(ValueError):
        matches_time_spec(datetime.now(), '')


def test_time_spec():
    assert not matches_time_spec(datetime.now(), 'never')
    assert matches_time_spec(datetime.now(), 'always')
    assert not matches_time_spec(datetime.now(), 'Mon-Mon 00:00-00:00 CET')
    assert matches_time_spec(datetime.now(), 'Mon-Sun 00:00-24:00 CET')

    dt = datetime(2017, 11, 26, 15, 33)
    assert matches_time_spec(dt, 'Sat-Sun 15:30-16:00 UTC')
    assert not matches_time_spec(dt, 'Sat-Sun 15:34-16:00 UTC')
    assert not matches_time_spec(dt, 'Mon-Fri 08:00-18:00 UTC')

    assert matches_time_spec(dt, 'Mon-Fri 08:00-18:00 UTC, Sun-Sun 15:30-16:00 UTC')

    dt = datetime(2018, 11, 4, 20, 30, 00)
    assert matches_time_spec(dt, 'Mon-Fri 09:00-10:00 Pacific/Auckland')
    assert not matches_time_spec(dt, 'Sat-Sun 09:00-10:00 Pacific/Auckland')
