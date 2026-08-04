import os

from steps import STEPS
from utils.group_operations import AP_GROUP_ATTRIBUTES
from utils.print_helpers import warn


REQUIRED_DEVICE_FIELDS = [
    "serial_number",
]
CENTRAL_DEVICE_FIELDS = ["device_type", "device_function", "device_group", "site"]
ADD_ON_FIELDS = {step.key: step.field for step in STEPS}
INHERITED_DEVICE_FIELDS = CENTRAL_DEVICE_FIELDS + list(ADD_ON_FIELDS)
SUPPORTED_DEVICE_TYPES = {"ACCESS_POINT"}
DEFAULT_MAX_DEVICES_PER_RUN = 50
DEFAULT_FIELDS = {
    "device_type",
    "device_function",
    "device_group",
    "site",
    "application_assignment",
    "subscription_key",
} | set(ADD_ON_FIELDS)
DEVICE_FIELDS = {
    "serial_number",
    "device_type",
    "device_function",
    "device_group",
    "site",
    "subscription_key",
    "glp_onboarding",
} | set(ADD_ON_FIELDS)
REQUIRED_SITE_FIELDS = [
    "name",
    "address",
    "city",
    "state",
    "country",
    "zipcode",
    "timezone",
]
REQUIRED_DEVICE_GROUP_FIELDS = ["group", "group_attributes"]
REQUIRED_SITE_COLLECTION_FIELDS = ["name", "sites"]


def get_max_devices_per_run():
    """Return the effective device cap, reading its environment override at use time."""
    raw_limit = os.environ.get("ONBOARDING_MAX_DEVICES")
    if raw_limit is None:
        return DEFAULT_MAX_DEVICES_PER_RUN

    try:
        max_devices = int(raw_limit)
    except (TypeError, ValueError):
        warn(
            f"Invalid ONBOARDING_MAX_DEVICES value {raw_limit!r}; "
            f"using default maximum of {DEFAULT_MAX_DEVICES_PER_RUN} devices."
        )
        return DEFAULT_MAX_DEVICES_PER_RUN

    if max_devices <= 0:
        warn(
            f"ONBOARDING_MAX_DEVICES must be positive; "
            f"using default maximum of {DEFAULT_MAX_DEVICES_PER_RUN} devices."
        )
        return DEFAULT_MAX_DEVICES_PER_RUN

    return max_devices


def validate_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def validate_defaults(defaults):
    unknown = sorted(set(defaults) - DEFAULT_FIELDS)
    if unknown:
        raise ValueError(f"defaults contains unknown keys: {', '.join(unknown)}")

    if "device_type" in defaults and defaults["device_type"] not in SUPPORTED_DEVICE_TYPES:
        raise ValueError(
            f"defaults.device_type '{defaults['device_type']}' is unsupported. "
            "Only ACCESS_POINT is supported by this workflow."
        )
    if "device_function" in defaults:
        validate_non_empty_string(defaults["device_function"], "defaults.device_function")
    # device_group and site are optional in defaults when every device supplies
    # its own value; blank strings here are treated as "not provided" and the
    # per-device check below will catch any device that needs them.
    for optional_field in ("device_group", "site"):
        if optional_field in defaults:
            value = defaults[optional_field]
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            validate_non_empty_string(value, f"defaults.{optional_field}")

    if "subscription_key" in defaults and "application_assignment" not in defaults:
        # GLP refuses a subscription on a device that is not assigned to a
        # service, and reports it only as a bare FAILED with no reason.
        raise ValueError(
            "defaults.subscription_key requires defaults.application_assignment"
        )
    if "application_assignment" in defaults:
        app = defaults["application_assignment"]
        if "name" not in app or "region" not in app:
            raise ValueError(
                "defaults.application_assignment missing required fields: 'name' and 'region'"
            )
    if "subscription_key" in defaults:
        if (
            not isinstance(defaults["subscription_key"], str)
            or not defaults["subscription_key"].strip()
        ):
            raise ValueError("defaults.subscription_key must be a non-empty string")
    for key, field in ADD_ON_FIELDS.items():
        if key in defaults:
            field.validate(defaults[key], f"defaults.{key}")


def validate_devices(devices, defaults=None):
    defaults = defaults or {}
    serials_seen = set()
    for idx, device in enumerate(devices):
        unknown = sorted(set(device) - DEVICE_FIELDS)
        if unknown:
            raise ValueError(
                f"Device {idx} contains unknown keys: {', '.join(unknown)}"
            )
        for field in REQUIRED_DEVICE_FIELDS:
            if field not in device:
                raise ValueError(f"Device {idx} missing required field: {field}")
        serial = device.get("serial_number")
        if serial in serials_seen:
            raise ValueError(
                f"Duplicate serial_number '{serial}' found in devices list."
            )
        serials_seen.add(serial)

        # Defaults have already been merged into each device by merge_central_defaults
        # (with empty strings on either side treated as missing). So any field still
        # absent here means neither the device nor defaults supplied a value.
        for field in CENTRAL_DEVICE_FIELDS:
            if field not in device:
                raise ValueError(
                    f"Device '{serial}' missing required field '{field}' and no defaults.{field} was provided."
                )

        device_type = device.get("device_type", defaults.get("device_type"))
        if device_type not in SUPPORTED_DEVICE_TYPES:
            raise ValueError(
                f"Device '{serial}' has unsupported device_type '{device_type}'. "
                "Only ACCESS_POINT is supported by this workflow."
            )

        device_function = device.get("device_function", defaults.get("device_function"))
        validate_non_empty_string(device_function, f"Device '{serial}' device_function")

        device_group = device.get("device_group", defaults.get("device_group"))
        validate_non_empty_string(device_group, f"Device '{serial}' device_group")

        site = device.get("site", defaults.get("site"))
        validate_non_empty_string(site, f"Device '{serial}' site")

        # GLP application assignment is only supported at defaults level.
        if "application_assignment" in device:
            raise ValueError(
                f"Device {idx} has application_assignment. "
                "Use defaults.application_assignment for a single workflow-wide assignment."
            )
        if "subscription_key" in device:
            if (
                not isinstance(device["subscription_key"], str)
                or not device["subscription_key"].strip()
            ):
                raise ValueError(
                    f"Device {idx} subscription_key must be a non-empty string"
                )
        # Devices are merged with defaults before validation, so an absent key
        # here means the step was set neither per-device nor in defaults.
        for key, field in ADD_ON_FIELDS.items():
            if key in device:
                field.validate(device[key], f"Device {idx} {key}")
            elif field.required:
                raise ValueError(f"Device {idx} missing required field '{key}'")


def validate_sites(sites):
    for idx, site in enumerate(sites):
        for field in REQUIRED_SITE_FIELDS:
            if field not in site:
                raise ValueError(f"Site {idx} missing required field: {field}")


def validate_device_groups(device_groups):
    names_seen = set()
    for idx, group in enumerate(device_groups):
        for field in REQUIRED_DEVICE_GROUP_FIELDS:
            if field not in group:
                raise ValueError(f"Device group {idx} missing required field: {field}")
        name = group["group"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Device group {idx} 'group' must be a non-empty string"
            )
        cleaned_name = name.strip()
        normalized_name = cleaned_name.casefold()
        if normalized_name in names_seen:
            raise ValueError(f"Duplicate device group name '{cleaned_name}'")
        names_seen.add(normalized_name)
        # Ensure NewCentral is present and True within group_properties
        group_attributes = group["group_attributes"]
        if not isinstance(group_attributes, dict):
            raise ValueError(
                f"Device group {idx} 'group_attributes' must be a mapping"
            )
        group_properties = group_attributes.get("group_properties", {})
        if (
            not isinstance(group_properties, dict)
            or "NewCentral" not in group_properties
            or group_properties["NewCentral"] is not True
        ):
            raise ValueError(
                f"Device group {idx} group_properties must have 'NewCentral: true'"
            )
        if group_attributes != AP_GROUP_ATTRIBUTES:
            raise ValueError(
                f"Device group {idx} group_attributes must match a supported device type"
            )


def validate_site_collections(site_collections):
    names_seen = set()
    for idx, sc in enumerate(site_collections):
        for field in REQUIRED_SITE_COLLECTION_FIELDS:
            if field not in sc:
                raise ValueError(f"Site collection {idx} missing required field: '{field}'")
        name = sc["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Site collection {idx} 'name' must be a non-empty string")
        if name in names_seen:
            raise ValueError(f"Duplicate site_collection name '{name}'")
        names_seen.add(name)
        sites = sc["sites"]
        if not isinstance(sites, list) or not sites:
            raise ValueError(f"Site collection '{name}' 'sites' must be a non-empty list")


def validate_configuration_profiles(configuration_profiles):
    for idx, binding in enumerate(configuration_profiles):
        has_site = "site" in binding
        has_collection = "site_collection" in binding
        if has_site and has_collection:
            raise ValueError(
                f"configuration_profiles[{idx}]: specify either 'site' or 'site_collection', not both"
            )
        if not has_site and not has_collection:
            raise ValueError(
                f"configuration_profiles[{idx}]: must specify either 'site' or 'site_collection'"
            )
        profiles = binding.get("profiles")
        if not isinstance(profiles, list) or not profiles:
            target = binding.get("site") or binding.get("site_collection")
            raise ValueError(
                f"configuration_profiles entry for '{target}' must have a non-empty 'profiles' list"
            )
        for pidx, p in enumerate(profiles):
            if "profile_name" not in p and "name" not in p:
                raise ValueError(
                    f"configuration_profiles[{idx}].profiles[{pidx}] missing required field 'profile_name'"
                )


def _validate_common_sections(data):
    """Validate sections that appear in both network-setup and device-onboarding YAMLs."""
    if "defaults" in data:
        if not isinstance(data["defaults"], dict):
            raise ValueError("'defaults' must be a mapping if provided")
        validate_defaults(data["defaults"])
    if "sites" in data and not isinstance(data["sites"], list):
        raise ValueError("'sites' must be a list if provided")
    if "site_collections" in data and not isinstance(data["site_collections"], list):
        raise ValueError("'site_collections' must be a list if provided")
    if "device_groups" in data and not isinstance(data["device_groups"], list):
        raise ValueError("'device_groups' must be a list if provided")
    if "configuration_profiles" in data and not isinstance(data["configuration_profiles"], list):
        raise ValueError("'configuration_profiles' must be a list if provided")
    if "sites" in data:
        validate_sites(data["sites"])
    if "site_collections" in data:
        validate_site_collections(data["site_collections"])
    if "device_groups" in data:
        validate_device_groups(data["device_groups"])
    if "configuration_profiles" in data:
        validate_configuration_profiles(data["configuration_profiles"])


NETWORK_SETUP_KEYS = ("sites", "site_collections", "device_groups", "configuration_profiles")
ONBOARDING_KEYS = ("defaults", "devices")


def validate_for_network_setup(data):
    """Validate network_setup_variables.yaml for network_setup.py.

    Requires at least one of: sites, site_collections, device_groups, configuration_profiles.
    Rejects onboarding-only keys (defaults, devices) with a helpful pointer.
    """
    if not isinstance(data, dict):
        raise ValueError("variables file must be a YAML mapping")

    unknown = sorted(set(data) - set(NETWORK_SETUP_KEYS))
    if unknown:
        raise ValueError(
            f"network setup variables contain unknown keys: {', '.join(unknown)}"
        )

    foreign = [k for k in ONBOARDING_KEYS if k in data]
    if foreign:
        raise ValueError(
            f"This file contains onboarding-only keys ({', '.join(foreign)}). "
            "network_setup.py expects network_setup_variables.yaml "
            "(sites / site_collections / device_groups / configuration_profiles). "
            "Did you mean to run onboarding.py?"
        )

    _validate_common_sections(data)
    if not any(data.get(k) for k in NETWORK_SETUP_KEYS):
        raise ValueError(
            "network_setup requires at least one of: "
            "'sites', 'site_collections', 'device_groups', or 'configuration_profiles'"
        )


def merge_central_defaults(devices, defaults=None):
    """Apply defaults to each device for inheritable core and add-on fields.

    Empty / whitespace-only strings on either side are treated as missing, so a
    blank device value is filled from a defaults value, and a blank defaults
    value is ignored. After merging, a field is present iff a real value
    came from the device or defaults.
    """
    defaults = defaults or {}
    merged = []
    for device in devices:
        merged_device = dict(device)
        for field in INHERITED_DEVICE_FIELDS:
            device_val = merged_device.get(field)
            if isinstance(device_val, str) and not device_val.strip():
                del merged_device[field]
            default_val = defaults.get(field)
            if field not in merged_device:
                if default_val is None:
                    continue
                if isinstance(default_val, str) and not default_val.strip():
                    continue
                merged_device[field] = default_val
        merged.append(merged_device)
    return merged


def validate_for_device_onboarding(data):
    """Validate onboarding_variables.yaml for onboarding.py.

    Requires a non-empty devices list. Rejects network-setup-only keys with a
    helpful pointer.
    """
    if not isinstance(data, dict):
        raise ValueError("variables file must be a YAML mapping")

    unknown = sorted(set(data) - set(ONBOARDING_KEYS))
    if unknown:
        raise ValueError(
            f"onboarding variables contain unknown keys: {', '.join(unknown)}"
        )

    foreign = [k for k in NETWORK_SETUP_KEYS if k in data]
    if foreign:
        raise ValueError(
            f"This file contains network-setup-only keys ({', '.join(foreign)}). "
            "onboarding.py expects onboarding_variables.yaml (defaults / devices). "
            "Did you mean to run network_setup.py?"
        )

    if (
        "devices" not in data
        or not isinstance(data["devices"], list)
        or len(data["devices"]) == 0
    ):
        raise ValueError(
            "Missing or invalid 'devices' list (at least one device required)"
        )
    max_devices = get_max_devices_per_run()
    if len(data["devices"]) > max_devices:
        raise ValueError(
            f"Too many devices ({len(data['devices'])}). "
            f"A maximum of {max_devices} devices is allowed per onboarding run."
        )
    _validate_common_sections(data)
    defaults = data.get("defaults", {})
    validate_devices(data["devices"], defaults)
