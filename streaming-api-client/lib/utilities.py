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
            jsondict = json.load(infile)
        return jsondict
    else:
        print("Error: json input file not found. exiting...")
        exit(0)

def write_jsonfile(filename, jsondict):
    jsonfile = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            filename)
    if os.path.isfile(filename):
        with open(filename, 'w') as outfile:
            json.dump(jsondict, outfile, indent=2)
    return True
