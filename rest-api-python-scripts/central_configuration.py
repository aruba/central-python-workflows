"""
Sample python script with functions to create/update/delete groups, sites,
templates, variables and move devices to a group
"""
from central_main import ArubaCentralAPI
import re
import json


class ArubaCentralConfiguration:

    def __init__(self, deviceHandle):
        self.deviceHandle = deviceHandle

    def isExists(self, apiPath):
        # Does a HTTP GET to check if entity is present already
        # return: apiMethod "PATCH" if entity is present else returns "POST"
        try:

            resp = self.deviceHandle.command(apiMethod="GET", apiPath=apiPath)
            if resp and resp != '':
                if resp["code"] == 200 or resp["code"] == 201:
                    return "PATCH"
                else:
                    return "POST"
        except Exception as err:
            print("***Exception: Method: %s; Error: %s; apiPath: %s"
                  % ("GET", err, apiPath))

    def checkResponse(self, resp, successMsg, printResp=True):
        if resp and resp != "":
            if resp["code"] == 200 or resp["code"] == 201:
                if printResp:
                    print(resp["msg"])
                print(successMsg)
                return True
            else:
                print("Status Code: %d" % resp["code"])
                print("Message: %s" % resp["msg"])
                return False

    def delete(self, apiPath):
        apiMethod = "DELETE"
        try:
            resp = self.deviceHandle.command(apiPath=apiPath,
                                             apiMethod=apiMethod)
            if resp != '':
                if resp["code"] == 200 or resp["code"] == 201:
                    return True
                else:
                    print("Status Code: %d" % resp["code"])
                    print("Message: %s" % resp["msg"])
                    return False
        except Exception as err:
            print("***Exception: Method: %s; Error: %s; apiPath: %s"
                  % (apiMethod, err, apiPath))

    def createGroup(self, groupName, groupPass="admin1234",
                    templateGroup={"Wired": True, "Wireless": True}):

        apiData = ""
        print("Checking if group is present...")
        apiPath = "/configuration/v1/groups/" + groupName
        # apiParams = {"limit":"20", "offset":"0", "q": groupName}
        if self.isExists(apiPath=apiPath) == "PATCH":
            if templateGroup is False:
                apiData = {"group_password": groupPass,
                           "template_group": templateGroup}
                print("Patching exisiting group %s" % groupName)
                apiMethod = "PATCH"
            else:
                # Nothing to Do as template group password can't be changed
                return
        else:
            # Do a HTTP POST if the group does not exists
            apiMethod = "POST"
            apiPath = "/configuration/v2/groups"
            apiData = {"group": groupName,
                       "group_attributes": {"group_password": groupPass,
                                            "template_info": templateGroup}}

        resp = self.deviceHandle.command(apiMethod=apiMethod,
                                         apiPath=apiPath, apiData=apiData)
        if resp != '':
            if resp["code"] == 200 or resp["code"] == 201:
                print("Success: group %s" % groupName)
            else:
                print("Status Code: %d" % resp["code"])
                print("Message: %s" % resp["msg"])

    def deleteGroup(self, groupName):
        apiPath = "/configuration/v1/groups/" + groupName
        if self.delete(apiPath=apiPath):
            print("Deleted group %s" % groupName)

    def moveDevicesToGroup(self, groupName, serialsList):
        apiPath = "/configuration/v1/devices/move"
        apiMethod = "POST"
        if not isinstance(serialsList, list):
            serialsList = list(serialsList)
        apiData = {"group": groupName, "serials": serialsList}
        resp = self.deviceHandle.command(apiMethod=apiMethod,
                                         apiPath=apiPath, apiData=apiData)
        successMsg = "Moved devices to the group " + groupName
        return self.checkResponse(resp, successMsg)

    def uploadTemplate(self, groupName, templateName, deviceType,
                       fileName, version="ALL", model="ALL"):
        apiPath = "/configuration/v1/groups/" + groupName
        apiPath = apiPath + "/templates/" + templateName
        print("Checking if template is present...")
        apiMethod = self.isExists(apiPath=apiPath)

        # Open template file in binary mode
        try:
            fp = open(fileName, "rb")
            files = {"template": fp}
        except Exception:
            raise

        resp = ''
        apiPath = "/configuration/v1/groups/" + groupName
        apiPath = apiPath + "/templates"
        apiParams = {"name": templateName, "device_type": deviceType,
                     "version": version, "model": model}
        resp = self.deviceHandle.command(apiMethod=apiMethod, apiPath=apiPath,
                                         apiParams=apiParams, files=files,
                                         headers="")
        if resp != '':
            if resp["code"] == 200 or resp["code"] == 201:
                print("Success: template %s added to group %s"
                      % (templateName, groupName))
            else:
                print("Status Code: %d" % resp["code"])
                print("Message: %s" % resp["msg"])

    def deleteTemplate(self, groupName, templateName):
        apiPath = "/configuration/v1/groups/" + groupName
        apiPath = apiPath + "/templates/" + templateName
        if self.delete(apiPath=apiPath):
            print("Deleted template %s from group %s"
                  % (templateName, groupName))

    def uploadVariable(self, fileName=None,
                       device_serial=None, variables=None):
        # Expects template variables or file in JSON format.
        # If fileName is not provided,
        #    (device_serial and variables) are expected.
        # Sample variable file in JSON format can be downloaded from central
        # if device_serial is provided in the argument, variables to be updated
        # for that device should be provided in JSON format
        # {"_sys_serial": "CJ0219729",
        #  "ssid": "s1",
        #  "_sys_lan_mac": "ac:a3:1e:cb:04:92",
        #  "vc_name": "test_config_CK0036968",
        #  "org": "Uber_org_test",
        #  "vc_dns_ip":"22.22.22.22",
        #  "zonename": "Uber_1",
        #  "uplinkvlan": "0",
        #  "swarmmode": "cluster",
        #  "md5_checksum": "ed8a67a3d1be58261640ca53f8fd3bb8",
        #  "hostname": "Uber_2"
        # }
        #
        print("Uploading Variables to template group")
        template_format = "JSON"
        responses = []
        # To update variables for multiple devices supply a JSON file
        if fileName:
            # Open template variable file
            try:
                fp = open(fileName, "rb")
                files = {"variables": fp}
            except Exception:
                raise
            # Uploading template variables as a file does not throw an error
            # when device is not present under the customer
            # As a workaround, make POST for every device mentioned in the file
            '''
            apiPath = "/configuration/v1/devices/template_variables"
            apiParams = {"format": template_format}
            apiMethod = "POST"
            resp  = self.deviceHandle.command(apiMethod=apiMethod,
                                              apiPath=apiPath,
                                              apiParams=apiParams,
                                              files=files, headers="")
            '''
            apiMethod = "POST"

            # Make post for every device in the JSON file
            fp_data = fp.read()
            fp_dict = json.loads(fp_data)
            for device_serial, variables in fp_dict.items():
                apiData = {"variables": variables}
                apiPath = "/configuration/v1/devices/" + device_serial
                apiPath = apiPath + "/template_variables"
                if self.isExists(apiPath):
                    apiMethod = "PATCH"
                responses.append(self.deviceHandle.command(apiMethod=apiMethod,
                                                           apiPath=apiPath,
                                                           apiData=apiData))

        elif device_serial:
            if not variables:
                print("Exception.. Skipping variable update:: Provide \
                      variables in JSON format for this device %s"
                      % device_serial)
            else:
                apiPath = "/configuration/v1/devices/" + device_serial
                apiPath = apiPath + "/template_variables"
                apiData = {"variables": variables}
                if self.isExists(apiPath):
                    apiMethod = "PATCH"
                responses.append(self.deviceHandle.command(apiMethod=apiMethod,
                                                           apiPath=apiPath,
                                                           apiData=apiData))

        for resp in responses:
            if resp["code"] == 200 or resp["code"] == 201:
                # print("Successfully added template variables")
                pass
            else:
                print("Status Code: %d" % resp["code"])
                print("Message: %s" % resp["msg"])

    def deleteVariablesOfDevice(self, deviceSerial):
        apiPath = "/configuration/v1/devices/" + deviceSerial
        apiPath = apiPath + "/template_variables"
        if self.delete(apiPath=apiPath):
            print("Deleted variables of the device %s" % deviceSerial)

    def findSiteId(self, siteName):
        apiPath = "/central/v2/sites"
        apiMethod = "GET"
        apiData = {"calculate_total": True, "limit": 1000}
        resp = self.deviceHandle.command(apiMethod=apiMethod,
                                         apiPath=apiPath, apiData=apiData)
        successMsg = "Checking list of sites to match with the siteName "
        successMsg = successMsg + siteName
        if self.checkResponse(resp, successMsg, printResp=False):
            resp = json.loads(resp["msg"])
            for site in resp["sites"]:
                if site["site_name"] == siteName:
                    print("Found siteId for the siteName %s" % siteName)
                    return site["site_id"]
            print("Please provide an existing siteName")
            return False

    def createSite(self, siteName, siteAddress=None, geoLocation=None):
        # Sample site_address in Dictionary format
        #   "site_address": {
        #        "address": "3970 Rivermark Plaza",
        #        "city": "Santa Clara",
        #        "state": "California",
        #        "country": "United States",
        #        "zipcode": "95053"
        #    }
        #   "geolocation": {
        #        "latitude": "38.8951",
        #        "longitude": "-77.0364"
        #    }
        apiPath = "/central/v2/sites"
        apiMethod = "POST"
        siteId = self.findSiteId(siteName)
        if siteId:
            apiPath = "/central/v2/sites/" + str(siteId)
            apiMethod = "PATCH"
        apiData = {"site_name": siteName}
        if siteAddress:
            apiData.update({"site_address": siteAddress})
        if geoLocation:
            apiData.update({"geolocation": geoLocation})

        resp = self.deviceHandle.command(apiMethod=apiMethod,
                                         apiPath=apiPath, apiData=apiData)
        successMsg = "Site " + siteName + " updated/created!"
        return self.checkResponse(resp, successMsg)

    def deleteSite(self, siteId=None, siteName=None):
        if not siteId and not siteName:
            print("Provide siteId or siteName to delete")
            return False
        elif siteName:
            siteId = self.findSiteId(siteName)
            if not siteId:
                return False
        apiPath = "/central/v2/sites/" + str(siteId)
        if self.delete(apiPath=apiPath):
            print("Deleted the site %s" % siteName)
            return True

    def addDevicesToSite(self, deviceSerials, deviceType,
                         siteId=None, siteName=None):
        """
        deviceSerials: Type list (required)
        siteId: Type integer (if optional, siteName is required)
        siteName: Type string (if optional, siteId is required)
        """
        apiPath = "/central/v2/labels/associations"
        apiMethod = "POST"
        if not siteId:
            if siteName:
                siteId = self.findSiteId(siteName)
            else:
                print("Provide siteId or siteName to add device to the site")
                return False
        if siteId:
            apiData = {"device_ids": deviceSerials,
                       "device_type": deviceType,
                       "label_id": siteId}
            resp = self.deviceHandle.command(apiMethod=apiMethod,
                                             apiPath=apiPath,
                                             apiData=apiData)
            successMsg = "Added devices to the site" + str(siteId)
            return self.checkResponse(resp, successMsg)

    def removeDevicesFromSite(self, deviceSerials, deviceType,
                              siteId=None, siteName=None):
        """
        deviceSerials: Type list (required)
        siteId: Type integer (if optional, siteName is required)
        siteName: Type string (if optional, siteId is required)
        """
        apiPath = "/central/v2/labels/associations"
        apiMethod = "DELETE"
        if not siteId:
            if siteName:
                siteId = self.findSiteId(siteName)
            else:
                print("Provide siteId or siteName to delete device \
                      from the site")
                return False
        if siteId:
            apiData = {"device_ids": deviceSerials,
                       "device_type": deviceType, "label_id": siteId}
            resp = self.deviceHandle.command(apiMethod=apiMethod,
                                             apiPath=apiPath, apiData=apiData)
            successMsg = "Deleted devices from the site" + str(siteId)
            return self.checkResponse(resp, successMsg)

    def modifyUser(self, apiData, apiParams):
        apiPath = "/accounts/v2/users/" + urlencode(apiParams)
        apiMethod = "PATCH"
        resp = self.deviceHandle.command(apiPath=apiPath,
                                         apiData=apiData, apiMethod=apiMethod)
        successMsg = "Modified Central User " + apiParams + " successfully"
        return self.checkResponse(resp, successMsg)

    def setCountryCode(self, apiData):
        apiPath = "/configuration/v1/country"
        apiMethod = "PUT"
        resp = self.deviceHandle.command(apiPath=apiPath,
                                         apiData=apiData, apiMethod=apiMethod)
        successMsg = "Modified country code successfully"
        return self.checkResponse(resp, successMsg)
