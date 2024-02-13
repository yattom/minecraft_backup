import datetime
import os
from pathlib import Path

from minecraft_backup import get_last_change_datetime, get_last_backup_datetime


def test_get_last_change_datetime(tmpdir):
    f1 = tmpdir.mkdir("dir1").join("file1")
    f1.write("")
    d1 = datetime.datetime(2024, 1, 1, 1, 23, 45)
    os.utime(f1, (d1.timestamp(), d1.timestamp()))

    f2 = tmpdir.mkdir("dir2").join("file2")
    f2.write("")
    d2 = datetime.datetime(2024, 1, 1, 1, 23, 46)
    os.utime(f2, (d2.timestamp(), d2.timestamp()))

    assert get_last_change_datetime(Path(tmpdir)) == d2


def test_get_last_backup_timestamp(tmpdir):
    tmpdir.mkdir("20240101_012345")
    tmpdir.mkdir("20240101_012346")
    tmpdir.mkdir("not_backup")
    assert get_last_backup_datetime(Path(tmpdir)) == datetime.datetime(2024, 1, 1, 1, 23, 46)
