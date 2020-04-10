from datetime import datetime
from datetime import timezone

import pytest

from kube_downscaler.helper import matches_time_spec


def test_invalid_time_spec():
    with pytest.raises(ValueError):
        matches_time_spec(datetime.now(), "")


def test_time_spec():
    assert not matches_time_spec(datetime.now(), "never")
    assert matches_time_spec(datetime.now(), "always")
    assert not matches_time_spec(datetime.now(), "Mon-Mon 00:00-00:00 CET")
    assert matches_time_spec(datetime.now(), "Mon-Sun 00:00-24:00 CET")

    # Sunday, November 26th 2017
    dt = datetime(2017, 11, 26, 15, 33, tzinfo=timezone.utc)
    assert matches_time_spec(dt, "Sat-Sun 15:30-16:00 UTC")
    assert not matches_time_spec(dt, "Sat-Sun 15:34-16:00 UTC")
    assert not matches_time_spec(dt, "Mon-Fri 08:00-18:00 UTC")

    assert matches_time_spec(dt, "Mon-Fri 08:00-18:00 UTC, Sun-Sun 15:30-16:00 UTC")

    assert matches_time_spec(dt, "2017-11-26T14:04:48+00:00-2017-11-26T16:04:48+00:00")
    assert not matches_time_spec(
        dt, "2017-11-26T14:04:48+00:00-2017-11-26T15:04:48+00:00"
    )

    dt = datetime(2018, 11, 4, 20, 30, 00, tzinfo=timezone.utc)
    assert matches_time_spec(dt, "Mon-Fri 09:00-10:00 Pacific/Auckland")
    assert not matches_time_spec(dt, "Sat-Sun 09:00-10:00 Pacific/Auckland")

    assert matches_time_spec(dt, "2017-01-01T00:01:02+00:00-2018-12-31T23:59:00+00:00")
    assert matches_time_spec(
        dt,
        "2017-01-01T00:01:02+00:00-2017-01-02T19:00:50+00:00, 2018-11-01T00:00:00+00:00-2018-12-31T23:59:00+00:00",
    )
    assert not matches_time_spec(
        dt, "2019-01-01T00:01:02+00:00-2019-12-31T23:59:00+00:00"
    )

    assert matches_time_spec(dt, "2018-11-04T16:00:00-04:00-2018-11-04T16:40:00-04:00")
    assert not matches_time_spec(
        dt, "2018-11-04T20:00:00-04:00-2018-11-04T20:40:00-04:00"
    )


def test_time_spec_error_message():
    """Test that the correct error message is shown to the user."""
    dt = datetime(2020, 4, 10, 10, 11, tzinfo=timezone.utc)
    with pytest.raises(ValueError) as excinfo:
        matches_time_spec(
            dt, "Mon-Thur 09:00-20:00 Europe/London,Fri-Fri 10:00-18:00 Europe/London"
        )
    assert (
        'Time spec value "Mon-Thur 09:00-20:00 Europe/London" does not match format ("Mon-Fri 06:30-20:30 Europe/Berlin" or "2019-01-01T00:00:00+00:00-2019-01-02T12:34:56+00:00")'
        in str(excinfo.value)
    )


def test_week_starts_sunday():
    # Monday, November 27th 2017
    dt = datetime(2017, 11, 27, 15, 33, tzinfo=timezone.utc)
    assert matches_time_spec(dt, "Sun-Fri 15:30-16:00 UTC")
    assert matches_time_spec(dt, "Sun-Mon 00:00-16:00 UTC")
    assert not matches_time_spec(dt, "Sun-Mon 00:00-15:00 UTC")

    # Sunday, November 26th 2017
    dt = datetime(2017, 11, 26, 15, 33, tzinfo=timezone.utc)
    assert matches_time_spec(dt, "Sun-Fri 15:30-16:00 UTC")
    assert matches_time_spec(dt, "Sun-Mon 00:00-16:00 UTC")
    assert not matches_time_spec(dt, "Sun-Mon 00:00-15:00 UTC")
