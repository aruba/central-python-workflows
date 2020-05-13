# Streaming API Client

Aruba Central streaming API follows publish–subscribe model where a topic is subscribed from WebSocket client and Aruba Central will publish continuous data streams to WebSocket client. This approach is different from "polling" where frequent HTTP requests to REST API endpoints are required, in order to get latest data from Aruba Central. 

This sample python script acts as a WebSocket client for Aruba Central streaming API and packs some useful features for reference and trying out streaming api. This script is NOT a production quality script and should be used with your discretion. Take additional care to store the WebSocket key securely.

### Script Features:
- Option to subscribe data streams for multiple customers
- Option to subscribe to multiple streaming topics for each customer
- Validate the Secure WebSocket Key. When connection is made for the first time, 
    - If the provided key is expired, the script obtains the working WebSocket key from Aruba Central via REST API.
    - Updates the input JSON file with working key. Next time when the script is executed, you would have most recent key.
- Decode data streams received in google protobuf format and convert it to python dictionary.
- Provide structure for data transport/export to external apps/storage device. User need to implement the transport/storage logic based on their requirement.

Please Note: This sample script does not attempt to retry when the WebSocket connection is broken inbetween data streaming. Validation of WebSocket Key only occurs during initial connection.

### Data Format

Data from Aruba Central will be in Google Protocol Buffer format. Most current proto files can be downloaded from the Aruba Central's Streaming API Page. Since the python programming language is used, the python based Google Proto Compiler was used to compile "*.proto" files to "*_pb2.py" files. [Link to compiled pb2 files in ubuntu X64 machine](/streaming-api-client/proto).

Upon running the script, if there are issues in decoding the output in human readable format try re-compiling the file in your machine. More info on compiling proto files [can be found here](https://developers.google.com/protocol-buffers/docs/pythontutorial#compiling-your-protocol-buffers).

Please Note: If you decide to download proto files from Aruba Central and compile yourself, read this note. Package name might be missing for proto files downloaded from Aruba Central. To avoid errors, add a package name to proto file before compiliation. Package name could be any valid alphabetic string and doesn't affect script execution. For Example `package Apprf;` defined in `proto/apprf.proto` file.

### Validate WebSocket Key

WebSocket key obtain from Aruba Central `Account Home -> Webhooks -> Streaming -> Key` expires every 7 days. The WebSocket key is renewed by Aruba Central internally. To obtain the renewed WebSocket key programatically without having to visit the WebUI, a REST API endpoint is available. This API accepts a WebSocket key and validates it. It returns the same key if it is valid otherwise returns the renewed key. 

Please Note: This API endpoint does not refresh the WebSocket Key. It only fetched a renwed key from Aruba Central. When multiple API calls are made to the same endpoint, valid key will be returned all the time. It might be same as the provided key if the key is valid.

REST API Endpoint to validate the WebSocket Key is as follows,

Endpoint URL: 

- https://<base-url>/streaming/token/validate
 
Request Header: 

- "Authorization" : <wss-key>
 
Response Data: 

```json 
{ 
   "token": xxxx 
) 
```

### Recommended Python Version: 3.6.1+
 
### Package Requirements

- See *requirements.txt*
- Install with: `pip3 install -r requirements.txt`

## Script Execution

Command to execute the script
```sh
python3 wsclient_public.py --hostname internal-ui.central.arubanetworks.com --jsoninput input.json --decode_data
```

To view description of all available arguments, execute the following command 
```sh
python3 wsclient_public.py --help
```

The required script arguments are,

- `--hostname` - The base url obtained from Aruba Central `Account Home -> Webhooks -> Streaming -> Endpoint`. For example "wss://**internal-ui.central.arubanetworks.com**/streaming/api"

- `--jsoninput` - Input File where the Aruba Central customer information is provided in JSON format.

To view data on screen,
- `--decode_decode` - to print the decoded data streams on screen during script execution.

Complete list of arguments accepted by the script
```
  wsclient_public.py [-h] --hostname HOSTNAME --jsoninput JSONINPUT
                          [--start_seq START_SEQ] [--deliver_last]             
                          [--deliver_all] [--since_time SINCE_TIME]
                          [--decode_data] [--export_data EXPORT_DATA]
 ```                         

### Input JSON file 

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

For Example to subscribe to multiple topics per customer and multiple customers, input.json file should look like the following

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

##### Required Variables

- `<define-unique-name>` is any unique name defined by you, to represent the Aruba Central customer information and topic to be subscribed for this entry.

- "username" --> A valid central user email address through which Streaming API will be accessed

- "wsskey" --> obtained from Aruba Central (Account Home -> Webhooks -> Streaming -> Key)

- "topic" --> provide one of the following [audit, apprf, location, monitoring, presence, security]
