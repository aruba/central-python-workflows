# Streaming API Client

### **[Download as Zip File](https://downgit.github.io/#/home?url=https://github.com/aruba/central-examples-only/tree/master/streaming-api-client)**

Aruba Central streaming API follows publish–subscribe model where a topic is subscribed from WebSocket client and Aruba Central will publish continuous data streams to WebSocket client. This approach is different from "polling" where frequent HTTP requests to REST API endpoints are required, in order to get latest data from Aruba Central.

This sample python script acts as a WebSocket client for Aruba Central streaming API and packs some useful features for reference and trying out streaming api. This script is NOT a production quality script and should be used with your discretion. Take additional care to store the WebSocket key securely.

### Data Format

Data from Aruba Central will be in Google Protocol Buffer format. Most current proto files can be downloaded from the Aruba Central's Streaming API Page. Since the python programming language is used, the python based Google Proto Compiler was used to compile "*.proto" files to "*_pb2.py" files. [Link to compiled pb2 files in ubuntu X64 machine](/streaming-api-client/proto).

Upon running the script, if there are issues in decoding the output in human readable format try re-compiling the file in your machine. More info on compiling proto files [can be found here](https://developers.google.com/protocol-buffers/docs/pythontutorial#compiling-your-protocol-buffers).

### Validate WebSocket Key

WebSocket key obtain from Aruba Central `Account Home -> Webhooks -> Streaming -> Key` expires every 7 days. The WebSocket key is renewed by Aruba Central internally. To obtain the renewed WebSocket key programmatically without having to visit the WebUI, a REST API endpoint is available. This API accepts a WebSocket key and validates it. It returns the same key if it is valid otherwise returns the renewed key.

Please Note: This API endpoint does not refresh the WebSocket Key. It only fetches a renewed key from Aruba Central. When multiple API calls are made to the same endpoint, valid key will be returned all the time. It might be same as the provided key if the key is valid.

REST API Endpoint to validate the WebSocket Key is as follows,

Endpoint URL:

`https://<base-url>/streaming/token/validate`

Request Header: 

- "Authorization" : `<wss-key>`

Response Data:

```json
{
   "token": "xxxx"
}
```

## Python Script

This section has documentation for two scripts
- `simple_app.py`: Purpose of this script to learn about making a WebSocket connection to Aruba Central Streaming API such as required headers and decoding protobuf data.
- `wsclient_public.py` - This script is for more advanced use cases. It offers support for multiple streaming API topics, ability to connect to multiple customers in parallel and provides structure to handle the data.

### Recommended Python Version: 3.6.1+

### Package Requirements

- See *requirements.txt*
- Install with: `pip3 install -r requirements.txt`

#### Simple Python WebSocket App 

The goal of this section is to create a simple websocket app in Python. The provided script subscribes to `monitoring` topic in Aruba Central Streaming API.

**Script:  `simple_app.py`**

The following variables `hostname`, `header["Authorization"]`, `header["UserName"]` needs to be updated. 

To execute this script, enter the command `python3 simple_app.py`

Refer the following snippet that subscribes to *monitoring* streaming topic. 
```python
import websocket

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

```

Upon executing this script the message will be in a serialized protobuffer format. To make it human readable, update `on_message()` block with the following code,

```python
def on_message(ws, message):
    # Decode Message in Serialized protobuffer
    from proto import streaming_pb2
    stream_data = streaming_pb2.MsgProto()
    stream_data.ParseFromString(message)
    print("Timestamp in Epoch: %s" % str(stream_data.timestamp))
    print("Customer_ID: %s" % str(stream_data.customer_id))
    # Based on the topic import compiled proto file and decode 'data' field
    from proto import monitoring_pb2
    monitoring_data = monitoring_pb2.MonitoringInformation()
    monitoring_data.ParseFromString(stream_data.data)
    
    print(monitoring_data)
```

`MsgProto()` and `MonitoringInformation()` are proto messages from compiled `streaming.proto` and `monitoring.proto` files respectively.

#### Advanced WebSocket Client

The python WebSocket client script provided in this section, packs more features. 

**Script:  `wsclient_public.py`**

##### Features

- Option to subscribe data streams for multiple customers
- Option to subscribe to multiple streaming topics for each customer
- Validate the Secure WebSocket Key. When connection is made for the first time,
    - If the provided key is expired, the script obtains the working WebSocket key from Aruba Central via REST API.
    - Updates the input JSON file with working key. Next time when the script is executed, you would have most recent key.
- Decode data streams received in google protobuf format and convert it to python dictionary.
- Provide structure for data transport/export to external apps/storage device. User need to implement the transport/storage logic based on their requirement.

Please Note: This sample script does not attempt to retry when the WebSocket connection is broken in-between data streaming. Validation of WebSocket Key only occurs during initial connection.

##### Script Execution
Command to execute the script
```sh
python3 wsclient_public.py --hostname internal-ui.central.arubanetworks.com --jsoninput input.json --decode_data
```

To view description of all available arguments, execute the following command
```sh
python3 wsclient_public.py --help
```

The required script arguments are,

- `--hostname` - The base url obtained from Aruba Central `Maintain -> Organization -> Platform Integration -> API Gateway -> Streaming -> Endpoint`. For example "wss://**internal-ui.central.arubanetworks.com**/streaming/api"

- `--jsoninput` - Input File where the Aruba Central customer information is provided in JSON format.

To view data on screen,
- `--decode_data` - to print the decoded data streams on screen during script execution.

Complete list of arguments accepted by the script
```
  wsclient_public.py [-h] --hostname HOSTNAME --jsoninput JSONINPUT
                          [--decode_data] [--no_valid_cert]
                          [--export_data EXPORT_DATA]
 ```                         

##### Input JSON file

Provide the input file in the following format.

This format is to subscribe to a single topic for a single customer
```json
{
  "customers": {
       "<define-unique-name>": {
         "username": "<aruba-central-username>",
         "wsskey": "<streaming-api-wss-key>",
         "topic": "<audit|apprf|location|monitoring|presence|security>"
       }
  }
}
```

##### Required Variables

- `<define-unique-name>` is any unique name defined by you, to represent the Aruba Central customer information and topic to be subscribed for this entry.

- "username" --> A valid central user email address through which Streaming API will be accessed

- "wsskey" --> obtained from Aruba Central (`Maintain -> Organization -> Platform Integration -> API Gateway -> Streaming -> Streaming Key`)

- "topic" --> provide one of the following [audit, apprf, location, monitoring, presence, security]

For Example to subscribe to multiple topics per customer and multiple customers, `input.json` file should look like the following. In this example, there are two customers "CustomerA" and "CustomerB". "CustomerA" subscribed to two topics "monitoring" and "security". "CustomerB" subscribed to one topic "monitoring".

```json
{
  "customers": {
       "CustomerA_monitoring": {
         "username": "abc@gmail.com",
         "wsskey": "xxxx",
         "topic": "monitoring"
       },
       "CustomerA_security": {
         "username": "abc@gmail.com",
         "wsskey": "xxxx",
         "topic": "security"
       },
       "CustomerB_monitoring": {
         "username": "xyz@gmail.com",
         "wsskey": "YYYY",
         "topic": "monitoring"
       }    
  }
}
```

**Please Note:** The proto messages of type *bytes* are *base64* encoded in the decoded data. Example message fields of type bytes are MAC Address, IP Address and ESSID. You can know the type of a certain message field from the proto files.

To decode the bytes data field, a snippet of python code is provided below
```python
import base64
mac_address = base64.b64decode("<mac-address-value>")
```

In some instances, the fields needs to processed further, after base64 decoding.
To get MAC Address in format *FF:FF:FF:FF:FF:FF*
```python
print(':'.join('%02x' % ord(byte) for byte in mac_address))
```

Similarly for IP address received as *b'\n\x01\ng'*, is *10.1.10.103* after processing.
```python
print('.'.join('%d' % byte for byte in ip_address))
```
