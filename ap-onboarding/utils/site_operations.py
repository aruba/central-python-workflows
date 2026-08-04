from pycentral.monitoring import Sites

from utils.api_helpers import name_id_map_from_scope, paginate_api, raise_for_central_response
from utils.print_helpers import info, step_ok, step_progress_str
from utils.retry import retry_on_response

SITES_LIMIT = 100
SITE_ASSOCIATION_PAUSE = 5
site_api = Sites()

SITE_COLLECTIONS_API_BASE = "network-config/v1alpha1/site-collections"
SITE_COLLECTIONS_PAGE_LIMIT = 100

DEVICE_TYPE_MAPPING = {
    "ACCESS_POINT": "IAP",
}


def get_site_name_id_mapping(classic_central_conn, sites_limit=SITES_LIMIT):
    """Get all sites and return a mapping of site name to site id."""

    def fetch_page(offset, limit):
        response = site_api.get_sites(
            conn=classic_central_conn,
            calculate_total=True,
            limit=limit,
            offset=offset,
        )
        payload = response["msg"]
        return payload.get("sites", []), payload.get("total")

    sites = paginate_api(fetch_page, sites_limit)
    return {site["site_name"]: site["site_id"] for site in sites}


def create_site(new_central_conn, site_name, sites_by_name):
    """Create site if it does not already exist."""
    sites = new_central_conn.scopes.sites
    if site_name in [site.name for site in sites]:
        info(f"site '{site_name}' already exists, skipping creation")
        return True

    site_attributes = sites_by_name.get(site_name)
    if site_attributes is None:
        raise Exception(f"Site {site_name} not found in provided site details.")

    site_creation_status = new_central_conn.scopes.create_site(
        site_attributes=site_attributes
    )
    if not site_creation_status:
        raise Exception(f"Failed to create site {site_name}.")
    info(f"created site '{site_name}'")
    return True


def create_sites_phase(new_central_conn, sites, site_name_to_site_id, ns_tracker):
    """Create missing sites and record outcomes in NetworkSetupTracker.

    sites              — list of site dicts from workflow_variables.yaml sites section
    site_name_to_site_id — mapping of already-existing site names to IDs
    ns_tracker         — NetworkSetupTracker
    """
    sites_by_name = {site["name"]: site for site in sites}

    for site_name in sorted(sites_by_name):
        if site_name in site_name_to_site_id:
            info(f"site '{site_name}' already exists, skipping creation")
            ns_tracker.mark_site(site_name, "create", "Skipped")
        else:
            info(f"site '{site_name}' not found, creating")
            try:
                create_site(new_central_conn, site_name, sites_by_name)
                ns_tracker.mark_site(site_name, "create", "Success")
            except Exception as error:
                ns_tracker.mark_site(site_name, "create", "Failed", str(error))


def get_site_name_id_mapping_new_central(new_central_conn):
    """Return mapping of site name → site ID using the New Central API."""
    return name_id_map_from_scope(new_central_conn.scopes.sites)


def get_site_collection_name_id_mapping(new_central_conn):
    """Return a mapping of site-collection name → collection ID from Central."""

    def fetch_page(offset, limit):
        response = new_central_conn.command(
            api_method="GET",
            api_path=SITE_COLLECTIONS_API_BASE,
            api_params={"limit": limit, "offset": offset},
        )
        raise_for_central_response(response, "list site collections", ok_codes=(200, 404))
        if response.get("code") == 404:
            return [], 0
        payload = response.get("msg", {})
        return payload.get("items", []), payload.get("total", 0)

    collections = paginate_api(fetch_page, SITE_COLLECTIONS_PAGE_LIMIT)
    return {c["scopeName"]: c["id"] for c in collections}


def create_site_collection(new_central_conn, name, site_ids):
    """Create a site collection containing the given site IDs."""
    response = new_central_conn.command(
        api_method="POST",
        api_path=SITE_COLLECTIONS_API_BASE,
        api_data={"scopeName": name, "siteIds": site_ids},
    )
    raise_for_central_response(response, f"create site collection '{name}'", ok_codes=(200, 201))
    payload = response.get("msg", {})
    return payload.get("id") or payload.get("site_collection_id")


def create_site_collections_phase(new_central_conn, site_collections, site_name_to_id, ns_tracker):
    """Create missing site collections and record outcomes in NetworkSetupTracker.

    site_collections  — list of {name, sites: [site_name, ...]} from workflow_variables.yaml
    site_name_to_id   — mapping of site name → site ID (from Central after site creation)
    ns_tracker        — NetworkSetupTracker
    """
    existing = get_site_collection_name_id_mapping(new_central_conn)

    for sc in site_collections:
        sc_name = sc["name"]
        site_names = sc.get("sites") or []

        if sc_name in existing:
            info(f"site collection '{sc_name}' already exists, skipping creation")
            ns_tracker.mark_site_collection(sc_name, "create", "Skipped")
            continue

        missing_sites = [s for s in site_names if s not in site_name_to_id]
        if missing_sites:
            error = (
                f"Cannot create site collection '{sc_name}': "
                f"the following sites were not found in Central: {', '.join(missing_sites)}"
            )
            ns_tracker.mark_site_collection(sc_name, "create", "Failed", error)
            continue

        site_ids = [str(site_name_to_id[s]) for s in site_names]
        try:
            create_site_collection(new_central_conn, sc_name, site_ids)
            info(f"created site collection '{sc_name}'")
            ns_tracker.mark_site_collection(sc_name, "create", "Success")
        except Exception as error:
            ns_tracker.mark_site_collection(sc_name, "create", "Failed", str(error))


def associate_device_to_site_api(
    classic_central_conn,
    device_serial_number,
    device_type,
    site_id,
    max_retries,
    retry_pause,
):
    api_path = "central/v2/sites/associate"
    api_method = "POST"
    api_data = {
        "device_id": device_serial_number,
        "device_type": device_type,
        "site_id": site_id,
    }

    response = retry_on_response(
        operation=lambda: classic_central_conn.command(
            apiPath=api_path, apiMethod=api_method, apiData=api_data
        ),
        is_success=lambda result: result.get("code") == 200,
        should_retry=lambda result: result.get("code") == 429
        or result.get("code", 0) >= 500,
        max_retries=max_retries,
        pause_seconds=retry_pause,
        on_retry_message=lambda result, attempt, total_attempts: step_progress_str(
            device_serial_number,
            f"site association failed (HTTP {result.get('code')}), retrying in {retry_pause}s",
            attempt, total_attempts,
        ),
    )

    raise_for_central_response(response, f"associate device {device_serial_number} with site {site_id}")
    return True


def assign_device_to_site(
    classic_central_conn,
    device_serial_number,
    device_type,
    site_name,
    site_name_to_site_id,
    device_site_mapping,
    max_retries,
    retry_pause=SITE_ASSOCIATION_PAUSE,
):
    site_id = site_name_to_site_id.get(site_name)
    if device_type not in DEVICE_TYPE_MAPPING:
        raise Exception(
            f"Unsupported device type: {device_type}. Supported types are: {list(DEVICE_TYPE_MAPPING.keys())}."
        )

    if not site_id:
        raise Exception(f"Site {site_name} not found in Central.")

    if device_site_mapping and device_serial_number in device_site_mapping:
        existing_site = device_site_mapping[device_serial_number]
        if existing_site is not None:
            raise Exception(
                f"Device {device_serial_number} is already assigned to site {existing_site}. "
                "Please remove the device from the site before assigning it to a new site."
            )

    associate_device_to_site_api(
        classic_central_conn,
        device_serial_number,
        DEVICE_TYPE_MAPPING[device_type],
        site_id,
        max_retries,
        retry_pause,
    )

    step_ok(device_serial_number, f"assigned to site '{site_name}'")
    return True
