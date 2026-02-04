REQUIRED_DEVICE_FIELDS = [
    "serial_number",
    "device_type",
    "persona",
    "device_group",
    "site",
]
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


def validate_devices(devices):
    for idx, device in enumerate(devices):
        for field in REQUIRED_DEVICE_FIELDS:
            if field not in device:
                raise ValueError(f"Device {idx} missing required field: {field}")
        # If application_assignment is present, check its fields and require subscription_assignment
        if "application_assignment" in device:
            if (
                "name" not in device["application_assignment"]
                or "region" not in device["application_assignment"]
            ):
                raise ValueError(
                    f"Device {idx} application_assignment missing name or region"
                )
            if "subscription_assignment" not in device:
                raise ValueError(
                    f"Device {idx} has application_assignment but missing subscription_assignment"
                )
            if "key" not in device["subscription_assignment"]:
                raise ValueError(f"Device {idx} subscription_assignment missing key")
        # If application_assignment is not present, subscription_assignment is not required


def validate_sites(sites):
    for idx, site in enumerate(sites):
        for field in REQUIRED_SITE_FIELDS:
            if field not in site:
                raise ValueError(f"Site {idx} missing required field: {field}")


def validate_device_groups(device_groups):
    for idx, group in enumerate(device_groups):
        for field in REQUIRED_DEVICE_GROUP_FIELDS:
            if field not in group:
                raise ValueError(f"Device group {idx} missing required field: {field}")
        # Ensure NewCentral is present and True within group_properties
        group_attributes = group["group_attributes"]
        group_properties = group_attributes.get("group_properties", {})
        if (
            "NewCentral" not in group_properties
            or group_properties["NewCentral"] is not True
        ):
            raise ValueError(
                f"Device group {idx} group_properties must have 'NewCentral: true'"
            )


def validate_yaml_structure(data):
    # Devices: required and must be a non-empty list
    if (
        "devices" not in data
        or not isinstance(data["devices"], list)
        or len(data["devices"]) == 0
    ):
        raise ValueError(
            "Missing or invalid 'devices' list (at least one device required)"
        )
    # Sites: if present, must be a list
    if "sites" in data and not isinstance(data["sites"], list):
        raise ValueError("'sites' must be a list if provided")
    # Device groups: if present, must be a list
    if "device_groups" in data and not isinstance(data["device_groups"], list):
        raise ValueError("'device_groups' must be a list if provided")
    validate_devices(data["devices"])
    if "sites" in data:
        validate_sites(data["sites"])
    if "device_groups" in data:
        validate_device_groups(data["device_groups"])
