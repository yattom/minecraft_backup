import pytest
from datetime import datetime, timedelta
import os
from pathlib import Path

from minecraft_backup import get_last_change_datetime, get_last_backup_datetime, BackupScheduler


def test_get_last_change_datetime(tmpdir):
    f1 = tmpdir.mkdir("dir1").join("file1")
    f1.write("")
    d1 = datetime(2024, 1, 1, 1, 23, 45)
    os.utime(f1, (d1.timestamp(), d1.timestamp()))

    f2 = tmpdir.mkdir("dir2").join("file2")
    f2.write("")
    d2 = datetime(2024, 1, 1, 1, 23, 46)
    os.utime(f2, (d2.timestamp(), d2.timestamp()))

    assert get_last_change_datetime(Path(tmpdir)) == d2


def test_get_last_backup_timestamp(tmpdir):
    tmpdir.mkdir("20240101_012345")
    tmpdir.mkdir("20240101_012346")
    tmpdir.mkdir("not_backup")
    assert get_last_backup_datetime(Path(tmpdir)) == datetime(2024, 1, 1, 1, 23, 46)


@pytest.fixture
def t0():
    return datetime.now()


class T:
    _10SEC = timedelta(seconds=10)
    _5SEC = timedelta(seconds=5)
    _1MIN = timedelta(minutes=1)
    _2MIN = timedelta(minutes=2)
    # noinspection NonAsciiCharacters
    _ε = timedelta(seconds=1)


class TestBackupTrigger:
    class TestNeedsTrigger:
        def test_no_backup_upon_no_changes(self, t0):
            sut = BackupScheduler()
            sut.record_modification(t0 - T._ε)
            sut.record_backup_execution(t0)
            assert not sut.needs_backup(t0 + T._ε)

        def test_trigger_10sec_after_modification(self, t0):
            sut = BackupScheduler()
            sut.record_modification(t0)
            assert sut.needs_backup(t0 + T._10SEC)

        def test_no_trigger_less_than_5sec_after_modification(self, t0):
            sut = BackupScheduler()
            sut.record_backup_execution(t0 - T._1MIN)
            sut.record_modification(t0)
            assert not sut.needs_backup(t0 + (T._5SEC - T._ε))

    class TestNextCheckTime:
        def test_first_check(self, t0):
            sut = BackupScheduler()
            assert sut.next_check_time(t0) == t0 + timedelta(minutes=5)

        def test_5min_interval(self, t0):
            sut = BackupScheduler()
            sut.record_modification(t0 - T._2MIN)
            sut.record_backup_execution(t0 - T._1MIN)
            assert sut.next_check_time(t0) == t0 + timedelta(minutes=5)

        def test_5sec_safe_margin(self, t0):
            sut = BackupScheduler()
            sut.record_backup_execution(t0 - T._1MIN)
            sut.record_modification(t0)
            assert sut.next_check_time(t0) == t0 + T._5SEC
