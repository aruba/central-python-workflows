import json

from pycentral import NewCentralBase
from pycentral.profiles import Profiles
from pycentral.utils.url_utils import NewCentralURLs


def main():
    # There are two ways to use Pycentral to interact with Central profiles. We can
    # use individual profile operations or bulk operations. The first thing we need
    # to do to use either of these is initialize a Central connection. Let's see how
    # to do that.

    # Generating a central connection with pycentral requires passing a dictionary
    # containing information to the NewCentralBase class. This dictionary should
    # include the base URL, client ID, and client secret for the Central API. Best
    # practice is to load this information from another file. For this example we will
    # load the credentials from a JSON file named 'central_token.json'. Please
    # reference the 'central_token.json' file in this directory for an example of how
    # the credential information should be structured.

    # Load the credentials from the JSON file
    try:
        with open("central_token.json", "r") as file:
            credentials = json.load(file)
    except FileNotFoundError:
        print("Error: Credentials file central_token.json not found.")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file 'central_token.json': {e}")
        return 1

    # Now that we have the credentials, we can create a connection to Central.
    try:
        print("Connecting to Central...")
        central_conn = NewCentralBase(
            token_info=credentials, enable_scope=True, log_level="ERROR"
        )
        print("Connected to Central successfully!")
    except Exception as e:
        print(f"\nFailed to connect to Central: {e}")
        return 1

    # Now that we have a connection to Central, we can start working with profiles.
    # Let's start by using the Profiles class to perform some individual profile
    # operations to work with the DNS profile. To do this, we need to gather
    # several pieces of information. This includes the API endpoint, the bulk key,
    # and the profile configurations we want to use. You can find this data by
    # referencing the API reference for the specific profile you want to work with.
    # The API reference for configuration profiles can be found at
    # https://developer.arubanetworks.com/new-central-config/reference/.

    # We refer to the bulk_key as the key that identifies the body object for the
    # payload of the API request. For example, in the case of DNS profiles,
    # the bulk_key is simply "profile".
    dns_bulk_key = "profile"
    # The endpoint is the suffix for the full API endpoint.
    dns_endpoint = "dns"
    # Let's set up a DNS profile to use for our operations.
    dns_profile = {
        "name": "example-dns",
        "description": "example-dns description",
        "resolver": [
            {"vrf": "default", "name-server": [{"ip": "8.8.8.8", "priority": 1}]}
        ],
    }
    # Finally, we use the generate_url function to create the full URL for the API
    # endpoint that will be consumed by the Pycentral functions.
    dns_url = NewCentralURLs.generate_url(api_endpoint=dns_endpoint)

    # Let's try creating a DNS profile using the create_profile function. We simply
    # need to pass the data we have prepared to the function along with the Central
    # Connection.
    print("\nCreating DNS profile...")
    create_profile = Profiles.create_profile(
        bulk_key=dns_bulk_key,
        path=dns_url,
        central_conn=central_conn,
        config_dict=dns_profile,
    )
    # if the profiles were created successfully, the function will return True.
    print(create_profile)

    # Now we can read the profile we just created. The get_profile function will
    # return a profile configuration specified by the path parameter. We will need
    # to add an identifier of the profile to the end of the URL to target the
    # specific profile in the Central Library. Most of the time the identifier will
    # be the profile name. Sometimes it will be something else, such as vlan for
    # VLAN profiles. You will want to refer to the API reference for the specific
    # profile you are working with to determine the correct identifier to use.
    print("\nGetting DNS profile...")
    example_dns_url = dns_url + f"/{dns_profile['name']}"
    get_dns = Profiles.get_profile(path=example_dns_url, central_conn=central_conn)
    print(get_dns)

    # We can also update the profile we just created. To update the profile we need
    # to provide a dictionary with the values we want to add/update. Each value
    # that matches a key from the current library profile configuration will be
    # updated and any that do not exist will be added. If any of the configurations
    # contain invalid values, the update will fail. We will also use the same URL
    # that we used to get the individual profile.
    print("\nUpdating DNS profile...")
    # For this example, we will update the description of the profile
    update_data = {"description": "Updated by script"}
    dns_profile.update(update_data)
    profile_update = Profiles.update_profile(
        bulk_key=None,
        path=example_dns_url,
        config_dict=dns_profile,
        central_conn=central_conn,
    )
    # The function will return True if the profile was updated successfully.
    print(profile_update)

    # Now we can read the updated profile to verify that the update was successful.
    print("\nReading updated DNS profile from Central...")
    get_updated_dns = Profiles.get_profile(
        path=example_dns_url, central_conn=central_conn
    )
    print(get_updated_dns)

    # Now let's delete the profile. Again, we will use the same URL as before with
    # the profile name appended to the end. The function will return True if the
    # profile was deleted successfully.
    print("\nDeleting DNS profile...")
    profile_delete = Profiles.delete_profile(
        path=example_dns_url, central_conn=central_conn
    )
    print(profile_delete)

    # To perform bulk profile operations through Pycentral, we need to gather the
    # same information. We will make some minor changes to the data that we pass
    # into the profile functions. Here we will use VLAN as an example for bulk
    # operations.
    vlan_bulk_key = "l2-vlan"
    # The endpoint is the suffix for the full URL.
    vlan_endpoint = "layer2-vlan"
    # Let's set up a few VLAN profiles to demonstrate bulk operations.
    vlan_profile1 = {
        "name": "profile-configuration-test456",
        "vlan": 456,
        "description": "profile-configuration-test456",
        "is-l3-vlan": None,
    }
    vlan_profile2 = {
        "name": "profile-configuration-test523",
        "vlan": 523,
        "description": "profile-configuration-test523",
        "is-l3-vlan": None,
    }
    vlan_profile3 = {
        "name": "profile-configuration-test673",
        "vlan": 673,
        "description": "profile-configuration-test673",
        "is-l3-vlan": None,
    }
    # Generate the URL for the VLAN endpoint.
    vlan_url = NewCentralURLs.generate_url(api_endpoint=vlan_endpoint)

    # Let's try creating several VLAN profiles using the bulk create_profiles
    # function. We can create a list of dictionaries containing the profile
    # configurations we want to create. This list will be passed to the
    # create_profiles function as the list_dict parameter.
    print("\nCreating bulk VLAN profiles...")
    vlan_profiles = [vlan_profile1, vlan_profile2, vlan_profile3]
    create_profiles = Profiles.create_profiles(
        bulk_key=vlan_bulk_key,
        path=vlan_url,
        central_conn=central_conn,
        list_dict=vlan_profiles,
    )
    # if the profiles were created successfully, the function will return True.
    print(create_profiles)

    # Now we can read the profiles we just created. The get_profile function will
    # return all the profiles in the category specified by the path parameter. This
    # time we don't need to add an identifier to the end of the URL since we want
    # to get all profiles in the category.
    print("\nGetting all VLAN profiles...")
    get_vlans = Profiles.get_profile(path=vlan_url, central_conn=central_conn)
    print(get_vlans)

    # We can also update the profiles we just created at the same time. To update
    # multiple profiles, a list of configuration dictionaries must be provided.
    # Just like individual updates, each value that is different from the current
    # library profile configuration will be updated and new ones will be added.
    # This time, each configuration dictionary must include the identifier(name,
    # ssid, vlan, etc...) for the profile to update. If any of the profiles in the
    # list contain invalid configuration or the identifier does not match an
    # existing profile, the update will fail for all profiles. The function will
    # return True if the profiles were updated successfully.
    print("\nBulk updating VLAN profiles...")
    # For this example, we will update the description for all the vlan profiles
    # at the same time.
    for profile in vlan_profiles:
        profile.update(update_data)
    bulk_update = Profiles.update_profiles(
        bulk_key=vlan_bulk_key,
        path=vlan_url,
        central_conn=central_conn,
        list_dict=vlan_profiles,
    )
    print(bulk_update)

    # Now we can read the updated profiles to verify that the updates were
    # successful.
    print("\nReading updated VLAN profiles from Central...")
    print(Profiles.get_profile(path=vlan_url, central_conn=central_conn))

    # Let's delete all the profiles at once. The delete_profiles function takes a
    # list of endpoint URLs to delete. Each URL should be the full endpoint URL
    # with the identifiers for the profile to delete appended to the end, just like
    # we did for deleting individual profiles. The function will return a list of
    # URLs that failed to delete, or an empty list if all profiles were deleted
    # successfully.
    print("\nDeleting VLAN profiles...")
    # Create a list of URLs with identifiers to delete the profiles.
    path_list = [
        NewCentralURLs.generate_url(api_endpoint=vlan_endpoint) + f"/{profile['vlan']}"
        for profile in vlan_profiles
    ]
    bulk_delete = Profiles.delete_profiles(
        path_list=path_list, central_conn=central_conn
    )
    print(bulk_delete)

    print("\nAll operations completed successfully!")
    return 0


if __name__ == "__main__":
    exit(main())
