"""
Sample Python Script to bring up a site in Aruba Central through REST API.
Involves creating group, adding devices, uploading templates and variables,
creating sites.
For complete capababilities of Aruba Central's REST API refer to API
documentation under Maintenance->API Gateway tab
"""
from central_configuration import ArubaCentralConfiguration
import json
from central_main import ArubaCentralAPI
from argparse import ArgumentParser, RawDescriptionHelpFormatter


def define_arguments():
    """
    Define arguments that this script will use.
    :return: Populated argument parser
    """
    description = ("This is a webserver application written to integrate \
                   aruba central and slack api bot user"
                   "Tested with Python 3.7"
                   "Required Packages: Requests")
    parser = ArgumentParser(description=description,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--input', required=True,
                        help=('Input file in JSON format which has \
                              central and slack info '
                              'as required by this script.'))
    return parser.parse_args()


if __name__ == "__main__":

    args = define_arguments()
    input_args = ""
    file_name = args.input

    with open(file_name, "r") as fp:
        input_args = json.loads(fp.read())

    central = input_args["central_info"]
    base_url = central["central_base_url"]
    central_handle = ArubaCentralAPI(client_id=central["client_id"],
                                     client_secret=central["client_secret"],
                                     customer_id=central["customer_id"],
                                     username=central["username"],
                                     password=central["password"],
                                     central_base_url=base_url)

    central_config = ArubaCentralConfiguration(central_handle)

    """
    # Creating a template group
    templateGroup = {"Wired": True, "Wireless": True}
    groupName = "iap-template"
    groupPass = "admin1234"
    central_config.createGroup(groupName, groupPass, templateGroup)

    # Moving IAP to a template group
    group_name = "iap-template"
    serial_list = ["CNC7J0XXXX"]
    central_config.moveDevicesToGroup(groupName=group_name,
                                      serialsList=serial_list)

    # Upload Template
    templateName = "iap-template"
    fileName = "/home/kdhandapani/Documents/central-groups/template-sample.txt"
    deviceType = "IAP"
    groupName = "iap-template"
    central_config.uploadTemplate(groupName, templateName,
                                  deviceType, fileName)

    # Upload Variable File
    fileName = "/home/kdhandapani/Documents/central-groups/\
               variable-sample.json"
    central_config.uploadVariable(fileName=fileName)

    # Create a Site
    siteName = "SantaClara-Lab"
    siteAddress = {"address": "3970 Rivermark Plaza", "city": "Santa Clara",
                   "state": "California", "country": "United States",
                   "zipcode": "95053"}
    geoLocation = {
                   "latitude": "34.8951",
                   "longitude": "-77.0364"
                  }
    central_config.createSite(siteName=siteName, geoLocation=geoLocation)

    # Add devices to a site
    deviceList = ["CNC7J0XXXX","CNC7J0XXXX","CNC7J0XXXX"]
    central_config.addDevicesToSite(siteName=siteName, deviceType="IAP",
                                    deviceSerials=deviceList)
    """

    """
    # Delete variables of devices
    deviceList = ["CNC7J0XXXX","CNC7J0XXXX","CNC7J0XXXX"]
    for deviceSerial in deviceList:
        central_config.deleteVariablesOfDevice(deviceSerial)

    # Delete the template file
    groupName = "iap-template"
    templateName = "iap-template"
    central_config.deleteTemplate(groupName=groupName,
                                  templateName=templateName)

    # Remove device from the site
    deviceType = "IAP"
    deviceSerials = ["CNC7J0XXXX","CNC7J0XXXX","CNC7J0XXXX"]
    siteName = "SantaClara-Lab"
    central_config.removeDevicesFromSite(deviceSerials, deviceType,
                                         siteName=siteName)

    # Delete Site
    siteName = "SantaClara-Lab"
    central_config.deleteSite(siteName=siteName)

    # Move devices to the default group
    central_config.moveDevicesToGroup(groupName="default",
                                      serialsList=deviceSerials)

    # Delete Group
    groupName = "iap-template"
    central_config.deleteGroup(groupName=groupName)
    """
