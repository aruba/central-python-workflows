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

import re
import json
import csv
import sys
import threading
from pprint import pprint
from google.protobuf import json_format
from proto import streaming_pb2
from proto.monitoring_pb2 import MonitoringInformation
from proto.apprf_pb2 import apprf_session
from proto.presence_pb2 import presence_event
from proto.audit_pb2 import audit_message
from proto.location_pb2 import stream_location
from proto.security_pb2 import RapidsStreamingEvent

threadLock = threading.Lock()

class Decoder():
    def __init__(self, topic):
        self.event_decoder = self.get_message_decoder(topic)
        self.topic = topic

    def get_message_decoder(self, topic):
        """
        This function returns the decoder based on subscription topic of
        streaming API. The decoder decodes message based on compiled proto files.
        """
        decoder = None
        if topic == "apprf":
            decoder = apprf_session()
        elif topic == "audit":
            decoder = audit_message()
        elif topic == "location":
            decoder = stream_location()
        elif topic == "monitoring":
            decoder = MonitoringInformation()
        elif topic == "presence":
            decoder = presence_event()
        elif topic == "security":
            decoder = RapidsStreamingEvent()
        return decoder

    def decodeData(self, msg):
        """
        This function decodes the received streaming API data from protobuf
        to python dictionary using the compiled proto definition.

        Params:
            msg: Streaming API message in google protobuf format.
        Returns:
            stream_info (dict): A Python dictionary to represent received data.
        """
        stream_info = {}
        try:
            # Decode Streaming data
            stream_data = streaming_pb2.MsgProto()
            stream_data.ParseFromString(msg)
            stream_info = {
                "topic": stream_data.subject,
                "timestamp": stream_data.timestamp,
                "customer_id": stream_data.customer_id,
                "data": stream_data.data,
                "msp_ip": stream_data.msp_id
            }
        except Exception as e:
            raise e

        try:
            if stream_info:
                data_decoder = self.event_decoder
                data_decoder.ParseFromString(stream_info["data"])
                stream_info["data"] = json_format.MessageToDict(data_decoder, preserving_proto_field_name=True)
            return stream_info
        except Exception as e:
            print("Exception Received for customer " +
                  "%s: %s" % (self.topic, str(e)))

class presenceExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class securityExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class monitoringExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class locationExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class apprfExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class auditExport():
    def __init__(self, topic, export_type):
        self.export_type = export_type
        self.subject = topic
        self.decoder = Decoder(topic)

    def processor(self, data):
        """
        A function to process the received data and provide means for data
        transport/storage.
        """
        streaming_data = self.decoder.decodeData(data)
        # Add Your code here to process data and handle transport/storage

class dataHandler ():
    def __init__(self, msg, class_inst_obj):
        self.msg = msg
        self.class_inst_obj = class_inst_obj

    def run(self):
        """
        This function runs the processor of mentioned class obj.
        """
        self.class_inst_obj.processor(self.msg)

class writeThread (threading.Thread):
    """
    A Class inherited from threading package in python to be used during
    streaming API data processing.
    """
    def __init__(self, msg, class_inst_obj):
        threading.Thread.__init__(self)
        self.msg = msg
        self.class_inst_obj = class_inst_obj

    def run(self):
        threadLock.acquire()
        # Add your task
        threadLock.release()
