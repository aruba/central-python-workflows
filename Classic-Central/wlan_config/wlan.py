# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from pycentral.configuration import Wlan
import sys


class WlanConfig(object):
    """
    Contains functions to manage Aruba Central WLANs.
    """

    def create_ssid(self, conn, target, wlan_data):
        """
        Create new ssid at target.

        :param conn: Instance of class:`pycentral.ArubaCentralBase` to make an
            API call.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param wlan_data: SSID config data.
        :type wlan_data: json
        """

        if target == "":
            sys.exit("Invalid value for 'target'.  Please add a valid target"
                     " and run again.")

        resp = Wlan.create_wlan(self, conn, group_name=target,
                                wlan_name=wlan_data["wlan"]["essid"],
                                wlan_data=wlan_data)

        if resp["code"] != 200:
            print("Bad request for create_wlan() SSID: %s at target: %s,"
                  " response code: %d. %s" %
                  (wlan_data["wlan"]["essid"], target, resp["code"],
                   resp["msg"]["description"]))
        else:
            print("Successfully created SSID: %s at %s" %
                  (wlan_data["wlan"]["essid"], target))

    def create_full_ssid(self, conn, target, name, wlan_data):
        """
        Create new fully configurable ssid at target.

        :param conn: Instance of class:`pycentral.ArubaCentralBase` to make an
            API call.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param wlan_data: SSID config data.
        :type wlan_data: json
        """

        if target == "":
            sys.exit("Invalid value for 'target'.  Please add a valid target"
                     " and run again.")

        resp = Wlan.create_full_wlan(self, conn, group_name=target,
                                     wlan_name=name,
                                     wlan_data=wlan_data)

        if resp["code"] != 200:
            print("Bad request for create_full_wlan() SSID: %s at target: %s,"
                  " response code: %d. %s" % (name, target, resp["code"],
                                              resp["msg"]["description"]))
        else:
            print("Successfully created SSID: %s at %s" %
                  (name, target))

    def delete_ssid(self, conn, target, ssid):
        """
        Delete ssid at target provided in wlan_data.

        :param conn: Instance of class:`pycentral.ArubaCentralBase` to make an
            API call.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param wlan_data: SSID config data.
        :type wlan_data: json
        """

        if target == "":
            sys.exit("Invalid value for 'target'.  Please add a valid target"
                     " and run again.")

        resp = Wlan.delete_wlan(self, conn, target, ssid)

        if resp["code"] != 200:
            print(
                "Bad request for delete_wlan() response code: %d. "
                "%s" % (resp["code"], resp["msg"]["description"]))
        else:
            print("Successfully deleted SSID: %s at %s" %
                  (ssid, target))

    def delete_all(self, conn, target):
        """
        Delete all SSIDs at target Central group.

        :param conn: Instance of class:`pycentral.ArubaCentralBase` to make an
            API call.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param target: Cerntral group name
        :type target: str
        """

        # Get all SSIDs from target Central group.
        ssid_res = Wlan.get_all_wlans(self, conn, target)
        if ssid_res["code"] != 200:
            print(
                "Bad request for get_all_wlans() response code: %d. "
                "%s" % (ssid_res["code"], ssid_res["msg"]["description"]))
        else:
            print("Successfully retrieved SSIDs from %s" %
                  (target))

        # Set SSID data.
        ssid_list = ssid_res["msg"]["wlans"]

        # Delete all SSIDs in ssid_list.
        for ssid in ssid_list:
            resp = Wlan.delete_wlan(self, conn, target, ssid["essid"])
            if resp["code"] != 200:
                print(
                    "Bad request for delete_wlan() response code: %d. "
                    "%s" % (resp["code"], resp["msg"]["description"]))
            else:
                print("Successfully deleted SSID: %s at %s" %
                      (ssid, target))

    def get_config(self, conn, target, name):
        """
        Gets full configuration of a WLAN in a Central group.

        :param conn: Instance of class:`pycentral.ArubaCentralBase` to make an
            API call.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param group_name: Group name of the group or guid of the swarm.
        :type group_name: str
        :param wlan_name: Name string for wlan to get.
        :type wlan_name: str

        :return: Encoded JSON string of WLAN data.
        :rtype: str
        """

        resp = Wlan.get_wlan(self, conn, target, name)

        if resp["code"] != 200:
            print(
                "Bad request for get_wlan() response code: %d. "
                "%s" % (resp["code"], resp["msg"]["description"]))

        return resp
