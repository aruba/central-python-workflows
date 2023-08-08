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

from pycentral.configuration import ApConfiguration as ap
import sys
import re
import copy
import pdb


class ApCLIConfig(object):
    """
    Contains functions to manage Aruba Central Access Points via CLI.
    """

    def get_ap_config(self, conn, group_name):
        """
        Get whole configuration in CLI format of an UI group or AOS10 device.

        :param conn: Instance of class:`pycentral.ArubaCentralBase`.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param group_name: Central UI groupname or serial for AOS10 device.
        :type group_name: str

        :return: List of strings in CLI format of AP configuration
        :rtype: list
        """

        # Call API
        resp = ap.get_ap_config(self, conn, group_name)
        if resp["code"] != 200:
            sys.exit(
                "Bad request for get_ap_config() response code: %d. "
                "%s. Exiting..." % resp["code"], resp["msg"]["description"])

        return resp["msg"]

    def merge_config(self, current, new):
        """
        Combine current AP configuration with additional configurations.
        the return value of get_ap_config() should be used for the current
        parameter to avoid corrupting the configuration.
        """

        result = []
        next_block = 0
        regex = re.compile('\\S')

        for line in range(len(current)):
            # Skip if context was replaced.
            if line < next_block:
                continue
            if current[line] in new:
                # Replace current context block with input from new CLI.
                if regex.match(current[line]) is not None:
                    next_block = self.get_next_context(current, line)
                    result.append(current[line])
                    new = self.copy_context(new, current[line], result)
            else:
                result.append(current[line])

        for line in new:
            result.append(line)

        return result

    def replace_config(self, conn, group_name, cli_config):
        """
        Replace whole configuration of a Central UI group.  Configuration is
        in CLI format as a list of strings.

        :param conn: Instance of class:`pycentral.ArubaCentralBase`.
        :type conn: class:`pycentral.ArubaCentralBase`
        :param group_name: Central UI groupname or serial for AOS10 device.
        :type group_name: str
        :param cli_config: CLI commands for AP configuration.
        :type cli_config: list of strings.
        """

        resp = ap.replace_ap(self, conn, group_name, cli_config)
        if resp["code"] != 200:
            sys.exit(
                "Bad request for get_ap_config() response code: %d. "
                "%s. Exiting..." % resp["code"], resp["msg"]["description"])

        return resp["msg"]

    def get_next_context(self, cli, index):
        """
        Finds the index of the start of the next context in a list of CLI
        commands.

        :param cli: A list of AP CLI commands.
        :type cli_config: list of strings.
        :param index: Starting index for cli parameter.
        :type index: int

        :return: index of the next CLI context.
        :rtype: int
        """

        # Check for out of bounds.
        if index + 1 > len(cli):
            return

        regex = re.compile('\\s\\s\\S')

        for i in range(index + 1, len(cli)):
            if regex.match(cli[i]) is None:
                return i

    def copy_context(self, cli, context, result):
        """
        Copy the commands of a CLI context into an array.

        :param cli: A list of AP CLI commands.
        :type cli_config: list of strings.
        :param context: CLI context string to copy child commands from.
        :type context: str
        :param result: result list to append commands to.
        :type result: list of strings.

        :return: modified result list with all context commands.
        :rtype: list
        """

        index = cli.index(context)
        regex = re.compile('\\s\\s\\S')
        result = copy.deepcopy(cli)

        # Check for out of bounds.
        if index + 1 > len(cli):
            return

        # Copy until next context.
        for i in range(index + 1, len(cli)):
            if regex.match(cli[i]) is None:
                break
            result.append(cli[i])
            # Cleanup input
            del result[i]

        # Cleanup input
        del result[index]
        return result
