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

import websocket
import _thread
import time
from proto import streaming_pb2

def on_message(ws, message):
    # Decode Message in Serialized protobuffer
    stream_data = streaming_pb2.MsgProto()
    stream_data.ParseFromString(message)
    print("Timestamp in Epoch: %s" % str(stream_data.timestamp))
    print("Customer_ID: %s" % str(stream_data.customer_id))
    # Based on the topic import compiled proto file and decode 'data' field
    from proto import monitoring_pb2
    monitoring_data = monitoring_pb2.MonitoringInformation()
    monitoring_data.ParseFromString(stream_data.data)

    print(monitoring_data)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        print("Start Streaming Data!")
    _thread.start_new_thread(run, ())


if __name__ == "__main__":
    # URL for WebSocket Connection from Streaming API page
    hostname = "internal-ui.central.arubanetworks.com"
    url = "wss://{}/streaming/api".format(hostname)
    # Construct Header for WebSocket Connection
    header = {}
    # Central User email
    header["UserName"] = "abc@gmail.com"
    # WebSocket Key from Streaming API Page
    header["Authorization"] = "XXXXXX"
    # Subscription TOPIC for Streaming API
    # (audit|apprf|location|monitoring|presence|security)
    header["Topic"] = "monitoring"
    # Create WebSocket connection
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(url=url,
                                header=header,
                                on_message = on_message,
                                on_error = on_error,
                                on_close = on_close)
    ws.on_open = on_open
    ws.run_forever()
