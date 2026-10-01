"""
config_loader.py

Responsible only for loading JSON configuration files.

It does not:
- merge configurations
- resolve overrides
- generate users
- generate sessions
"""

import json
from pathlib import Path
from typing import Any


class ConfigLoader:
    """Loads JSON configuration files from the project config directory."""

    def __init__(self, config_root: str | Path):
        self.config_root = Path(config_root).resolve()

        if not self.config_root.exists():
            raise FileNotFoundError(
                f"Configuration directory not found: {self.config_root}"
            )

        if not self.config_root.is_dir():
            raise NotADirectoryError(
                f"Configuration root is not a directory: {self.config_root}"
            )

    def load_file(self, file_path: str | Path) -> dict[str, Any]:
        """
        Load a JSON file.

        Relative paths are resolved from config_root.
        """

        path = Path(file_path)

        if not path.is_absolute():
            path = self.config_root / path

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Configuration path is not a file: {path}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in configuration file: {path}\n"
                f"Line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Configuration root must be a JSON object: {path}"
            )

        return data

    def load_scenario(
        self,
        scenario: str,
        advanced: bool = False
    ) -> dict[str, Any]:
        """
        Load a scenario configuration.

        Supported scenarios:
            enterprise
            customer_support_center
        """

        scenario = scenario.strip().lower()

        scenario_files = {
            "enterprise": {
                False: Path("enterprise") / "enterprise.json",
                True: Path("enterprise") / "enterprise_adv.json",
            },
            "customer_support_center": {
                False: (
                    Path("customer_support_center")
                    / "customer_support_center.json"
                ),
                True: (
                    Path("customer_support_center")
                    / "customer_support_center_adv.json"
                ),
            },
        }

        if scenario not in scenario_files:
            raise ValueError(
                f"Unsupported scenario '{scenario}'. "
                f"Supported scenarios: "
                f"{', '.join(scenario_files.keys())}"
            )

        return self.load_file(
            scenario_files[scenario][advanced]
        )


def load_json(
    file_path: str | Path
) -> dict[str, Any]:
    """
    Convenience function for loading a JSON file directly.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}\n"
            f"Line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Configuration root must be a JSON object: {path}"
        )

    return data


if __name__ == "__main__":

    # config_loader.py is inside:
    # VoIP/src/
    #
    # Therefore:
    # project_root = parent of src
    # config_root  = project_root/config

    project_root = Path(__file__).resolve().parent.parent
    config_root = project_root / "config"

    loader = ConfigLoader(config_root)

    enterprise = loader.load_scenario(
        "enterprise",
        advanced=False
    )

    enterprise_adv = loader.load_scenario(
        "enterprise",
        advanced=True
    )

    customer_support = loader.load_scenario(
        "customer_support_center",
        advanced=False
    )

    customer_support_adv = loader.load_scenario(
        "customer_support_center",
        advanced=True
    )

    print("Configuration loading successful.")
    print(
        "Enterprise:",
        enterprise.get("metadata", {}).get("name")
    )
    print(
        "Enterprise Advanced:",
        enterprise_adv.get("metadata", {}).get("name")
    )
    print(
        "Customer Support:",
        customer_support.get("metadata", {}).get("name")
    )
    print(
        "Customer Support Advanced:",
        customer_support_adv.get("metadata", {}).get("name")
    )