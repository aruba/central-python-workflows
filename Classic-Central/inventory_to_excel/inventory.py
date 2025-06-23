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

from pycentral.new_device_inventory import Inventory
import xlsxwriter
import csv as c
import sys


class InventoryToExcel(object):
    """
    Contains functions to create excel files from device inventory data.
    """

    def devices_to_excel(self, conn, sku_type='all', csv=False,
                         filename="inventory", limit=0, offset=0):
        """Create excel document with target sku_type devices from inventory.
        Excel document is created in working directory.

        :param conn: Instance of class:`pycentral.ArubaCentralBase`.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param sku_type: target device sku type to pull from inventory.
            Acceptable arguments: all, iap, switch, controller, gateway,
            vgw, cap, boc, all_ap, all_controller, others.
        :type sku_type: str
        :param csv: Flag to change output to csv.
        :type csv: bool
        :param filename: filename for created document.
        :type filename: str, optional
        :param limit: Pagination limit. Defaults to 0, which is intrepreted as
            get all. Maximum limit per request is 50.
        :type limit: int, optional
        :param offset: Pagination offset, defaults to 0.
        :type offset: int, optional
        """

        # Call API
        get_resp = Inventory.get_inventory(
            self, conn, sku_type, limit=limit, offset=offset)
        if get_resp["code"] != 200:
            sys.exit(
                "Bad request for get_inventory() response code: %d. "
                "Check parameters. Exiting..." % get_resp["code"])

        # Assign data from response.
        device_list = get_resp["msg"]["devices"]
        device_total = get_resp["msg"]["total"]
        if len(device_list) != 0:
            col_keys = list(device_list[0].keys())
        else:
            sys.exit("No devices found matching specifications. Exiting...")

        # Handle total devices greater than max limit.
        if limit == 0:
            while len(device_list) < device_total:
                # Increment pagination offset.
                offset += 50
                # Get next set of devices.
                get_resp = Inventory.get_inventory(
                    self, conn, sku_type, limit=limit, offset=offset)
                if get_resp["code"] != 200:
                    sys.exit(
                        "Bad request for get_inventory() response code: %d. "
                        "Check parameters. Exiting..." % get_resp["code"])

                # Add new set of devices to device_list.
                device_list.append(get_resp["msg"]["devices"])

        # Setup doc headers and filetype.
        col_headers = ["Aruba Part Number", "Customer ID", "Customer Name",
                       "Device Type", "IMEI", "Mac Address", "Model",
                       "Serial", "Services", "Subscription Key", "Tier Type"]
        filename = (filename + '.csv') if csv else (filename + '.xlsx')

        if not csv:
            # Create excel file, worksheet, and formatting.
            workbook = xlsxwriter.Workbook(filename)
            worksheet = workbook.add_worksheet()
            bold = workbook.add_format({'bold': True})

            # Setup headers and coordinates.
            for i in range(len(col_headers)):
                worksheet.write(0, i, col_headers[i], bold)
            row, col = 1, 0

            # Write device info to cells.
            for device in device_list:
                for key in col_keys:
                    # Switch to proper format for writing.
                    match device[key]:
                        case str():
                            worksheet.write(row, col, device[key])
                        case list():
                            data = ', '.join(device[key])
                            worksheet.write(row, col, data)
                        case _:
                            worksheet.write(row, col, 'null')
                    col += 1

                row += 1
                col = 0

            worksheet.autofit()
            workbook.close()
        else:
            # Open csv file and setup writer.
            with open(filename, 'w', newline='') as csvfile:
                writer = c.DictWriter(csvfile, fieldnames=col_keys)

                # Write to csv.
                writer.writeheader()
                for device in device_list:
                    writer.writerow(device)
