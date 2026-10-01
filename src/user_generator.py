"""
user_generator.py

Phase 2 - Step 1: Synthetic User Population Generator

This module generates users using ONLY the resolved configuration produced by
config_resolver.py.

Supported scenarios:
    - enterprise
    - customer_support_center

Responsibilities:
    - Generate internal and external users.
    - Generate user identities.
    - Generate phone numbers/extensions.
    - Generate SIP identifiers.
    - Allocate IP addresses.
    - Assign departments/groups.
    - Assign scenario-specific roles.
    - Assign communication activity level.
    - Assign communication behaviour profile.
    - Assign preferred active days.
    - Assign preferred communication categories.
    - Assign frequent contacts.
    - Assign active/inactive status.
    - Assign call weight.

This module does NOT:
    - Generate communication sessions.
    - Select caller/callee pairs.
    - Generate timestamps.
    - Generate outcomes.
    - Generate durations.
    - Generate protocols/codecs.
    - Generate events.
    - Export CSV/JSON.

Input:
    Resolved configuration returned by ConfigResolver.resolve_scenario()

Output:
    list[dict[str, Any]]
"""


from __future__ import annotations

import ipaddress
import random
import uuid
from collections import defaultdict
from typing import Any


class UserGenerator:
    """
    Generates a synthetic user population from a resolved scenario
    configuration.
    """

    def __init__(
        self,
        resolved_config: dict[str, Any],
        seed: int | None = None,
    ) -> None:

        if not isinstance(resolved_config, dict):
            raise TypeError(
                "resolved_config must be a dictionary."
            )

        self.config = resolved_config

        if seed is not None:
            random.seed(seed)

        self.scenario = self._get_scenario()

        self.environment = resolved_config.get(
            "environment"
        )

        if not isinstance(self.environment, dict):
            raise ValueError(
                "Resolved configuration does not contain "
                "a valid 'environment' object."
            )

        self.behavior_overrides = resolved_config.get(
            "behavior_overrides",
            {}
        )

        if not isinstance(self.behavior_overrides, dict):
            raise ValueError(
                "'behavior_overrides' must be a JSON object."
            )

        self.population_config = self._get_population_config()

        self.organization = self.environment.get(
            "organizational_structure",
            {}
        )

        if not isinstance(self.organization, dict):
            raise ValueError(
                "'organizational_structure' must be a JSON object."
            )

        self.network_config = self.environment.get(
            "network_configuration",
            {}
        )

        if not isinstance(self.network_config, dict):
            raise ValueError(
                "'network_configuration' must be a JSON object."
            )

        self.communication_scale = self.environment.get(
            "communication_scale",
            {}
        )

        if not isinstance(self.communication_scale, dict):
            raise ValueError(
                "'communication_scale' must be a JSON object."
            )

        # Track generated values that must be unique.
        self.used_user_ids: set[str] = set()
        self.used_extensions: set[str] = set()

        # Track allocated internal IPs.
        self.used_internal_ips: set[str] = set()

        # Department -> assigned manager.
        #
        # This is primarily useful for the Enterprise hierarchical
        # organization.
        self.department_manager_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Configuration access
    # ------------------------------------------------------------------

    def _get_scenario(self) -> str:
        """
        Get the canonical scenario name from the resolver output.
        """

        scenario = self.config.get("scenario")

        if not scenario:
            raise ValueError(
                "Resolved configuration does not contain 'scenario'."
            )

        scenario = str(scenario).strip().lower()

        if scenario == "customer_support":
            return "customer_support_center"

        if scenario == "customer_support_scenario":
            return "customer_support_center"

        if scenario not in {
            "enterprise",
            "customer_support_center",
        }:
            raise ValueError(
                f"Unsupported scenario: {scenario}"
            )

        return scenario

    def _get_population_config(self) -> dict[str, Any]:
        """
        Retrieve the scenario-specific section from
        user_population_characeristics.json.

        The source ZIP uses:
            enterprise
            customer_support_scenario
        """

        all_population_config = self.config.get(
            "user_population_characteristics"
        )

        if not isinstance(all_population_config, dict):
            raise ValueError(
                "Resolved configuration does not contain "
                "'user_population_characteristics'."
            )

        population_by_environment = (
            all_population_config.get(
                "population_by_environment"
            )
        )

        if not isinstance(
            population_by_environment,
            dict
        ):
            raise ValueError(
                "user_population_characteristics does not contain "
                "'population_by_environment'."
            )

        if self.scenario == "enterprise":
            key = "enterprise"

        else:
            key = "customer_support_scenario"

        population = population_by_environment.get(key)

        if not isinstance(population, dict):
            raise ValueError(
                f"No population configuration found for '{key}'."
            )

        return population

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_choice(
        distribution: dict[str, float]
    ) -> str:
        """
        Select a value according to configured weights.
        """

        if not distribution:
            raise ValueError(
                "Weighted distribution cannot be empty."
            )

        values = list(distribution.keys())
        weights = list(distribution.values())

        if any(
            not isinstance(weight, (int, float))
            or weight < 0
            for weight in weights
        ):
            raise ValueError(
                "Distribution weights must be non-negative numbers."
            )

        if sum(weights) <= 0:
            raise ValueError(
                "Distribution must contain at least one positive weight."
            )

        return random.choices(
            values,
            weights=weights,
            k=1,
        )[0]

    @staticmethod
    def _validate_distribution(
        distribution: dict[str, Any],
        field_name: str,
    ) -> None:

        if not isinstance(distribution, dict):
            raise ValueError(
                f"'{field_name}' must be an object."
            )

        for key, value in distribution.items():

            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"'{field_name}.{key}' must be numeric."
                )

            if value < 0:
                raise ValueError(
                    f"'{field_name}.{key}' cannot be negative."
                )

        if sum(distribution.values()) <= 0:
            raise ValueError(
                f"'{field_name}' must contain a positive weight."
            )

    # ------------------------------------------------------------------
    # Population size
    # ------------------------------------------------------------------

    def _get_total_users(self) -> int:
        """
        Get the population size from communication_scale.num_users.
        """

        num_users = self.communication_scale.get(
            "num_users"
        )

        if not isinstance(num_users, int):
            raise ValueError(
                "communication_scale.num_users must be an integer."
            )

        if num_users <= 0:
            raise ValueError(
                "communication_scale.num_users must be greater than zero."
            )

        return num_users

    def _get_internal_external_counts(
        self,
        total_users: int,
    ) -> tuple[int, int]:
        """
        Calculate internal and external population sizes using the exact
        internal_vs_external_ratio from user population configuration.
        """

        ratio = self.population_config.get(
            "internal_vs_external_ratio"
        )

        if not isinstance(ratio, dict):
            raise ValueError(
                "internal_vs_external_ratio is missing."
            )

        internal_ratio = ratio.get("internal")
        external_ratio = ratio.get("external")

        if not isinstance(
            internal_ratio,
            (int, float)
        ):
            raise ValueError(
                "internal_vs_external_ratio.internal must be numeric."
            )

        if not isinstance(
            external_ratio,
            (int, float)
        ):
            raise ValueError(
                "internal_vs_external_ratio.external must be numeric."
            )

        if internal_ratio < 0 or external_ratio < 0:
            raise ValueError(
                "Internal/external ratios cannot be negative."
            )

        ratio_total = (
            internal_ratio +
            external_ratio
        )

        if ratio_total <= 0:
            raise ValueError(
                "Internal/external ratios must contain a positive total."
            )

        internal_ratio /= ratio_total
        external_ratio /= ratio_total

        external_count = round(
            total_users * external_ratio
        )

        internal_count = (
            total_users - external_count
        )

        return (
            internal_count,
            external_count,
        )

    # ------------------------------------------------------------------
    # User ID generation
    # ------------------------------------------------------------------

    def _generate_user_id(
        self,
        external: bool,
    ) -> str:

        prefix = (
            f"{self._environment_id()}_"
            f"{'ext' if external else 'usr'}"
        )

        while True:

            identifier = (
                f"{prefix}_"
                f"{uuid.uuid4().hex[:8]}"
            )

            if identifier not in self.used_user_ids:

                self.used_user_ids.add(
                    identifier
                )

                return identifier

    def _environment_id(self) -> str:
        """
        Use environment_id when supplied by run resolution.
        Otherwise use the canonical scenario.
        """

        environment_id = self.config.get(
            "environment_id"
        )

        if environment_id:
            return str(environment_id)

        return self.scenario

    # ------------------------------------------------------------------
    # Phone / SIP
    # ------------------------------------------------------------------

    def _generate_internal_extension(self) -> str:
        """
        Generate a unique 4-digit internal extension.

        Source strategy:
            1000-9999
        """

        while True:

            extension = str(
                random.randint(
                    1000,
                    9999
                )
            )

            if extension not in self.used_extensions:

                self.used_extensions.add(
                    extension
                )

                return extension

    def _generate_external_phone(self) -> str:
        """
        Generate the configured synthetic E.164-like external number.

        Source strategy:
            +1-555-{7 random digits}
        """

        return (
            "+1-555-"
            f"{random.randint(0, 9_999_999):07d}"
        )

    def _internal_domain(self) -> str:
        """
        Source strategy:
            {environment_id}.example.org
        """

        return (
            f"{self._environment_id()}.example.org"
        )

    # ------------------------------------------------------------------
    # IP allocation
    # ------------------------------------------------------------------

    def _find_network_segment_for_internal_user(
        self,
        department_id: str | None,
        canonical_role: str | None,
        org_role_id: str | None,
    ) -> str | None:
        """
        Find the configured network segment applicable to an internal user.

        Enterprise uses:
            department_ids

        Customer Support uses:
            applies_to
        """

        segments = self.network_config.get(
            "network_segments",
            []
        )

        for segment in segments:

            if not isinstance(segment, dict):
                continue

            cidr = segment.get("cidr")

            if not cidr:
                continue

            department_ids = segment.get(
                "department_ids",
                []
            )

            if department_id in department_ids:
                return str(cidr)

            applies_to = segment.get(
                "applies_to",
                []
            )

            role_values = {
                str(canonical_role)
                if canonical_role
                else None,
                str(org_role_id)
                if org_role_id
                else None,
            }

            if role_values.intersection(
                str(value)
                for value in applies_to
            ):
                return str(cidr)

        return None

    def _allocate_internal_ip(
        self,
        department_id: str | None,
        canonical_role: str | None,
        org_role_id: str | None,
    ) -> str:

        cidr = (
            self._find_network_segment_for_internal_user(
                department_id,
                canonical_role,
                org_role_id,
            )
        )

        if cidr is None:

            ranges = self.network_config.get(
                "internal_ip_ranges",
                []
            )

            if not ranges:
                raise ValueError(
                    "No internal network range is configured."
                )

            cidr = random.choice(
                ranges
            )

        network = ipaddress.ip_network(
            cidr,
            strict=False,
        )

        if network.version != 4:
            raise ValueError(
                f"Only IPv4 networks are supported: {cidr}"
            )

        # The generator needs to handle large populations safely.
        hosts = list(network.hosts())

        if not hosts:
            raise ValueError(
                f"No usable host addresses in network: {cidr}"
            )

        random.shuffle(hosts)

        for host in hosts:

            address = str(host)

            if address not in self.used_internal_ips:

                self.used_internal_ips.add(
                    address
                )

                return address

        # The configured department/role segment is full.
        # Fall back to the environment-level internal IP ranges.
        fallback_ranges = self.network_config.get(
            "internal_ip_ranges",
            []
        )

        if not fallback_ranges:
            raise RuntimeError(
                f"No unused IP addresses remain in configured "
                f"network segment {cidr}, and no fallback internal "
                f"IP ranges are configured."
            )

        fallback_networks = []

        for fallback_cidr in fallback_ranges:
            fallback_network = ipaddress.ip_network(
                fallback_cidr,
                strict=False,
            )

            if fallback_network.version != 4:
                continue

            fallback_networks.append(
                fallback_network
            )

        for fallback_network in fallback_networks:

            hosts = list(
                fallback_network.hosts()
            )

            random.shuffle(hosts)

            for host in hosts:

                address = str(host)

                if address not in self.used_internal_ips:

                    self.used_internal_ips.add(
                        address
                    )

                    return address

        raise RuntimeError(
            "No unused internal IP addresses remain in any "
            "configured internal network range."
        )

    def _generate_external_ip(self) -> str:
        """
        user_population_characeristics.json explicitly specifies:

            203.0.113.0/24

        for synthetic external endpoints.
        """

        network = ipaddress.ip_network(
            "203.0.113.0/24"
        )

        hosts = list(network.hosts())

        return str(
            random.choice(hosts)
        )

    # ------------------------------------------------------------------
    # Activity / behaviour
    # ------------------------------------------------------------------

    def _activity_level(self) -> str:

        distribution = self.population_config.get(
            "communication_activity_level_distribution"
        )

        self._validate_distribution(
            distribution,
            "communication_activity_level_distribution",
        )

        return self._weighted_choice(
            distribution
        )

    def _behaviour_profile(self) -> str:

        distribution = self.population_config.get(
            "communication_behaviour_profile_distribution"
        )

        self._validate_distribution(
            distribution,
            "communication_behaviour_profile_distribution",
        )

        return self._weighted_choice(
            distribution
        )

    def _preferred_active_days(self) -> str:

        distribution = self.population_config.get(
            "preferred_active_days_distribution"
        )

        self._validate_distribution(
            distribution,
            "preferred_active_days_distribution",
        )

        return self._weighted_choice(
            distribution
        )

    def _active_hours_label(self) -> str:

        distribution = self.population_config.get(
            "active_hours_distribution"
        )

        self._validate_distribution(
            distribution,
            "active_hours_distribution",
        )

        return self._weighted_choice(
            distribution
        )

    # ------------------------------------------------------------------
    # Active hours
    # ------------------------------------------------------------------

    def _build_active_hours(
        self,
        label: str,
    ) -> dict[str, str] | None:
        """
        Convert configured shift information into the user_schema
        active_hours object.

        Customer Support advanced configuration explicitly defines
        Morning/Afternoon/Night hours.

        Enterprise's early_shift/late_shift labels do not have explicit
        start/end values anywhere in the supplied ZIP, so this method
        does not invent times for them.
        """

        if self.scenario == "customer_support_center":

            shifts = self.behavior_overrides.get(
                "shifts",
                {}
            )

            lookup = {
                "morning_shift": "Morning",
                "afternoon_shift": "Afternoon",
                "night_shift": "Night",
            }

            shift_name = lookup.get(
                label
            )

            if shift_name is not None:

                shift = shifts.get(
                    shift_name
                )

                if isinstance(shift, dict):

                    start_hour = shift.get(
                        "start_hour"
                    )

                    end_hour = shift.get(
                        "end_hour"
                    )

                    if (
                        isinstance(
                            start_hour,
                            int
                        )
                        and isinstance(
                            end_hour,
                            int
                        )
                    ):

                        return {
                            "start": (
                                f"{start_hour:02d}:00"
                            ),
                            "end": (
                                f"{end_hour:02d}:00"
                            ),
                            "shift_label": shift_name,
                        }

            return None

        # Enterprise only supplies labels:
        #
        # standard_business
        # early_shift
        # late_shift
        #
        # but the ZIP does not specify clock times for the latter two.
        #
        # Therefore do not invent a time range.
        if label == "standard_business":
            return {
                "start": "09:00",
                "end": "17:00",
                "shift_label": label,
            }

        return None

    # ------------------------------------------------------------------
    # Preferred categories
    # ------------------------------------------------------------------

    def _preferred_categories(
        self,
        canonical_role: str,
    ) -> list[str]:

        category_bias = self.population_config.get(
            "preferred_category_bias",
            {}
        )

        categories = category_bias.get(
            canonical_role
        )

        if categories is None:

            categories = category_bias.get(
                "manager"
                if canonical_role
                in {
                    "support_manager",
                    "manager",
                }
                else "employee"
            )

        if not categories:

            # customer is explicitly present in the supplied configuration,
            # but this fallback protects against a future missing role.
            categories = [
                "business_communication"
            ]

        return list(categories)

    # ------------------------------------------------------------------
    # Communication preference
    # ------------------------------------------------------------------

    def _internal_external_preference(
        self,
        canonical_role: str,
    ) -> float:

        distribution = (
            self.population_config.get(
                "internal_external_comm_preference",
                {}
            )
        )

        value = distribution.get(
            canonical_role
        )

        if value is None:

            # Customer Support configuration uses
            # support_manager instead of manager.
            if canonical_role == "support_manager":
                value = distribution.get(
                    "support_manager",
                    0.0
                )

            else:
                value = 0.0

        value = float(value)

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "internal_external_comm_preference values "
                "must be between 0 and 1."
            )

        return value

    # ------------------------------------------------------------------
    # Role mapping
    # ------------------------------------------------------------------

    def _enterprise_roles(
        self,
        internal_count: int,
    ) -> list[dict[str, Any]]:
        """
        Generate the Enterprise hierarchy defined by the advanced
        configuration.

        Advanced configuration specifies:
            - 8 departments
            - Executive department
            - CEO
            - Manager
            - Employee
            - employees_per_manager target

        Therefore:
            1 CEO
            8 managers
            remaining internal users -> employees

        Department sizes from the base configuration are used as weights
        when distributing employees across departments.
        """

        advanced_org = self.behavior_overrides.get(
            "organization",
            {}
        )

        departments = advanced_org.get(
            "departments",
            []
        )

        if not departments:
            raise ValueError(
                "Enterprise advanced configuration does not contain "
                "organization.departments."
            )

        if internal_count < (
            1 + len(departments)
        ):
            raise ValueError(
                "Enterprise population is too small to create "
                "the configured CEO and one manager per department."
            )

        role_labels = self.behavior_overrides.get(
            "role_labels",
            {}
        )

        ceo_role = role_labels.get(
            "ceo",
            "executive"
        )

        manager_role = role_labels.get(
            "manager",
            "manager"
        )

        employee_role = role_labels.get(
            "employee",
            "employee"
        )

        roles = []

        # --------------------------------------------------------------
        # CEO
        # --------------------------------------------------------------

        roles.append(
            {
                "org_role_id": "ceo",
                "user_role": ceo_role,
                "department": "exec",
                "department_name": "Executive",
                "is_manager": True,
            }
        )

        # --------------------------------------------------------------
        # One manager per advanced-config department
        # --------------------------------------------------------------

        for department_name in departments:

            department_id = (
                self._match_department_id(
                    department_name
                )
            )

            roles.append(
                {
                    "org_role_id": "manager",
                    "user_role": manager_role,
                    "department": department_id,
                    "department_name": department_name,
                    "is_manager": True,
                }
            )

        # --------------------------------------------------------------
        # Remaining internal users are employees.
        # --------------------------------------------------------------

        employee_count = (
            internal_count
            - len(roles)
        )

        base_departments = self.organization.get(
            "departments",
            []
        )

        if not base_departments:
            raise ValueError(
                "Enterprise organizational_structure.departments "
                "is missing."
            )

        department_weights = [
            float(
                department.get(
                    "size",
                    1
                )
            )
            for department in base_departments
        ]

        employee_departments = random.choices(
            base_departments,
            weights=department_weights,
            k=employee_count,
        )

        for department in employee_departments:

            roles.append(
                {
                    "org_role_id": "employee",
                    "user_role": employee_role,
                    "department": department["id"],
                    "department_name": department["name"],
                    "is_manager": False,
                }
            )

        return roles

    def _customer_support_roles(
        self,
        internal_count: int,
    ) -> list[dict[str, Any]]:
        """
        Generate the exact role structure defined by the Customer Support
        advanced configuration.

        Advanced configuration:
            manager_count = 1
            team_lead_count = 4
            remaining internal users = agents
        """

        advanced_org = self.behavior_overrides.get(
            "organization",
            {}
        )

        manager_count = int(
            advanced_org.get(
                "manager_count",
                0
            )
        )

        team_lead_count = int(
            advanced_org.get(
                "team_lead_count",
                0
            )
        )

        minimum_internal = (
            manager_count
            + team_lead_count
        )

        if internal_count < minimum_internal:
            raise ValueError(
                "Customer Support internal population is too small "
                "for the configured manager/team-lead counts."
            )

        role_labels = self.behavior_overrides.get(
            "role_labels",
            {}
        )

        manager_role = role_labels.get(
            "manager",
            "support_manager"
        )

        team_lead_role = role_labels.get(
            "team_lead",
            "team_lead"
        )

        agent_role = role_labels.get(
            "agent",
            "customer_support_agent"
        )

        roles = []

        for _ in range(manager_count):

            roles.append(
                {
                    "org_role_id": "support_manager",
                    "user_role": manager_role,
                    "department": None,
                    "department_name": None,
                    "is_manager": True,
                }
            )

        for _ in range(team_lead_count):

            roles.append(
                {
                    "org_role_id": "team_lead",
                    "user_role": team_lead_role,
                    "department": None,
                    "department_name": None,
                    "is_manager": False,
                }
            )

        remaining_agents = (
            internal_count
            - manager_count
            - team_lead_count
        )

        for _ in range(remaining_agents):

            roles.append(
                {
                    "org_role_id": "agent",
                    "user_role": agent_role,
                    "department": None,
                    "department_name": None,
                    "is_manager": False,
                }
            )

        return roles

    # ------------------------------------------------------------------
    # Department lookup
    # ------------------------------------------------------------------

    def _match_department_id(
        self,
        department_name: str,
    ) -> str:

        departments = self.organization.get(
            "departments",
            []
        )

        target = str(
            department_name
        ).strip().lower()

        for department in departments:

            if not isinstance(
                department,
                dict
            ):
                continue

            department_id = str(
                department.get(
                    "id",
                    ""
                )
            )

            name = str(
                department.get(
                    "name",
                    ""
                )
            )

            if (
                department_id.lower()
                == target
                or name.lower()
                == target
            ):
                return department_id

        # Enterprise advanced configuration contains "Support" and
        # "Marketing", while the base environment does not contain
        # those exact departments. Preserve the advanced department
        # as a generated department identifier instead of silently
        # mapping it to another department.
        return department_name.lower().replace(
            " ",
            "_"
        )

    # ------------------------------------------------------------------
    # Shift assignment
    # ------------------------------------------------------------------

    def _assign_support_shift(
        self,
    ) -> dict[str, Any] | None:

        shifts = self.behavior_overrides.get(
            "shifts"
        )

        if not isinstance(
            shifts,
            dict
        ):
            return None

        usable = {}

        for name, definition in shifts.items():

            if not isinstance(
                definition,
                dict
            ):
                continue

            if (
                "start_hour" not in definition
                or "end_hour" not in definition
            ):
                continue

            weight = float(
                definition.get(
                    "weight",
                    0
                )
            )

            if weight > 0:
                usable[name] = weight

        if not usable:
            return None

        shift_name = self._weighted_choice(
            usable
        )

        definition = shifts[
            shift_name
        ]

        start_hour = int(
            definition["start_hour"]
        )

        end_hour = int(
            definition["end_hour"]
        )

        return {
            "name": shift_name,
            "start": (
                f"{start_hour:02d}:00"
            ),
            "end": (
                f"{end_hour:02d}:00"
            ),
        }

    # ------------------------------------------------------------------
    # User creation
    # ------------------------------------------------------------------

    def _create_internal_user(
        self,
        role_info: dict[str, Any],
        active: bool,
    ) -> dict[str, Any]:

        user_id = self._generate_user_id(
            external=False
        )

        org_role_id = role_info[
            "org_role_id"
        ]

        canonical_role = role_info[
            "user_role"
        ]

        department_id = role_info.get(
            "department"
        )

        department_name = role_info.get(
            "department_name"
        )

        ip_address = (
            self._allocate_internal_ip(
                department_id,
                canonical_role,
                org_role_id,
            )
        )

        extension = (
            self._generate_internal_extension()
        )

        domain = self._internal_domain()

        active_hours_label = (
            self._active_hours_label()
        )

        active_hours = (
            self._build_active_hours(
                active_hours_label
            )
        )

        # Customer Support's advanced shift configuration is the
        # authoritative source for its staffing shifts.
        if (
            self.scenario
            == "customer_support_center"
            and canonical_role
            in {
                "customer_support_agent",
                "team_lead",
                "support_manager",
            }
        ):
            support_shift = (
                self._assign_support_shift()
            )

            if support_shift is not None:
                active_hours = {
                    "start": support_shift["start"],
                    "end": support_shift["end"],
                    "shift_label": support_shift["name"],
                }

        user = {
            "user_id": user_id,
            "user_type": "internal",
            "phone_number": extension,
            "sip_identifier": (
                f"sip:{user_id}@{domain}"
            ),
            "ip_address": ip_address,
            "department_group": department_id,
            "organization_domain": domain,
            "communication_activity_level": (
                self._activity_level()
            ),
            "preferred_communication_categories": (
                self._preferred_categories(
                    canonical_role
                )
            ),
            "has_frequent_contacts": False,
            "frequent_contacts": [],
            "preferred_active_days": (
                self._preferred_active_days()
            ),
            "user_role": canonical_role,
            "org_role_id": org_role_id,
            "communication_behaviour_profile": (
                self._behaviour_profile()
            ),
            "community_id": (
                department_id
                if department_id is not None
                else domain
            ),
            "internal_external_comm_preference": (
                self._internal_external_preference(
                    canonical_role
                )
            ),
            "environment": self._environment_id(),
            "is_active": active,
            "call_weight": (
                1.0
                if active
                else (
                    0.1
                    if self.communication_scale.get(
                        "inactive_user_behavior"
                    )
                    == "minimal_calls"
                    else 0.0
                )
            ),
        }

        # user_schema requires active_hours only when present in the
        # generated object. Enterprise early_shift/late_shift have no
        # clock definitions in the supplied ZIP, so they are omitted
        # rather than inventing unsupported values.
        if active_hours is not None:
            user["active_hours"] = active_hours

        # Department name is useful for traceability, but only add it
        # when the scenario actually supplied one.
        if department_name is not None:
            user["department_name"] = department_name

        return user

    def _create_external_user(self) -> dict[str, Any]:

        user_id = self._generate_user_id(
            external=True
        )

        external_domains = (
            self.population_config.get(
                "external_domains"
            )
        )

        if not external_domains:
            raise ValueError(
                "external_domains is missing from "
                "user population configuration."
            )

        domain = random.choice(
            external_domains
        )

        external_softphone_ratio = float(
            self.population_config.get(
                "external_softphone_ratio",
                0.0
            )
        )

        is_softphone = (
            random.random()
            < external_softphone_ratio
        )

        phone_number = (
            self._generate_external_phone()
        )

        sip_identifier = (
            f"sip:{user_id}@{domain}"
            if is_softphone
            else None
        )

        external_role = (
            self.population_config.get(
                "default_external_role",
                "customer"
            )
        )

        user = {
            "user_id": user_id,
            "user_type": "external",
            "phone_number": phone_number,
            "sip_identifier": sip_identifier,
            "ip_address": (
                self._generate_external_ip()
            ),
            "department_group": None,
            "organization_domain": domain,
            "communication_activity_level": (
                self._activity_level()
            ),
            "preferred_communication_categories": (
                self._preferred_categories(
                    external_role
                )
            ),
            "has_frequent_contacts": False,
            "frequent_contacts": [],
            "preferred_active_days": (
                self._preferred_active_days()
            ),
            "user_role": external_role,
            "org_role_id": None,
            "communication_behaviour_profile": (
                self._behaviour_profile()
            ),
            "community_id": domain,
            "internal_external_comm_preference": 1.0,
            "environment": self._environment_id(),
            "is_active": True,
            "call_weight": 1.0,
        }

        return user

    # ------------------------------------------------------------------
    # Active user percentage
    # ------------------------------------------------------------------

    def _generate_internal_activity_flags(
        self,
        internal_count: int,
    ) -> list[bool]:

        percentage = self.communication_scale.get(
            "active_user_percentage"
        )

        if not isinstance(
            percentage,
            (int, float)
        ):
            raise ValueError(
                "communication_scale.active_user_percentage "
                "must be numeric."
            )

        if not 0 <= percentage <= 1:
            raise ValueError(
                "active_user_percentage must be between 0 and 1."
            )

        active_count = round(
            internal_count * percentage
        )

        flags = (
            [True] * active_count
            + [False] * (
                internal_count
                - active_count
            )
        )

        random.shuffle(
            flags
        )

        return flags

    # ------------------------------------------------------------------
    # Frequent contacts
    # ------------------------------------------------------------------

    def _assign_frequent_contacts(
        self,
        users: list[dict[str, Any]],
    ) -> None:
        """
        Assign frequent contacts using the configured prevalence and
        contact-count range.

        Contacts are selected from the same community first, matching
        the community membership strategy supplied in the ZIP.
        """

        percentage = float(
            self.population_config.get(
                "percentage_with_frequent_contacts",
                0.0
            )
        )

        contact_range = (
            self.population_config.get(
                "average_frequent_contacts_per_user",
                {}
            )
        )

        minimum = int(
            contact_range.get(
                "min",
                0
            )
        )

        maximum = int(
            contact_range.get(
                "max",
                0
            )
        )

        if minimum < 0 or maximum < 0:
            raise ValueError(
                "Frequent contact limits cannot be negative."
            )

        if maximum < minimum:
            raise ValueError(
                "Frequent contact maximum cannot be less than minimum."
            )

        users_by_community = defaultdict(list)

        for user in users:

            users_by_community[
                user["community_id"]
            ].append(user)

        for user in users:

            if random.random() >= percentage:
                continue

            if maximum == 0:
                continue

            target_count = random.randint(
                minimum,
                maximum
            )

            same_community = [
                candidate
                for candidate
                in users_by_community[
                    user["community_id"]
                ]
                if candidate["user_id"]
                != user["user_id"]
            ]

            random.shuffle(
                same_community
            )

            selected = same_community[
                :target_count
            ]

            # If the community does not contain enough users,
            # use the remaining population.
            if len(selected) < target_count:

                selected_ids = {
                    candidate["user_id"]
                    for candidate in selected
                }

                remaining = [
                    candidate
                    for candidate in users
                    if (
                        candidate["user_id"]
                        != user["user_id"]
                        and candidate["user_id"]
                        not in selected_ids
                    )
                ]

                random.shuffle(
                    remaining
                )

                selected.extend(
                    remaining[
                        :target_count
                        - len(selected)
                    ]
                )

            user["frequent_contacts"] = [
                candidate["user_id"]
                for candidate in selected
            ]

            user["has_frequent_contacts"] = bool(
                user["frequent_contacts"]
            )

    # ------------------------------------------------------------------
    # Public generation API
    # ------------------------------------------------------------------

    def generate(self) -> list[dict[str, Any]]:
        """
        Generate the complete user population.
        """

        total_users = (
            self._get_total_users()
        )

        (
            internal_count,
            external_count,
        ) = self._get_internal_external_counts(
            total_users
        )

        # --------------------------------------------------------------
        # Build role roster
        # --------------------------------------------------------------

        if self.scenario == "enterprise":

            internal_roles = (
                self._enterprise_roles(
                    internal_count
                )
            )

        else:

            internal_roles = (
                self._customer_support_roles(
                    internal_count
                )
            )

        if len(internal_roles) != internal_count:
            raise RuntimeError(
                "Internal role roster size does not match "
                "the configured internal population."
            )

        active_flags = (
            self._generate_internal_activity_flags(
                internal_count
            )
        )

        users = []

        # --------------------------------------------------------------
        # Internal users
        # --------------------------------------------------------------

        for role_info, active in zip(
            internal_roles,
            active_flags,
        ):

            users.append(
                self._create_internal_user(
                    role_info,
                    active,
                )
            )

        # --------------------------------------------------------------
        # External users
        # --------------------------------------------------------------

        for _ in range(
            external_count
        ):

            users.append(
                self._create_external_user()
            )

        # --------------------------------------------------------------
        # Frequent contacts
        # --------------------------------------------------------------

        self._assign_frequent_contacts(
            users
        )

        # --------------------------------------------------------------
        # Final validation
        # --------------------------------------------------------------

        self._validate_generated_users(
            users,
            total_users,
            internal_count,
            external_count,
        )

        return users

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_generated_users(
        self,
        users: list[dict[str, Any]],
        total_users: int,
        internal_count: int,
        external_count: int,
    ) -> None:

        if len(users) != total_users:
            raise RuntimeError(
                f"Generated {len(users)} users but expected "
                f"{total_users}."
            )

        internal_users = [
            user
            for user in users
            if user["user_type"] == "internal"
        ]

        external_users = [
            user
            for user in users
            if user["user_type"] == "external"
        ]

        if len(internal_users) != internal_count:
            raise RuntimeError(
                "Internal user count mismatch."
            )

        if len(external_users) != external_count:
            raise RuntimeError(
                "External user count mismatch."
            )

        user_ids = [
            user["user_id"]
            for user in users
        ]

        if len(user_ids) != len(set(user_ids)):
            raise RuntimeError(
                "Duplicate user_id values generated."
            )

        internal_extensions = [
            user["phone_number"]
            for user in internal_users
        ]

        if len(internal_extensions) != len(
            set(internal_extensions)
        ):
            raise RuntimeError(
                "Duplicate internal extensions generated."
            )

        for user in users:

            required_fields = {
                "user_id",
                "user_type",
                "organization_domain",
                "user_role",
                "communication_activity_level",
                "communication_behaviour_profile",
                "preferred_communication_categories",
                "preferred_active_days",
                "has_frequent_contacts",
                "frequent_contacts",
                "environment",
            }

            missing = (
                required_fields
                - user.keys()
            )

            if missing:
                raise RuntimeError(
                    f"Generated user {user['user_id']} "
                    f"is missing fields: {sorted(missing)}"
                )

            if (
                user["has_frequent_contacts"]
                and not user["frequent_contacts"]
            ):
                raise RuntimeError(
                    f"User {user['user_id']} is marked as having "
                    "frequent contacts but the list is empty."
                )

            if (
                not user["has_frequent_contacts"]
                and user["frequent_contacts"]
            ):
                raise RuntimeError(
                    f"User {user['user_id']} has frequent contacts "
                    "but has_frequent_contacts is false."
                )


# ----------------------------------------------------------------------
# Convenience function
# ----------------------------------------------------------------------

def generate_users(
    resolved_config: dict[str, Any],
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """
    Convenience wrapper around UserGenerator.
    """

    generator = UserGenerator(
        resolved_config,
        seed=seed,
    )

    return generator.generate()


# ----------------------------------------------------------------------
# Standalone test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    from pathlib import Path

    from config_resolver import ConfigResolver

    PROJECT_ROOT = (
        Path(__file__).resolve().parent.parent
    )

    resolver = ConfigResolver(
        PROJECT_ROOT
    )

    for scenario in (
        "enterprise",
        "customer_support_center",
    ):

        print("=" * 70)
        print(
            f"Testing user generation: {scenario}"
        )
        print("=" * 70)

        resolved = resolver.resolve_scenario(
            scenario,
            include_advanced=True,
        )

        users = generate_users(
            resolved,
            seed=42,
        )

        print(
            f"Total users: {len(users)}"
        )

        internal = [
            user
            for user in users
            if user["user_type"] == "internal"
        ]

        external = [
            user
            for user in users
            if user["user_type"] == "external"
        ]

        print(
            f"Internal users: {len(internal)}"
        )

        print(
            f"External users: {len(external)}"
        )

        role_counts = defaultdict(int)

        for user in users:
            role_counts[
                user["user_role"]
            ] += 1

        print("\nRole distribution:")

        for role, count in sorted(
            role_counts.items()
        ):
            print(
                f"  {role}: {count}"
            )

        print("\nFirst user:")

        print(users[0])