"""network_setup.py — Prepare network infrastructure in HPE Aruba Central.

Run this once (or whenever sites, groups, or profile bindings change) before
onboarding devices with onboarding.py.

What this script does:
  1. Create any sites declared in network_setup_variables.yaml that do not yet exist.
  2. Create any site collections declared that do not yet exist.
  3. Create any device groups declared that do not yet exist, and verify each is
     a New Central 3.x (AOS10) access-point group with correct attributes.
  4. Bind configuration profiles to sites or site collections (configuration_profiles
     section in YAML).  Each profile entry uses name, profile_type, and
     device_function (friendly name e.g. "Campus Access Point") attributes; the binding target
     is specified with either 'site' or 'site_collection'.

Usage:
  python3 network_setup.py \\
    -c account_credentials.yaml \\
    -cc classic_central_credentials.yaml \\
    -vars network_setup_variables.yaml

Exit code: 0 on full success, 1 if any step fails (safe to gate CI on this).
"""

import sys
import time

from pycentral import NewCentralBase
from pycentral.workflows.workflows_utils import get_conn_from_file

from utils.cli import build_common_arg_parser, load_and_validate_variables
from utils.group_operations import create_groups_phase
from utils.network_setup_tracker import NetworkSetupTracker
from utils.print_helpers import error, info, phase_header, warn
from utils.profile_operations import (
    bind_profiles_to_site,
    bind_profiles_to_site_collection,
)
from utils.preflight import (
    format_credential_verification_error,
    verify_credential_canaries,
)
from utils.site_operations import (
    create_site_collections_phase,
    create_sites_phase,
    get_site_collection_name_id_mapping,
    get_site_name_id_mapping_new_central,
)
from utils.validate_workflow_variables_template import validate_for_network_setup


def run_network_setup(variables_data, creds_path, classic_creds_path, *, tracker=None):
    scoped_conn = NewCentralBase(token_info=creds_path, log_level="ERROR", enable_scope=True)
    classic_central_conn = get_conn_from_file(filename=classic_creds_path)

    sites = variables_data.get("sites") or []
    site_collections = variables_data.get("site_collections") or []
    groups = variables_data.get("device_groups") or []
    configuration_profiles = variables_data.get("configuration_profiles") or []

    if tracker is None:
        tracker = NetworkSetupTracker(sites, groups, configuration_profiles, site_collections)

    # ── Phase 1: Sites ───────────────────────────────────────────────────────
    phase_header("Sites", 1, 4)
    if sites:
        site_name_to_id = get_site_name_id_mapping_new_central(scoped_conn)
        create_sites_phase(scoped_conn, sites, site_name_to_id, tracker)
        site_name_to_id = get_site_name_id_mapping_new_central(scoped_conn)
    else:
        info("no sites declared, skipping")
        site_name_to_id = get_site_name_id_mapping_new_central(scoped_conn)
    # ── Phase 2: Site Collections ────────────────────────────────────────────
    phase_header("Site Collections", 2, 4)
    if site_collections:
        create_site_collections_phase(scoped_conn, site_collections, site_name_to_id, tracker)
    else:
        info("no site_collections declared, skipping")

    # ── Phase 3: Groups ──────────────────────────────────────────────────────
    phase_header("Device Groups", 3, 4)
    if groups:
        create_groups_phase(scoped_conn, classic_central_conn, groups, tracker)
    else:
        info("no device groups declared, skipping")
    # ── Phase 4: Profile Bindings ────────────────────────────────────────────
    phase_header("Profile Bindings", 4, 4)
    if configuration_profiles:
        collection_name_to_id = get_site_collection_name_id_mapping(scoped_conn)

        # Partition bindings into those whose target exists and those that don't.
        bindings_to_apply = []
        for binding in configuration_profiles:
            profile_entries = binding.get("profiles", [])
            if "site_collection" in binding:
                target_type = "site_collection"
                target_name = binding["site_collection"]
                scope_id = collection_name_to_id.get(target_name)
            else:
                target_type = "site"
                target_name = binding["site"]
                scope_id = site_name_to_id.get(target_name)

            if not scope_id:
                warn(
                    f"{target_type.replace('_', ' ')} '{target_name}' not found in Central — "
                    "skipping profile binding(s)"
                )
                skip_reason = (
                    f"{target_type.replace('_', ' ')} '{target_name}' does not exist in Central"
                )
                for entry in profile_entries:
                    tracker.mark_profile(
                        target_type, target_name, entry.get("name"), "Skipped", skip_reason
                    )
            else:
                bindings_to_apply.append((binding, target_type, scope_id, target_name, profile_entries))

        for binding, target_type, scope_id, target_name, profile_entries in bindings_to_apply:
            if target_type == "site_collection":
                outcomes = bind_profiles_to_site_collection(
                    scoped_conn, scope_id, target_name, profile_entries
                )
                for profile_name, status, err in outcomes:
                    tracker.mark_profile("site_collection", target_name, profile_name, status, err or None)
            else:
                outcomes = bind_profiles_to_site(
                    scoped_conn, scope_id, target_name, profile_entries
                )
                for profile_name, status, err in outcomes:
                    tracker.mark_profile("site", target_name, profile_name, status, err or None)
    else:
        info("no configuration_profiles declared, skipping")

    tracker.generate_summary()
    return tracker


def main():
    start_time = time.time()
    args = build_common_arg_parser(
        "Network Setup — create sites, groups, and bind profiles in Aruba Central"
    ).parse_args()

    credential_result = verify_credential_canaries(
        args.credentials,
        args.classic_credentials,
    )
    if not credential_result["ok"]:
        error(format_credential_verification_error(credential_result))
        sys.exit(1)

    variables_data = load_and_validate_variables(args.variables_file, validate_for_network_setup)

    tracker = run_network_setup(variables_data, args.credentials, args.classic_credentials)
    info(f"total execution time: {time.time() - start_time:.2f}s")
    sys.exit(1 if tracker.has_failures() else 0)


if __name__ == "__main__":
    main()
