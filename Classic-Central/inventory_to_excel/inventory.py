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

from pycentral.device_inventory import Inventory
import xlsxwriter
import csv as c
import sys

MAX_LIMIT = 1000


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

        if limit == 0:
            raise ValueError(
                "limit=0 (fetch all) is not supported in this workflow. Please specify a positive limit."
            )

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

        # Setup doc headers and filetype.
        # Use the device keys as headers to keep header columns aligned with values.
        col_headers = [k.replace('_', ' ').title() for k in col_keys]
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

            # Prepare column width tracking (start with header widths).
            col_widths = [len(str(h)) for h in col_headers]

            # Write device info to cells and track max width per column.
            for device in device_list:
                for idx, key in enumerate(col_keys):
                    value = device.get(key, None)
                    if isinstance(value, str):
                        out = value
                    elif isinstance(value, list):
                        out = ", ".join([str(x) for x in value])
                    elif value is None:
                        out = "null"
                    else:
                        out = str(value)

                    worksheet.write(row, idx, out)
                    # update width
                    col_widths[idx] = max(col_widths[idx], len(out))

                row += 1

            # Apply reasonable column widths (add padding).
            for i, w in enumerate(col_widths):
                width = min(max(w + 2, 8), 60)
                worksheet.set_column(i, i, width)

            workbook.close()
        else:
            # Open csv file and setup writer.
            with open(filename, "w", newline="") as csvfile:
                writer = c.DictWriter(csvfile, fieldnames=col_headers)

                # Write to csv.
                writer.writeheader()
                for device in device_list:
                    row_dict = {h: device.get(k, "") for h, k in zip(col_headers, col_keys)}
                    writer.writerow(row_dict)
