import yaml
from operator import itemgetter
from termcolor import colored
from pycentral import NewCentralBase
from pycentral.profiles import Wlan, Role, Profiles, Policy
from pycentral.scopes import Scopes
from pycentral.utils.url_utils import NewCentralURLs
from pycentral.base import ArubaCentralBase
from pycentral.classic.monitoring import Sites


def load_configurations():
    profiles_vars = yaml.safe_load(open("wlan_overlay_profiles.yaml"))
    credentials = yaml.safe_load(open("account_credentials.yaml"))
    inventory = yaml.safe_load(open("inventory.yaml"))
    return profiles_vars, credentials, inventory


def create_central_connection(credentials):
    central_conn = NewCentralBase(
        token_info={"new_central": credentials["new_central"]},
        log_level="INFO",
        enable_scope=False,
    )
    if central_conn is None:
        print("Error in central connection")
        exit()
    return central_conn


def create_roles(central_conn, roles_dict):
    for role in roles_dict:
        result = Role.create_role(
            central_conn=central_conn, name=role["name"], config_dict=role
        )
        if not result:
            print(f"Error in creating role {role['name']}")

            exit()
        else:
            print(
                f"Successfully created {colored('ROLE', 'blue')} library profile - {colored(role['name'], 'blue')}"
            )


def create_policies(central_conn, policies_dict):
    for policy in policies_dict:
        result = Policy.create_policy(
            central_conn=central_conn, name=policy["name"], config_dict=policy
        )
        if not result:
            print(f"Error in creating policy {policy['name']}")
            exit()
        else:
            print(
                f"Successfully created {colored('POLICY', 'blue')} library profile - {colored(policy['name'], 'blue')}"
            )


def create_ssids(central_conn, ssids_dict):
    for ssid in ssids_dict:
        result = Wlan.create_wlan(
            central_conn=central_conn, ssid=ssid["ssid"], config_dict=ssid
        )
        if not result:
            print(f"Error in creating SSID {ssid['ssid']}")
            exit()
        else:
            print(
                f"Successfully created {colored('SSID', 'blue')} library profile - {colored(ssid['ssid'], 'blue')}"
            )

        wlan_role_dict = {"name": ssid["ssid"], "description": ssid["ssid"]}
        result = Role.create_role(
            central_conn=central_conn, name=ssid["ssid"], config_dict=wlan_role_dict
        )
        if not result:
            print(f"Error in creating role {ssid['ssid']}")

            exit()
        else:
            print(
                f"Successfully created {colored('ROLE', 'blue')} library profile - {colored(ssid['ssid'], 'blue')}"
            )


def create_profiles(central_conn, path, body_key, profiles_dict):
    # policy-group has distinct structure that doesn't match config profiles
    if body_key == "policy-group":
        body = dict()
        body[body_key] = profiles_dict
        resp = central_conn.command("POST", path, api_data=body, api_params=None)
        if resp["code"] == 200:
            print(
                f"Successfully created {colored('PROFILE', 'blue')} library profile - {colored(body_key, 'blue')}"
            )
        else:
            error = resp["msg"]
            err_str = f"Error-message -> {error}"
            central_conn.logger.error(
                f"Failed to create {body_key} profile - {err_str}"
            )
    else:
        # Not all features are implemented as classes so generic create_profiles
        # can be used to create configuration profiles profiles
        for profile in profiles_dict:
            result = Profiles.create_profile(
                bulk_key=body_key,
                path=path,
                central_conn=central_conn,
                config_dict=profile,
            )
            if not result:
                print(f"Error in creating profile {profile['profile']}")
                exit()
            else:
                print(
                    f"Successfully created {colored('PROFILE', 'blue')} library profile - {colored(profile['profile'], 'blue')}"
                )


def assign_profiles_to_global(scope_global, roles_dict, policies_dict):
    print("Assigning Profiles...")
    device_personas = ["CAMPUS_AP", "MOBILITY_GW"]
    for role in roles_dict:
        profile_resource_str = f"{Role.get_resource()}/{role['name']}"
        result = scope_global.assign_profile_to_scope(
            profile_name=profile_resource_str,
            profile_persona=device_personas,
            scope="global",
        )
        if not result:
            print(
                f"Error in assigning profile {role['name']} with persona {device_personas} to global scope"
            )
        else:
            print(
                f"Successfully assigned {colored('ROLE', 'blue')} profile - {colored(role['name'], 'blue')} to {colored('GLOBAL SCOPE', 'blue')} - {colored(scope_global.get_id(), 'blue')}"
            )

    for policy in policies_dict:
        profile_resource_str = f"{Policy.get_resource()}/{policy['name']}"
        result = scope_global.assign_profile_to_scope(
            profile_name=profile_resource_str,
            profile_persona=device_personas,
            scope="global",
        )
        if not result:
            print(
                f"Error in assigning profile {policy['name']} with persona {device_personas} to global scope"
                f" - {result}"
            )
        else:
            print(
                f"Successfully assigned {colored('POLICY', 'blue')} profile - {colored(policy['name'], 'blue')} to {colored('GLOBAL SCOPE', 'blue')} - {colored(scope_global.get_id(), 'blue')}"
            )


def assign_profiles_to_group(central_conn, group_id, ssids_dict, overlay_wlan):
    print("Assigning Profiles...")
    device_persona = "CAMPUS_AP"
    # Need to use Command b/c group assignment not currently supported
    for ssid in ssids_dict:
        profile_resource_str = f"{Wlan.get_resource()}/{ssid['ssid']}"
        path = NewCentralURLs.generate_url(api_endpoint="scope-maps")
        body = {
            "scope-name": str(group_id),
            "persona": device_persona,
            "resource": profile_resource_str,
        }
        resp = central_conn.command(
            "POST", path, api_data={"scope-map": [body]}, api_params=None
        )
        if resp["code"] == 200:
            print(
                f"Successfully assigned {colored(profile_resource_str, 'blue')} library profile - {colored(group_id, 'blue')}"
            )
        else:
            error = resp["msg"]
            err_str = f"Error-message -> {error}"
            central_conn.logger.error(
                f"Failed to assign {colored(profile_resource_str, 'blue')} library profile - {colored(group_id, 'blue')}"
                f" - {err_str}"
            )
        # Need to assign SSID Role to Global
        scope_global = Scopes(central_conn=central_conn)
        profile_resource_str = f"{Role.get_resource()}/{ssid['ssid']}"

        result = scope_global.assign_profile_to_scope(
            profile_name=profile_resource_str,
            profile_persona=device_persona,
            scope="global",
        )
        if not result:
            print(
                f"Error in assigning profile {ssid['ssid']} with persona {device_persona} to global scope"
            )
        else:
            print(
                f"Successfully assigned {colored('ROLE', 'blue')} profile - {colored(ssid['ssid'], 'blue')} to {colored('GLOBAL SCOPE', 'blue')} - {colored(scope_global.get_id(), 'blue')}"
            )

    # Need to use Command b/c group assignment not currently supported
    profile_resource_str = f"overlay-wlan/{overlay_wlan['profile']}"
    path = NewCentralURLs.generate_url(api_endpoint="scope-maps")
    body = {
        "scope-name": str(group_id),
        "persona": device_persona,
        "resource": profile_resource_str,
    }
    resp = central_conn.command(
        "POST", path, api_data={"scope-map": [body]}, api_params=None
    )
    if resp["code"] == 200:
        print(
            f"Successfully assigned {colored(profile_resource_str, 'blue')} library profile - {colored(group_id, 'blue')}"
        )
    else:
        error = resp["msg"]
        err_str = f"Error-message -> {error}"
        central_conn.logger.error(
            f"Failed to assign {colored(profile_resource_str, 'blue')} library profile - {colored(group_id, 'blue')}"
            f" - {err_str}"
        )


def move_device_to_site(token_info, site_device_assignment):
    central_conn = ArubaCentralBase(central_info=token_info["classic"])
    global_site = Sites()
    move_device_status = False
    for site_name, devices in site_device_assignment.items():
        if site_name == "AP_GROUP":
            continue
        site_id = global_site.find_site_id(conn=central_conn, site_name=site_name)
        if not site_id:
            exit(f"Unable to find site {site_name}")
        for devices_data in devices:
            for serial_num in devices_data["devices"]:
                resp = global_site.associate_devices(
                    conn=central_conn,
                    site_id=site_id,
                    device_type=devices_data["device_type"],
                    device_ids=serial_num,
                )
                if resp["code"] == 200:
                    print(
                        f"Successfully assigned device {colored(serial_num, 'blue')} to - {colored(site_name, 'blue')}"
                    )
                    move_device_status = True
                else:
                    move_device_status = False
                    print(resp["msg"])
                    return move_device_status
    return move_device_status


def main():
    profiles_vars, credentials, inventory = load_configurations()
    central_conn = create_central_connection(credentials)
    central_conn = NewCentralBase(
        token_info={"new_central": credentials["new_central"]},
        log_level="INFO",
        enable_scope=False,
    )
    scope_global = central_conn.get_scopes()

    policies_dict, ssids_dict, roles_dict, policy_group, overlay_wlan = itemgetter(
        "policies", "ssids", "roles", "policy-group", "overlay-wlan"
    )(profiles_vars)

    print("Creating Library Profiles....")
    create_roles(central_conn, roles_dict)
    create_policies(central_conn, policies_dict)
    create_profiles(
        central_conn,
        NewCentralURLs.generate_url(api_endpoint="policy-groups"),
        "policy-group",
        policy_group,
    )

    print("Assigning Library Role & Policies to Global....")
    assign_profiles_to_global(scope_global, roles_dict, policies_dict)

    print("Creating SSID Profiles....")
    create_ssids(central_conn, ssids_dict)
    create_profiles(
        central_conn,
        NewCentralURLs.generate_url(api_endpoint="overlay-wlan"),
        "ssid-cluster",
        [overlay_wlan],
    )

    print("Assigning devices to Site...")
    move_device_to_site(token_info=credentials, site_device_assignment=inventory)

    assign_profiles_to_group(
        central_conn, inventory["AP_GROUP"], ssids_dict, overlay_wlan
    )


if __name__ == "__main__":
    main()
