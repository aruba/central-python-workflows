"""
This is a sample python script to act as a websocket client inorder to stream
data from Aruba Central Streaming API. Only one topic/subject can be streamed
with this script. However multiple websocket connections or multiple
instances of this script can be run with different topics.

For Presence Topic, the script will create a csv file and log the streaming
API data.
"""
import argparse
import os
import sys
import json
import pprint
import ssl
import time
import threading

from websocket import create_connection
from google.protobuf import text_format
from google.protobuf.message import DecodeError
import gevent
from gevent import monkey, pool

from proto import streaming_pb2
from arubaExport import presenceExport as pe
from arubaExport import writeThread
from excelUpdate import exportToFile

monkey.patch_all()

services_dict = {
    'monitoring': 1,
    'apprf': 2,
    'presence': 4,
    'audit': 8
}

filter_dict = {
    'clients': 1,
    'aps': 2,
    'switches': 4,
    'controllers': 8,
    'devices': 16,
    'locations': 32,
    'destinations': 64,
    'applications': 128,
    'security': 256,
    'events': 512,
    'notifications': 1024

}
message_count = 0
truncated_message_count = 0


def StreamClient(ip, username, password, param_dict,
                 services, filters, secure_url):
    """
    Summary: Websocket Client to stream data from Aruba Central Streaming API.

    Parameters:
        ip (str): hostname of Aruba Central Website
        username (str): username of Aruba Central User
        password (str): Secure WebSocket key obtained from Streaming
                        API page of Aruba Central
        param_dict (dict): A python dictionary with required key-value
                           pairs such as topic to subscribe and many more
        services (int): Mask value to enable certain services
        filters (int): Mask value to set certain filters
        secure_url (bool): True/False will determine whether WSS or WS
    """
    global message_count, truncated_message_count
    if secure_url:
        proto = "wss"
    else:
        proto = "ws"
    origin = "{}://{}".format(proto, ip)
    if param_dict['type'] == 'streams':
        url = "{}://{}/streaming/api".format(proto, ip)
    else:
        url = None
    if url is None:
        return

    print("URL: {}".format(url))
    print("ORIGIN: {}".format(origin))

    header = {}
    msg_decoder = None
    # Choosing the which message of the proto file needs to be decoded
    # based on the chosen topic/subject.
    # To subscribe to a different message, refer proto file.
    # The imported files are python compiled proto files.
    if 'X-Subject' in param_dict and param_dict['X-Subject'] is not None:
        header["Topic"] = param_dict['X-Subject']
        if header["Topic"] == "monitoring":
            from proto import monitoring_pb2
            msg_decoder = monitoring_pb2.MonitoringInformation()
        elif header["Topic"] == "apprf":
            from proto import apprf_pb2
            msg_decoder = apprf_pb2.apprf_session()
        elif header["Topic"] == "presence":
            from proto import presence_pb2
            msg_decoder = presence_pb2.presence_event()
        elif header["Topic"] == "audit":
            from proto import audit_pb2
            msg_decoder = audit_pb2.audit_message()
        elif header["Topic"] == "location":
            from proto import location_pb2
            msg_decoder = location_pb2.stream_location()
        elif header["Topic"] == "rapids":
            from proto import rapids_pb2
            msg_decoder = rapids_pb2.RogueEvent()

    # Constructing Headers
    if ('X-Deliver-All' in param_dict and
       param_dict['X-Deliver-All'] is not None):
        header["X-Deliver-All"] = param_dict['X-Deliver-All']

    if 'X-Start-Seq' in param_dict and param_dict['X-Start-Seq'] is not None:
        header["X-Start-Seq"] = param_dict['X-Start-Seq']

    if ('X-Deliver-Last' in param_dict and
       param_dict['X-Deliver-Last'] is not None):
        header["X-Deliver-Last"] = param_dict['X-Deliver-Last']

    if 'X-Since-Time' in param_dict and param_dict['X-Since-Time'] is not None:
        header["X-Since-Time"] = param_dict['X-Since-Time']
    header["Authorization"] = password
    header["UserName"] = username
    # header2 = json.dumps(header)
    print("HEADER:")
    pprint.pprint(header)

    # Creating a websocket connection
    print("CREATE CONNECTION...")
    if secure_url:
        client = create_connection(url, header=header,
                                   sslopt={"cert_reqs": ssl.CERT_NONE,
                                           "check_hostname": False})
    else:
        client = create_connection(url, header=header)
    print("start" + str(time.time()))
    if not client:
        raise RuntimeError('Web socket connection is closed.')

    c = 0
    try:
        # If the presence topic is chosen, create a csv file
        # with column names for storing data
        exportData = None
        write_threads = []
        if header["Topic"] == "presence":
            fileName = "central_streaming"
            fileType = None
            filePath = None
            if 'addtofilename' in param_dict:
                fileName = param_dict['addtofilename']
            if 'filepath' in param_dict:
                filePath = param_dict['filepath']
            if 'filetype' in param_dict:
                fileType = param_dict['filetype']
            exportData = pe(topic=header["Topic"],
                            fileName=fileName,
                            filePath=filePath,
                            fileType=fileType)
            exportData.createProximityCol()

        # Create an infinite loop to stream indefinitely
        while True:
            msg = client.recv()
            if param_dict['sleep'] > 0:
                gevent.sleep(param_dict['sleep'])

            # Constructing a Protobuf decoder
            if param_dict['do_decode'] is True:

                try:
                    if param_dict['type'] == 'events':
                        msg_decoder.ParseFromString(msg)
                        pprint.pprint(msg_decoder)

                    elif (param_dict['type'] ==
                          'streams'):
                        #  Two steps decoding, once for the data
                        #  received from Aruba Central and another
                        #  to decode data of the subscribed topic
                        #  1. Decoding the streaming message
                        #  received from Aruba Central using compiled
                        #  proto file
                        print("Decoding the streammsg")
                        msgp = streaming_pb2.MsgProto()
                        msgp.ParseFromString(msg)
                        # text_format.Merge(msg, msgp)
                        # pprint.pprint(msgp)
                        if param_dict['do_decode']:
                            # 2. Using the decoder specific to the subscribed
                            # topic to decode data of received streaming
                            # proto message.
                            msg_decoder.ParseFromString(msgp.data)
                            pprint.pprint(msg_decoder)
                            # Export Decoded proto message
                            if header["Topic"] == "presence":
                                dataList = pe.extractProximityData(msg_decoder)
                                if dataList:
                                    t = writeThread(exportData, dataList)
                                    t.start()
                                    write_threads.append(t)
                    else:
                        # pprint.pprint(msg)
                        pass

                except DecodeError as e:
                    print("Decode Error: ", e)
                    if "Truncated" in str(e):
                        truncated_message_count += 1
                except Exception as e:
                    print("Exception Received: ", e)
            else:
                pprint.pprint(msg)

            message_count += 1
            if message_count % 100 == 0:
                print("Message Received : " + str(message_count))
                if truncated_message_count > 0:
                    print("Truncated Messages Received : "
                          + str(truncated_message_count))
            if param_dict['count'] > 0:
                if message_count == param_dict['count']:
                    client.close()
                    break
            if msg is None:
                client.close()
                break
        for t in write_threads:
            t.join()
    except Exception as e:
        print("end" + str(time.time()))
        print("Total Message Received : " + str(message_count))
        if truncated_message_count > 0:
            print("Total Truncated Messages Received : "
                  + str(truncated_message_count))
        print("connection closed.error.." + e.message)


def parse_str(str, dict, sep=','):
    toks = str.split(sep)
    ret = 0
    for tok in toks:
        tok = tok.strip()
        tok = tok.lower()
        if tok in dict:
            ret = ret | dict[tok]
    return ret


if __name__ == '__main__':

    # Parsing script arguments
    parser = argparse.ArgumentParser(description='........ \
             Websocket Client App for Aruba Cloud API Streaming .....')
    parser.add_argument('--hostname', required=True,
                        help='Websocket server host')
    parser.add_argument('--jsoninput',
                        required=True,
                        help='Json input files containing customer details')
    parser.add_argument('--services', required=False,
                        help='Service to be subscribed - integer or comma \
                        separated string like "monitoring,apprf,\
                        presence" (default: 65535)')
    parser.add_argument('--filters', required=False,
                        help='fileters to be applied on services -integer \
                        or comma separated string like "clients,aps,switches"\
                        (default: 65535)')

    parser.add_argument('--subject', required=True,
                        help='X-Subject to be set in header \
                        "monitoring|apprf|presence"')
    parser.add_argument('--start_seq', required=False,
                        help='a valid sequence number to start getting \
                        events from that sequence (optional)')
    parser.add_argument('--deliver_last', required=False,
                        help='X-Deliver-Last get latest events (Optional)',
                        action='store_true')
    parser.add_argument('--deliver_all', required=False,
                        help='Deliver-All get all events(optional)',
                        action='store_true')
    parser.add_argument('--since_time', required=False,
                        help='X-Since-Time receive events after the time \
                        stamp in predefined string format like 1h, 5m, 10s \
                        etc (optional)')
    parser.add_argument('--non_secure_url', required=False,
                        help='do ws connection insted of wss',
                        action='store_true')
    parser.add_argument('--type', required=True,
                        help='type of url location (stream | event)')
    parser.add_argument('--multiplier', required=False,
                        help='connection multiplier count (Default:1)')
    parser.add_argument('--do_decode',
                        required=False,
                        help="Do decode of the received mesages",
                        action='store_true')

    parser.add_argument('--count', required=False,
                        help='receive number of message per stream \
                        -default(0:all)')
    parser.add_argument('--sleep', required=False,
                        help='sleep in seconds between receive msgs to \
                        simulate slow client simulation -default(0:all)')

    args = parser.parse_args()

    if args.services is not None:
        if args.services.isdigit():
            services = int(args.services)
        else:
            services = parse_str(args.services, services_dict)
    else:
        services = 65535

    if args.filters is not None:
        if args.filters.isdigit():
            filters = int(args.filters)
        else:
            filters = parse_str(args.filters, filter_dict)

    else:
        filters = 65535

    if args.non_secure_url:
        secure_url = False
    else:
        secure_url = True

    param_dict = {}

    if args.subject is None:
        print("subject is not specified. exiting..")
        exit(0)
    if args.subject not in ['monitoring', 'apprf', 'presence',
                            'audit', 'location', 'rapids']:
        print("unknown subject specified")
        exit(0)
    param_dict['X-Subject'] = args.subject

    if args.type is None:
        print("type is not specified. exiting..")
        exit(0)
    if args.type not in ['streams', 'events']:
        print("Invalid request type : should be streams or events...")
        exit(0)
    param_dict['type'] = args.type

    jsonfile = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            args.jsoninput)
    if os.path.isfile(jsonfile):
        with open(jsonfile, 'r') as infile:
            jsondict = json.load(infile)
            param_dict['customerlist'] = jsondict['customerlist']
        if jsondict is not None:
            if 'customerlist' in jsondict:
                param_dict['customerlist'] = jsondict['customerlist']
            else:
                print("json file does not have customer dict.exiting...")
                exit(0)
            if args.subject == "presence":
                if 'addtofilename' in jsondict:
                    param_dict['addtofilename'] = jsondict['addtofilename']
                if 'filepath' in jsondict:
                    param_dict['filepath'] = jsondict['filepath']
                else:
                    print("filepath not present in json file... \
                           Choosing default path for logging data \
                           <current_dir>/logs")
                if 'filetype' in jsondict:
                    param_dict['filetype'] = jsondictp['filetype']
                else:
                    print("filetype not present in json file... \
                          Choosing default type for file \"csv\"")
    else:
        print("json input file not found. exiting...")
        exit(0)

    if args.start_seq is not None:
        param_dict['X-Start-Seq'] = int(args.start_seq)
    else:
        param_dict['X-Start-Seq'] = None

    if args.deliver_last:
        param_dict['X-Deliver-Last'] = "true"
    else:
        param_dict['X-Deliver-Last'] = None

    if args.deliver_all:
        param_dict['X-Deliver-All'] = "true"
    else:
        param_dict['X-Deliver-All'] = None

    if args.since_time is not None:
        param_dict['X-Since-Time'] = args.since_time
    else:
        param_dict['X-Since-Time'] = None

    if args.multiplier is not None:
        param_dict['multiplier'] = int(args.multiplier)

    else:
        param_dict['multiplier'] = 1

    if args.count is not None:
        param_dict['count'] = int(args.count)

    else:
        param_dict['count'] = 0

    if args.sleep is not None:
        param_dict['sleep'] = int(args.sleep)

    else:
        param_dict['sleep'] = 0

    if args.do_decode:
        param_dict['do_decode'] = True
    else:
        param_dict['do_decode'] = False

    pprint.pprint("Websocket server to connect : {}".format(args.hostname))
    pprint.pprint("Services : {}".format(args.services))
    pprint.pprint("Filters : {}".format(args.filters))
    pprint.pprint("secure url : {}".format(secure_url))
    pprint.pprint("other Paramters :")
    pprint.pprint(param_dict)

    # Creating gevent pool and spawing asynchronous concurrent tasks
    # based on customer list in input file
    # All customers will subsribe to same topic as provided in script
    # argument during execution
    jobs = []
    p = pool.Pool(len(param_dict['customerlist']) * param_dict['multiplier'])

    for i in range(param_dict['multiplier']):
        for customer in param_dict['customerlist']:
            if len(customer) >= 2 and param_dict['type'] == 'streams':
                jobs.append(
                    p.spawn(StreamClient, args.hostname, customer[0],
                            customer[1], param_dict, services, filters,
                            secure_url))
            else:
                print("Invalid json file and type combination.exiting...")
                exit(0)
    try:
        gevent.joinall(jobs)
    except KeyboardInterrupt:
        print("Total Message Received : " + str(message_count))
        if truncated_message_count > 0:
            print("Total Truncated Messages Received : "
                  + str(truncated_message_count))
        p.kill()
    except Exception:
        print("Total Message Received : " + str(message_count))
        if truncated_message_count > 0:
            print("Total Truncated Messages Received : "
                  + str(truncated_message_count))
        raise
