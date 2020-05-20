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
