import csv
import json
from pathlib import Path

from src.config_resolver import ConfigResolver
from src.user_generator import UserGenerator

from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_ROOT / "generated_dataset"


def export_users(
    scenario_name,
    output_folder,
    json_filename,
    csv_filename
):
    resolver = ConfigResolver(PROJECT_ROOT)

    # Resolve scenario configuration
    resolved_config = resolver.resolve_scenario(scenario_name)

    # Generate users
    generator = UserGenerator(resolved_config)
    users = generator.generate()

    #
    print("-" * 70)
    print(f"Testing user generation: {scenario_name}")
    print("-" * 70)

    total_users = len(users)

    internal_users = sum(
        1 for user in users if user["user_type"] == "internal"
    )

    external_users = sum(
        1 for user in users if user["user_type"] == "external"
    )

    role_distribution = Counter(
        user["user_role"] for user in users
    )

    print(f"Total users: {total_users}")
    print(f"Internal users: {internal_users}")
    print(f"External users: {external_users}")

    print("\nRole distribution:")
    for role, count in sorted(role_distribution.items()):
        print(f"  {role}: {count}")

    print("\nFirst user:")
    print(users[0])

    # Create output directory
    output_dir = OUTPUT_ROOT / output_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # JSON EXPORT
    # -------------------------------------------------
    json_path = output_dir / json_filename

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(
            users,
            file,
            indent=2,
            ensure_ascii=False
        )

    # -------------------------------------------------
    # CSV EXPORT
    # -------------------------------------------------
    csv_path = output_dir / csv_filename

    if users:
        # Collect ALL fields used by ALL users.
        fieldnames = []
        seen_fields = set()

        for user in users:
            for field in user.keys():
                if field not in seen_fields:
                    fieldnames.append(field)
                    seen_fields.add(field)

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
                extrasaction="ignore"
            )

            writer.writeheader()
            writer.writerows(users)

    print(f"{scenario_name}: {len(users)} users generated")
    print(f"  JSON: {json_path}")
    print(f"  CSV : {csv_path}")
    print()


def main():

    # -------------------------------------------------
    # ENTERPRISE
    # -------------------------------------------------
    export_users(
        scenario_name="enterprise",
        output_folder="enterprise",
        json_filename="enterprise_users.json",
        csv_filename="enterprise_users.csv"
    )

    # -------------------------------------------------
    # CUSTOMER SUPPORT CENTRE
    # -------------------------------------------------
    export_users(
        scenario_name="customer_support_center",
        output_folder="customer_support_center",
        json_filename="customer_support_center_users.json",
        csv_filename="customer_support_center_users.csv"
    )

    print("User dataset export completed successfully.")


if __name__ == "__main__":
    main()