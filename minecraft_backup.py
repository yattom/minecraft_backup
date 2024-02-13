import os
from pathlib import Path 
import re
import datetime
import shutil
import threading
import time
import tomllib
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def test_get_last_backup_timestamp(tmpdir):
    tmpdir.mkdir("20240101_012345")
    tmpdir.mkdir("20240101_012346")
    tmpdir.mkdir("not_backup")
    assert get_last_backup_datetime(Path(tmpdir)) == datetime.datetime(2024, 1, 1, 1, 23, 46)


def get_last_backup_datetime(backup_path: Path) -> datetime.datetime:
    last_datetime = datetime.datetime(1980, 1, 1, 0, 0, 0)
    for name in [n for n in backup_path.iterdir()]:
        m = re.match(r'^(\d{8})_(\d{6})$', name.stem)
        if not m:
            continue
        dt = datetime.datetime.strptime(m.group(0), '%Y%m%d_%H%M%S')
        if last_datetime < dt:
            last_datetime = dt
    return last_datetime 


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


def get_last_change_datetime(minecraft_directory: Path) -> datetime.datetime:
    last_change = datetime.datetime(1980, 1, 1, 0, 0, 0)
    for p in minecraft_directory.rglob('*'): 
        if p.is_file():
            ts = p.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(ts)
            if last_change < dt:
                last_change = dt
    return last_change


def read_config():
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    assert "minecraft_directory" in config
    assert "backup_path" in config
    assert "wait_time" in config
    config["minecraft_directory"] = Path(config["minecraft_directory"])
    config["backup_path"] = Path(config["backup_path"])
    return config


def watch_changes(minecraft_directory: Path, wait_time: int, backup_function: Callable[[], None]):
    class BackupHandler(FileSystemEventHandler):
        def __init__(self, backup_function, wait_time=5):
            self.backup_function = backup_function
            self.wait_time = wait_time
            self.debounce_timer = None

        def on_any_event(self, event):
            if self.debounce_timer is not None:
                self.debounce_timer.cancel()
            self.debounce_timer = threading.Timer(self.wait_time, self.backup_function)
            self.debounce_timer.start()

    event_handler = BackupHandler(backup_function=backup_function, wait_time=wait_time)
    observer = Observer()
    observer.schedule(event_handler, minecraft_directory, recursive=True)
    observer.start()
    

def make_new_backup_directory(backup_path: Path) -> Path:
    current_time = datetime.datetime.now()
    backup_dir_name = current_time.strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_path / backup_dir_name
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def backup_worlds(minecraft_directory: Path, backup_path: Path) -> None:
    new_backup_dir = make_new_backup_directory(backup_path)
    print(f"Starting new backup to {new_backup_dir}")

    for source_path in minecraft_directory.rglob('*'):  # Use rglob for recursion
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(minecraft_directory)  # Get path relative to source
        dest_path = new_backup_dir / relative_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)  # Create subdirs if needed 
        try:
            shutil.copy2(source_path, dest_path) 
            print(f"Copied: {source_path} -> {dest_path}")
        except shutil.Error as e:
            print(f"Error copying {source_path}: {e}")


def main():
    config = read_config()
    if get_last_backup_datetime(config["backup_path"]) < get_last_change_datetime(config["minecraft_directory"]):
        backup_worlds(config["minecraft_directory"], config["backup_path"])

    def do_backup():
        backup_worlds(config["minecraft_directory"], config["backup_path"])
    watch_changes(config["minecraft_directory"], config["wait_time"], do_backup)

    while True:
        time.sleep(100)


if __name__=='__main__':
    main()
