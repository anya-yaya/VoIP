"""
config_resolver.py

Resolves the complete configuration required by the VoIP dataset generator.

Responsibilities:
- Load the selected scenario configuration.
- Load the scenario-specific advanced behaviour configuration.
- Load the shared generic configuration files.
- Resolve the final configuration into one structured object.
- Validate that required configuration sections exist.

This module does NOT:
- Generate users.
- Generate sessions.
- Generate timestamps.
- Generate network data.
- Generate datasets.

"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config_loader import ConfigLoader


class ConfigResolver:
    """
    Resolves generic configuration + scenario configuration
    + scenario-specific advanced behaviour.
    """

    # Scenario aliases used by the run configuration.
    SCENARIO_ALIASES = {
        "enterprise": "enterprise",
        "customer_support": "customer_support_center",
        "customer_support_center": "customer_support_center",
        "customer_support_scenario": "customer_support_center",
    }

    # Scenario-specific directories and files.
    SCENARIO_FILES = {
        "enterprise": {
            "directory": "enterprise",
            "base": "enterprise.json",
            "advanced": "enterprise_adv.json",
        },
        "customer_support_center": {
            "directory": "customer_support_center",
            "base": "customer_support_center.json",
            "advanced": "customer_support_center_adv.json",
        },
    }

    # Shared configuration files required by the generator.
    GENERIC_CONFIG_FILES = {
        "communication_categories": (
            "communication_categories.json"
        ),
        "communication_patterns": (
            "communication_patterns.json"
        ),
        "caller_callee_selection": (
            "caller_callee_selection.json"
        ),
        "protocol_codec_assignment": (
            "protocol_codec_assignment.json"
        ),
        "user_population_characteristics": (
            "user_population_characteristics.json"
        ),
    }

    REQUIRED_ENVIRONMENT_SECTIONS = {
        "metadata",
        "observation_period",
        "communication_scale",
        "traffic_distribution",
        "call_outcome_distribution",
        "organizational_structure",
        "network_configuration",
        "protocol_configuration",
        "codec_distribution",
    }

    def __init__(self, project_root: str | Path):
        """
        Args:
            project_root:
                Root directory of the VoIP project.

                Example:
                    C:/Users/anya2/Desktop/VoIP
        """

        self.project_root = Path(project_root).resolve()
        self.config_root = self.project_root /  "config"

        if not self.project_root.exists():
            raise FileNotFoundError(
                f"Project root not found: {self.project_root}"
            )

        if not self.project_root.is_dir():
            raise NotADirectoryError(
                f"Project root is not a directory: {self.project_root}"
            )

        # ConfigLoader works relative to the supplied root.
        self.loader = ConfigLoader(self.config_root)

    # ------------------------------------------------------------------
    # Path handling
    # ------------------------------------------------------------------

    def _resolve_path(self, relative_path: str | Path) -> Path:
        """Convert a config-relative path into an absolute path."""

        path = Path(relative_path)

        if path.is_absolute():
            return path

        return self.config_root / path

    # ------------------------------------------------------------------
    # Scenario handling
    # ------------------------------------------------------------------

    def normalize_scenario(self, scenario: str) -> str:
        """
        Normalize a scenario name to the canonical internal name.

        Examples:
            enterprise
            customer_support
            customer_support_center
            customer_support_scenario

        Returns:
            Canonical scenario name.
        """

        if not isinstance(scenario, str):
            raise TypeError(
                "Scenario name must be a string."
            )

        normalized = scenario.strip().lower()

        if normalized not in self.SCENARIO_ALIASES:
            supported = ", ".join(
                sorted(self.SCENARIO_ALIASES.keys())
            )

            raise ValueError(
                f"Unsupported scenario '{scenario}'. "
                f"Supported names: {supported}"
            )

        return self.SCENARIO_ALIASES[normalized]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_base_scenario(
        self,
        scenario: str,
    ) -> dict[str, Any]:
        """Load the main scenario configuration."""

        canonical = self.normalize_scenario(scenario)

        scenario_info = self.SCENARIO_FILES[canonical]

        path = (
            Path(scenario_info["directory"])
            / scenario_info["base"]
        )

        return self.loader.load_file(path)

    def load_advanced_scenario(
        self,
        scenario: str,
    ) -> dict[str, Any]:
        """Load the scenario-specific advanced behaviour configuration."""

        canonical = self.normalize_scenario(scenario)

        scenario_info = self.SCENARIO_FILES[canonical]

        path = (
            Path(scenario_info["directory"])
            / scenario_info["advanced"]
        )

        return self.loader.load_file(path)

    def load_generic_configurations(self) -> dict[str, Any]:
        """
        Load all shared configuration files.

        Returns:
            Dictionary containing the generic configuration resources.
        """

        configurations: dict[str, Any] = {}

        for name, relative_path in self.GENERIC_CONFIG_FILES.items():
            configurations[name] = self.loader.load_file(
                relative_path
            )

        return configurations

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_base_scenario(
        self,
        configuration: dict[str, Any],
        scenario: str,
    ) -> None:
        """Validate the main scenario configuration."""

        if not isinstance(configuration, dict):
            raise ValueError(
                f"Base configuration for '{scenario}' "
                "must be a JSON object."
            )

        missing = (
            self.REQUIRED_ENVIRONMENT_SECTIONS
            - configuration.keys()
        )

        if missing:
            missing_text = ", ".join(sorted(missing))

            raise ValueError(
                f"Base configuration for '{scenario}' "
                f"is missing required sections: {missing_text}"
            )

    def validate_advanced_scenario(
        self,
        configuration: dict[str, Any],
        scenario: str,
    ) -> None:
        """Validate the advanced scenario configuration."""

        if not isinstance(configuration, dict):
            raise ValueError(
                f"Advanced configuration for '{scenario}' "
                "must be a JSON object."
            )

        if scenario == "enterprise":
            required = {
                "organization",
                "role_labels",
                "selection",
                "duration_model",
                "ring_duration_model",
            }

        elif scenario == "customer_support_center":
            required = {
                "organization",
                "role_labels",
                "shifts",
                "shift_sampling",
                "escalation",
                "selection",
                "duration_model",
                "ring_duration_model",
                "abandonment",
            }

        else:
            required = set()

        missing = required - configuration.keys()

        if missing:
            missing_text = ", ".join(sorted(missing))

            raise ValueError(
                f"Advanced configuration for '{scenario}' "
                f"is missing required sections: {missing_text}"
            )

    # ------------------------------------------------------------------
    # Generic resource validation
    # ------------------------------------------------------------------

    def validate_generic_configurations(
        self,
        configurations: dict[str, Any],
    ) -> None:
        """Validate that generic configuration files loaded correctly."""

        required = set(self.GENERIC_CONFIG_FILES.keys())

        missing = required - configurations.keys()

        if missing:
            missing_text = ", ".join(sorted(missing))

            raise ValueError(
                "Missing generic configurations: "
                f"{missing_text}"
            )

        for name, configuration in configurations.items():
            if not isinstance(configuration, dict):
                raise ValueError(
                    f"Generic configuration '{name}' "
                    "must be a JSON object."
                )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_scenario(
        self,
        scenario: str,
        include_advanced: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve all configuration required for a scenario.

        The returned structure intentionally keeps the scenario
        configuration and advanced behaviour separate.

        This is important because the *_adv.json files in the project
        are behaviour overrides, not replacements for the main
        environment configuration.

        Returns:
            A resolved configuration dictionary.
        """

        canonical = self.normalize_scenario(scenario)

        # --------------------------------------------------------------
        # Load main scenario configuration
        # --------------------------------------------------------------

        base_config = self.load_base_scenario(canonical)

        self.validate_base_scenario(
            base_config,
            canonical,
        )

        # --------------------------------------------------------------
        # Load generic configuration
        # --------------------------------------------------------------

        generic_config = self.load_generic_configurations()

        self.validate_generic_configurations(
            generic_config
        )

        # --------------------------------------------------------------
        # Load advanced behaviour configuration
        # --------------------------------------------------------------

        if include_advanced:
            advanced_config = self.load_advanced_scenario(
                canonical
            )

            self.validate_advanced_scenario(
                advanced_config,
                canonical,
            )
        else:
            advanced_config = {}

        # --------------------------------------------------------------
        # Build resolved configuration
        # --------------------------------------------------------------

        resolved = {
            "scenario": canonical,

            "environment": deepcopy(base_config),

            "behavior_overrides": deepcopy(
                advanced_config
            ),

            "communication_categories": deepcopy(
                generic_config["communication_categories"]
            ),

            "communication_patterns": deepcopy(
                generic_config["communication_patterns"]
            ),

            "caller_callee_selection": deepcopy(
                generic_config["caller_callee_selection"]
            ),

            "protocol_codec_assignment": deepcopy(
                generic_config["protocol_codec_assignment"]
            ),

            "user_population_characteristics": deepcopy(
                generic_config[
                    "user_population_characteristics"
                ]
            ),
        }

        # --------------------------------------------------------------
        # Add useful metadata
        # --------------------------------------------------------------

        resolved["resolution"] = {
            "scenario": canonical,
            "advanced_behavior_loaded": include_advanced,
            "source_files": {
                "environment": str(
                    self._resolve_path(
                        self.SCENARIO_FILES[canonical]["directory"]
                    )
                    / self.SCENARIO_FILES[canonical]["base"]
                ),
                "advanced_behavior": (
                    str(
                        self._resolve_path(
                            self.SCENARIO_FILES[canonical]["directory"]
                        )
                        / self.SCENARIO_FILES[canonical]["advanced"]
                    )
                    if include_advanced
                    else None
                ),
            },
        }

        return resolved

    # ------------------------------------------------------------------
    # Run configuration support
    # ------------------------------------------------------------------

    def resolve_run_environment(
        self,
        environment_config: dict[str, Any],
        include_advanced: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve a single environment entry from a run configuration.

        Example input:

        {
            "environment_id": "enterprise",
            "base_scenario": "enterprise"
        }

        or:

        {
            "environment_id": "customer_support_center",
            "base_scenario": "customer_support_scenario"
        }
        """

        if not isinstance(environment_config, dict):
            raise ValueError(
                "Environment configuration must be a JSON object."
            )

        scenario = environment_config.get(
            "base_scenario"
        )

        if not scenario:
            raise ValueError(
                "Environment configuration must contain "
                "'base_scenario'."
            )

        resolved = self.resolve_scenario(
            scenario,
            include_advanced=include_advanced,
        )

        # Preserve the environment ID from the run configuration.
        if "environment_id" in environment_config:
            resolved["environment_id"] = (
                environment_config["environment_id"]
            )

        # Preserve any future run-level options without modifying
        # the underlying scenario configuration.
        resolved["run_environment"] = deepcopy(
            environment_config
        )

        return resolved


# ----------------------------------------------------------------------
# Convenience function
# ----------------------------------------------------------------------

def resolve_scenario(
    project_root: str | Path,
    scenario: str,
    include_advanced: bool = True,
) -> dict[str, Any]:
    """
    Convenience function for resolving a scenario.
    """

    resolver = ConfigResolver(project_root)

    return resolver.resolve_scenario(
        scenario,
        include_advanced=include_advanced,
    )


# ----------------------------------------------------------------------
# Command-line test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    # config_resolver.py is located in:
    #
    # VoIP/src/config_resolver.py
    #
    # Therefore the project root is one directory above src/.

    PROJECT_ROOT = (
        Path(__file__).resolve().parent.parent
    )

    resolver = ConfigResolver(PROJECT_ROOT)

    print("=" * 60)
    print("VoIP Configuration Resolver")
    print("=" * 60)

    # --------------------------------------------------------------
    # Enterprise test
    # --------------------------------------------------------------

    enterprise = resolver.resolve_scenario(
        "enterprise",
        include_advanced=True,
    )

    print("\nEnterprise configuration resolved successfully.")

    print(
        "Scenario:",
        enterprise["scenario"]
    )

    print(
        "Environment:",
        enterprise["environment"]["metadata"]["name"]
    )

    print(
        "Advanced behaviour:",
        enterprise["resolution"][
            "advanced_behavior_loaded"
        ]
    )

    # --------------------------------------------------------------
    # Customer Support test
    # --------------------------------------------------------------

    customer_support = resolver.resolve_scenario(
        "customer_support_center",
        include_advanced=True,
    )

    print(
        "\nCustomer Support configuration "
        "resolved successfully."
    )

    print(
        "Scenario:",
        customer_support["scenario"]
    )

    print(
        "Environment:",
        customer_support["environment"]["metadata"]["name"]
    )

    print(
        "Advanced behaviour:",
        customer_support["resolution"][
            "advanced_behavior_loaded"
        ]
    )

    print("\nConfiguration resolution completed.")