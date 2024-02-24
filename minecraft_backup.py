import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
import re
import datetime
import shutil
import time
import tomllib
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


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


def get_last_change_datetime(minecraft_directory: Path) -> datetime.datetime:
    last_change = datetime.datetime(1980, 1, 1, 0, 0, 0)
    for p in minecraft_directory.rglob('*'):
        if p.is_file():
            ts = p.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(ts)
            if last_change < dt:
                last_change = dt
    return last_change


@dataclass
class Config:
    minecraft_directory: Path
    backup_path: Path
    backup_interval: datetime.timedelta


def read_config() -> Config:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    assert "minecraft_directory" in config
    assert "backup_path" in config
    assert "backup_interval_minutes" in config
    config["minecraft_directory"] = Path(config["minecraft_directory"])
    config["backup_path"] = Path(config["backup_path"])
    return Config(
        minecraft_directory=Path(config["minecraft_directory"]),
        backup_path=Path(config["backup_path"]),
        backup_interval=datetime.timedelta(minutes=config["backup_interval_minutes"]),
    )


def start_watch_for_modification(minecraft_directory: Path, recorder: 'BackupScheduler'):
    class ModificationWatcher(FileSystemEventHandler):
        def __init__(self):
            self.recorder = recorder

        def on_modified(self, event):
            scheduler = self.recorder
            time = datetime.datetime.now()
            scheduler.last_modification_time = time

    event_handler = ModificationWatcher()
    observer = Observer()
    observer.schedule(event_handler, str(minecraft_directory), recursive=True)
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
            print(f"Copied: {relative_path}")
        except shutil.Error as e:
            print(f"Error copying {source_path}: {e}")


class BackupScheduler:
    DENOUNCEMENT_TIME = datetime.timedelta(seconds=5)

    def __init__(self, backup_interval: datetime.timedelta = datetime.timedelta(minutes=5)):
        self.backup_interval = backup_interval
        self.last_modification_time: datetime.datetime = None
        self.last_backup_time: datetime.datetime = None

    def needs_backup(self, upon) -> bool:
        if self.no_recorded_modification():
            return False
        if self.no_backup_ever():
            return True
        if self.updated_since_last_backup():
            return self.is_safe_margin_passed_since_last_modification(upon)
        return False

    def is_safe_margin_passed_since_last_modification(self, upon):
        return self.last_modification_time + BackupScheduler.DENOUNCEMENT_TIME < upon

    def updated_since_last_backup(self):
        if self.no_recorded_modification():
            return False
        if self.no_backup_ever():
            return True
        return self.last_backup_time < self.last_modification_time

    def no_backup_ever(self):
        return not self.last_backup_time

    def no_recorded_modification(self):
        return not self.last_modification_time

    def next_check_time(self, last_checked: datetime.datetime) -> datetime.timedelta:
        if self.updated_since_last_backup() and not self.is_safe_margin_passed_since_last_modification(last_checked):
            return self.next_check_time_after_denouncement_wait(last_checked)
        return self.backup_interval

    def next_check_time_after_denouncement_wait(self, last_checked):
        return BackupScheduler.DENOUNCEMENT_TIME - (last_checked - self.last_modification_time)


def start_auto_backup(config: Config, do_backup: Callable[[], None]):
    scheduler = BackupScheduler(config.backup_interval)
    scheduler.last_modification_time = get_last_change_datetime(config.minecraft_directory)
    scheduler.last_backup_time = get_last_backup_datetime(config.backup_path)
    start_watch_for_modification(config.minecraft_directory, scheduler)

    while True:
        if scheduler.needs_backup(datetime.datetime.now()):
            do_backup()
            scheduler.last_backup_time = datetime.datetime.now()
        time.sleep(scheduler.next_check_time(datetime.datetime.now()).total_seconds())


def main():
    config = read_config()

    def do_backup():
        backup_worlds(config.minecraft_directory, config.backup_path)

    try:
        start_auto_backup(config, do_backup)
    except:
        traceback.print_exc()
        input("Press Enter to exit")
        sys.exit(1)


if __name__ == '__main__':
    main()
