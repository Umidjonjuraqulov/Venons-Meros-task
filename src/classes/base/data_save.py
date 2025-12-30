from pathlib import Path
import shutil
import json

from .singleton import Singleton


class BaseDataSave(Singleton):
    empty_data = {}
    app_config_path: Path
    _config: dict

    def init(self, config_path: Path):
        """for the type annotation, fill in the arguments in __init__
        but the function should not do anything, since it should inherit from Singleton"""
        self.app_config_path = config_path
        self.app_config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self.load_config()

    def dump_json(self, info: dict) -> None:
        with open(self.app_config_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4, ensure_ascii=False)

    def load_config(self) -> dict:
        try:
            with self.app_config_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            self.handle_config_error()
            return self.empty_data

    def handle_config_error(self) -> None:
        backup_path = self.app_config_path.parent / f"error_{self.app_config_path.stem}.json"
        try:
            shutil.copy(self.app_config_path, backup_path)
        except FileNotFoundError:
            pass
        self.dump_json(self.empty_data)

    def save_config(self) -> None:
        self.dump_json(self._config)
