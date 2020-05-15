# MIT License
#
# Copyright (c) 2019 Aruba, a Hewlett Packard Enterprise company
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import json
import sys

def parse_str(str, dict, sep=','):
    toks = str.split(sep)
    ret = 0
    for tok in toks:
        tok = tok.strip()
        tok = tok.lower()
        if tok in dict:
            ret = ret | dict[tok]
    return ret

def read_jsonfile(filename):
    # Extract customer info from input JSON File
    jsondict = {}
    jsonfile = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            filename)

    if os.path.isfile(jsonfile):
        with open(jsonfile, 'r') as infile:
            try:
                jsondict = json.load(infile)
            except Exception as err:
                sys.exit("Error in Input JSON file: %s" % str(err))

        return jsondict
    else:
        sys.exit("Error: json input file not found. exiting...")

def write_jsonfile(filename, jsondict):
    jsonfile = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            filename)
    if os.path.isfile(filename):
        with open(filename, 'w') as outfile:
            json.dump(jsondict, outfile, indent=2)
        return True
    else:
        return False
