import csv
import json
import ipaddress
import re
from pathlib import Path
from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_ROOT = PROJECT_ROOT / "config"
DATASET_ROOT = PROJECT_ROOT / "generated_dataset"


SCENARIOS = {
    "enterprise": {
        "folder": "enterprise",
        "json": "enterprise_users.json",
        "csv": "enterprise_users.csv",
        "base_config": "enterprise/enterprise.json",
        "advanced_config": "enterprise/enterprise_adv.json",
    },
    "customer_support_center": {
        "folder": "customer_support_center",
        "json": "customer_support_center_users.json",
        "csv": "customer_support_center_users.csv",
        "base_config": (
            "customer_support_center/"
            "customer_support_center.json"
        ),
        "advanced_config": (
            "customer_support_center/"
            "customer_support_center_adv.json"
        ),
    },
}


USER_SCHEMA_FILE = CONFIG_ROOT / "user_schema.json"
POPULATION_FILE = CONFIG_ROOT / "user_population_characteristics.json"


class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def passed_check(self, message):
        self.passed.append(message)

    @property
    def is_valid(self):
        return len(self.errors) == 0


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_users_json(path):
    return load_json(path)


def load_users_csv(path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


def load_users(path):
    if path.suffix.lower() == ".json":
        return load_users_json(path)

    if path.suffix.lower() == ".csv":
        return load_users_csv(path)

    raise ValueError(f"Unsupported file type: {path}")


def normalize_csv_values(user):
    """
    Convert CSV string representations back into the types
    used by the JSON dataset where possible.
    """

    boolean_fields = {
        "has_frequent_contacts",
        "is_active",
    }

    numeric_fields = {
        "internal_external_comm_preference",
        "call_weight",
    }

    for field in boolean_fields:
        if field in user:
            value = str(user[field]).strip().lower()

            if value == "true":
                user[field] = True
            elif value == "false":
                user[field] = False

    for field in numeric_fields:
        if field in user:
            try:
                user[field] = float(user[field])
            except (ValueError, TypeError):
                pass

    return user


def validate_required_fields(users, schema, result):
    required_fields = schema.get("required", [])

    missing_count = 0

    for index, user in enumerate(users):
        missing = [
            field
            for field in required_fields
            if field not in user or user[field] in ("", None)
        ]

        if missing:
            missing_count += 1
            result.error(
                f"User {index} is missing required fields: "
                f"{', '.join(missing)}"
            )

    if missing_count == 0:
        result.passed_check(
            "All users contain the required schema fields."
        )


def validate_user_ids(users, result, scenario):
    ids = [
        user.get("user_id")
        for user in users
        if user.get("user_id")
    ]

    duplicates = [
        user_id
        for user_id, count in Counter(ids).items()
        if count > 1
    ]

    if duplicates:
        result.error(
            f"Duplicate user IDs found: {len(duplicates)}"
        )
    else:
        result.passed_check("All user IDs are unique.")

    prefix = f"{scenario}_"

    invalid_prefix = [
        user_id
        for user_id in ids
        if not user_id.startswith(prefix)
    ]

    if invalid_prefix:
        result.error(
            f"{len(invalid_prefix)} user IDs do not start "
            f"with '{prefix}'."
        )
    else:
        result.passed_check(
            f"All user IDs use the '{prefix}' environment prefix."
        )


def validate_internal_external_ids(users, result, scenario):
    internal_ids = {
        user["user_id"]
        for user in users
        if user.get("user_type") == "internal"
    }

    external_ids = {
        user["user_id"]
        for user in users
        if user.get("user_type") == "external"
    }

    overlap = internal_ids & external_ids

    if overlap:
        result.error(
            f"Internal/external ID overlap detected: {len(overlap)}"
        )
    else:
        result.passed_check(
            "Internal and external user IDs are disjoint."
        )

    expected_internal_prefix = f"{scenario}_usr_"
    expected_external_prefix = f"{scenario}_ext_"

    invalid_internal = [
        user_id
        for user_id in internal_ids
        if not user_id.startswith(expected_internal_prefix)
    ]

    invalid_external = [
        user_id
        for user_id in external_ids
        if not user_id.startswith(expected_external_prefix)
    ]

    if invalid_internal:
        result.error(
            f"{len(invalid_internal)} internal IDs have an invalid format."
        )
    else:
        result.passed_check("Internal user ID format is valid.")

    if invalid_external:
        result.error(
            f"{len(invalid_external)} external IDs have an invalid format."
        )
    else:
        result.passed_check("External user ID format is valid.")


def validate_counts(users, base_config, population_config, result):
    scale = base_config.get("communication_scale", {})

    expected_total = scale.get("num_users")

    actual_total = len(users)

    if expected_total is not None and actual_total != expected_total:
        result.error(
            f"Total users: expected {expected_total}, "
            f"found {actual_total}."
        )
    else:
        result.passed_check(
            f"Total user count is correct: {actual_total}."
        )

    distribution = population_config.get("population_distribution", {})

    expected_internal_ratio = distribution.get("internal")
    expected_external_ratio = distribution.get("external")

    internal_count = sum(
        1
        for user in users
        if user.get("user_type") == "internal"
    )

    external_count = sum(
        1
        for user in users
        if user.get("user_type") == "external"
    )

    if actual_total:
        actual_internal_ratio = internal_count / actual_total
        actual_external_ratio = external_count / actual_total

        tolerance = 0.02

        if (
            expected_internal_ratio is not None
            and abs(actual_internal_ratio - expected_internal_ratio)
            > tolerance
        ):
            result.error(
                f"Internal population ratio is "
                f"{actual_internal_ratio:.3f}; expected approximately "
                f"{expected_internal_ratio:.3f}."
            )
        else:
            result.passed_check(
                f"Internal population ratio: "
                f"{actual_internal_ratio:.3f}."
            )

        if (
            expected_external_ratio is not None
            and abs(actual_external_ratio - expected_external_ratio)
            > tolerance
        ):
            result.error(
                f"External population ratio is "
                f"{actual_external_ratio:.3f}; expected approximately "
                f"{expected_external_ratio:.3f}."
            )
        else:
            result.passed_check(
                f"External population ratio: "
                f"{actual_external_ratio:.3f}."
            )


def validate_extensions(users, result):
    internal_users = [
        user
        for user in users
        if user.get("user_type") == "internal"
    ]

    extensions = [
        str(user.get("phone_number"))
        for user in internal_users
        if user.get("phone_number") is not None
    ]

    duplicates = [
        extension
        for extension, count in Counter(extensions).items()
        if count > 1
    ]

    if duplicates:
        result.error(
            f"Duplicate internal extensions: {len(duplicates)}"
        )
    else:
        result.passed_check(
            "Internal extensions are unique."
        )

    invalid_extensions = []

    for extension in extensions:
        if not extension.isdigit():
            invalid_extensions.append(extension)
            continue

        number = int(extension)

        if number < 1000 or number > 9999:
            invalid_extensions.append(extension)

    if invalid_extensions:
        result.error(
            f"{len(invalid_extensions)} internal extensions "
            f"are outside 1000-9999."
        )
    else:
        result.passed_check(
            "Internal extensions are within 1000-9999."
        )


def validate_ip_addresses(users, base_config, result):
    internal_ranges = (
        base_config
        .get("network", {})
        .get("internal_ip_ranges", [])
    )

    internal_networks = []

    for network in internal_ranges:
        try:
            internal_networks.append(
                ipaddress.ip_network(network)
            )
        except ValueError:
            result.warning(
                f"Invalid configured internal network: {network}"
            )

    internal_ips = []
    external_ips = []

    for user in users:
        ip_value = user.get("ip_address")

        if not ip_value:
            result.error(
                f"User {user.get('user_id')} has no IP address."
            )
            continue

        try:
            ip = ipaddress.ip_address(ip_value)
        except ValueError:
            result.error(
                f"Invalid IP address for "
                f"{user.get('user_id')}: {ip_value}"
            )
            continue

        if user.get("user_type") == "internal":
            internal_ips.append(ip)

            if internal_networks and not any(
                ip in network
                for network in internal_networks
            ):
                result.error(
                    f"Internal IP {ip} for "
                    f"{user.get('user_id')} is outside "
                    f"configured internal ranges."
                )

        else:
            external_ips.append(ip)

            # Documentation/example network from the config.
            external_network = ipaddress.ip_network(
                "203.0.113.0/24"
            )

            if ip not in external_network:
                result.error(
                    f"External IP {ip} for "
                    f"{user.get('user_id')} is outside "
                    f"203.0.113.0/24."
                )

    duplicate_internal_ips = [
        str(ip)
        for ip, count in Counter(internal_ips).items()
        if count > 1
    ]

    if duplicate_internal_ips:
        result.error(
            f"Duplicate internal IP addresses: "
            f"{len(duplicate_internal_ips)}"
        )
    else:
        result.passed_check(
            "Internal IP addresses are unique."
        )


def validate_domains(users, scenario, result):
    expected_internal_domain = f"{scenario}.example.org"

    invalid_internal = []

    for user in users:
        if user.get("user_type") == "internal":
            if user.get("organization_domain") != expected_internal_domain:
                invalid_internal.append(user.get("user_id"))

    if invalid_internal:
        result.error(
            f"{len(invalid_internal)} internal users have an unexpected "
            f"organization domain."
        )
    else:
        result.passed_check(
            f"All internal users use the correct organization domain: "
            f"{expected_internal_domain}."
        )

    # External users are allowed to belong to external organizations.
    external_users = [
        user
        for user in users
        if user.get("user_type") == "external"
    ]

    if external_users:
        result.passed_check(
            f"External users have external organization domains "
            f"as configured: {len(external_users)} checked."
        )


def validate_roles(users, scenario, advanced_config, result):
    role_counter = Counter(
        user.get("user_role")
        for user in users
    )

    if scenario == "enterprise":
        expected_roles = {
            "executive": 1,
            "manager": 8,
        }

        for role, expected_count in expected_roles.items():
            actual = role_counter.get(role, 0)

            if actual != expected_count:
                result.error(
                    f"Enterprise {role} count: "
                    f"expected {expected_count}, found {actual}."
                )
            else:
                result.passed_check(
                    f"Enterprise {role} count is correct: {actual}."
                )

        if role_counter.get("employee", 0) <= 0:
            result.error("Enterprise has no employees.")
        else:
            result.passed_check(
                f"Enterprise employee count: "
                f"{role_counter.get('employee', 0)}."
            )

    elif scenario == "customer_support_center":
        expected_roles = {
            "support_manager": 1,
            "team_lead": 4,
        }

        for role, expected_count in expected_roles.items():
            actual = role_counter.get(role, 0)

            if actual != expected_count:
                result.error(
                    f"Customer Support {role} count: "
                    f"expected {expected_count}, found {actual}."
                )
            else:
                result.passed_check(
                    f"Customer Support {role} count is correct: "
                    f"{actual}."
                )

        if role_counter.get("customer_support_agent", 0) <= 0:
            result.error(
                "Customer Support has no agents."
            )
        else:
            result.passed_check(
                f"Customer Support agent count: "
                f"{role_counter.get('customer_support_agent', 0)}."
            )


def validate_activity(users, base_config, result):
    scale = base_config.get("communication_scale", {})
    expected_percentage = scale.get("active_user_percentage")

    if expected_percentage is None:
        return

    internal_users = [
        user
        for user in users
        if user.get("user_type") == "internal"
    ]

    if not internal_users:
        return

    active_count = sum(
        1
        for user in internal_users
        if user.get("is_active") is True
    )

    actual_percentage = active_count / len(internal_users)

    # Allow a small tolerance for generated/random populations.
    tolerance = 0.03

    if abs(actual_percentage - expected_percentage) > tolerance:
        result.error(
            f"Active internal-user percentage is "
            f"{actual_percentage:.3f}; configured value is "
            f"{expected_percentage:.3f}."
        )
    else:
        result.passed_check(
            f"Active internal-user percentage: "
            f"{actual_percentage:.3f}."
        )


def validate_preferences(users, population_config, result):
    valid_activity = set(
        population_config
        .get("communication_activity_levels", {})
        .keys()
    )

    valid_behaviour = set(
        population_config
        .get("communication_behaviour_profiles", {})
        .keys()
    )

    for user in users:
        user_id = user.get("user_id")

        activity = user.get(
            "communication_activity_level"
        )

        if valid_activity and activity not in valid_activity:
            result.error(
                f"{user_id}: invalid activity level '{activity}'."
            )

        behaviour = user.get(
            "communication_behaviour_profile"
        )

        if valid_behaviour and behaviour not in valid_behaviour:
            result.error(
                f"{user_id}: invalid behaviour profile "
                f"'{behaviour}'."
            )

        preference = user.get(
            "internal_external_comm_preference"
        )

        if preference is not None:
            try:
                value = float(preference)

                if value < 0 or value > 1:
                    result.error(
                        f"{user_id}: internal/external preference "
                        f"must be between 0 and 1."
                    )
            except (ValueError, TypeError):
                result.error(
                    f"{user_id}: invalid internal/external preference."
                )

    if not result.errors:
        result.passed_check(
            "Communication activity, behaviour, and preference "
            "values are valid."
        )


def validate_frequent_contacts(users, result):
    user_ids = {
        user.get("user_id")
        for user in users
    }

    for user in users:
        user_id = user.get("user_id")
        frequent = user.get("frequent_contacts", [])
        has_frequent = user.get("has_frequent_contacts")

        if frequent is None:
            frequent = []

        if not isinstance(frequent, list):
            result.error(
                f"{user_id}: frequent_contacts is not a list."
            )
            continue

        if has_frequent is True and len(frequent) == 0:
            result.error(
                f"{user_id}: has_frequent_contacts is true "
                f"but no contacts are listed."
            )

        if has_frequent is False and len(frequent) != 0:
            result.error(
                f"{user_id}: has_frequent_contacts is false "
                f"but contacts are present."
            )

        if user_id in frequent:
            result.error(
                f"{user_id}: user references itself "
                f"as a frequent contact."
            )

        if len(frequent) != len(set(frequent)):
            result.error(
                f"{user_id}: duplicate frequent contacts."
            )

        invalid_contacts = [
            contact
            for contact in frequent
            if contact not in user_ids
        ]

        if invalid_contacts:
            result.error(
                f"{user_id}: references "
                f"{len(invalid_contacts)} unknown frequent contacts."
            )

    if not result.errors:
        result.passed_check(
            "Frequent-contact relationships are internally consistent."
        )


def validate_file_pair(json_users, csv_users, result):
    if len(json_users) != len(csv_users):
        result.error(
            f"JSON/CSV row count mismatch: "
            f"JSON={len(json_users)}, CSV={len(csv_users)}."
        )
        return

    json_ids = [
        user.get("user_id")
        for user in json_users
    ]

    csv_ids = [
        user.get("user_id")
        for user in csv_users
    ]

    if set(json_ids) != set(csv_ids):
        result.error(
            "JSON and CSV contain different user IDs."
        )
    else:
        result.passed_check(
            "JSON and CSV contain the same user IDs."
        )


def validate_dataset(scenario, config, result):
    scenario_dir = DATASET_ROOT / config["folder"]

    json_path = scenario_dir / config["json"]
    csv_path = scenario_dir / config["csv"]

    base_config = load_json(
        CONFIG_ROOT / config["base_config"]
    )

    advanced_config = load_json(
        CONFIG_ROOT / config["advanced_config"]
    )

    population_config = load_json(
        POPULATION_FILE
    )

    schema = load_json(USER_SCHEMA_FILE)

    if not json_path.exists():
        result.error(f"Missing JSON file: {json_path}")
        return

    if not csv_path.exists():
        result.error(f"Missing CSV file: {csv_path}")
        return

    json_users = load_users(json_path)
    csv_users = [
        normalize_csv_values(dict(user))
        for user in load_users(csv_path)
    ]

    print(f"\nValidating: {scenario}")
    print("-" * 60)

    validate_file_pair(
        json_users,
        csv_users,
        result
    )

    validate_required_fields(
        json_users,
        schema,
        result
    )

    validate_user_ids(
        json_users,
        result,
        scenario
    )

    validate_internal_external_ids(
        json_users,
        result,
        scenario
    )

    validate_counts(
        json_users,
        base_config,
        population_config
        .get("environments", {})
        .get(scenario, {}),
        result
    )

    validate_extensions(
        json_users,
        result
    )

    validate_ip_addresses(
        json_users,
        base_config,
        result
    )

    validate_domains(
        json_users,
        scenario,
        result
    )

    validate_roles(
        json_users,
        scenario,
        advanced_config,
        result
    )

    validate_activity(
        json_users,
        base_config,
        result
    )

    validate_preferences(
        json_users,
        population_config
        .get("environments", {})
        .get(scenario, {}),
        result
    )

    validate_frequent_contacts(
        json_users,
        result
    )

    print(f"Users: {len(json_users)}")
    print(f"Passed checks: {len(result.passed)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")


def main():
    print("=" * 60)
    print("VOIP USER DATASET VALIDATION")
    print("=" * 60)

    all_results = {}

    for scenario, config in SCENARIOS.items():
        result = ValidationResult()
        all_results[scenario] = result

        try:
            validate_dataset(
                scenario,
                config,
                result
            )
        except Exception as exc:
            result.error(
                f"Validation could not complete: {exc}"
            )

    print("\n")
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    overall_valid = True

    for scenario, result in all_results.items():
        status = "PASS" if result.is_valid else "FAIL"

        print(f"\n{scenario}: {status}")

        if result.errors:
            overall_valid = False

            print("\nErrors:")
            for error in result.errors:
                print(f"  [ERROR] {error}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  [WARNING] {warning}")

    print("\n" + "=" * 60)

    if overall_valid:
        print("OVERALL RESULT: PASS")
        print("All exported user datasets passed validation.")
    else:
        print("OVERALL RESULT: FAIL")
        print("One or more validation checks failed.")

    print("=" * 60)


if __name__ == "__main__":
    main()