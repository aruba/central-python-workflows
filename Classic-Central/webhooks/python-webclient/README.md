# Client Application for Aruba Central Webhooks

### **[Download as Zip File](https://downgit.github.io/#/home?url=https://github.com/aruba/central-examples-only/tree/master/webhooks/python-webclient)**

Webhooks allow you to implement event reactions by providing real-time information or notifications to other applications. Aruba Central allows you to create [Webhooks](https://help.central.arubanetworks.com/latest/documentation/online_help/content/api/api_webhook.htm) and select them as the notification delivery option for all [Alerts & Events](https://help.central.arubanetworks.com/latest/documentation/online_help/content/nms/alerts/alerts.htm). When an Alert is configured with Webhook, the notification for the Alert will be pushed to the Webhook URL via HTTP POST from Aruba Central.

The purpose of the sample python based HTTP(s) client application is to act as a reference on how to securely receive data from Aruba Central via Webhooks. This is not a production quality code and to be used under your sole discretion. 

Some use cases would be to integrate with external applications for automated ticket filing, push notifications in workspace communication tool such as Slack/Teams, build your own dashboard to monitor alerts and more.  

## About "central_webhook_client.py"

The script is verified to work with **Python version 3+**. 

### Pre-Requisites

Host this web client application in your preferred method. One way to run this script is to have the following

-  Webserver with FQDN/IP reachable from Aruba Central. Some of the most popular webservers are [Apache](https://httpd.apache.org/) / [Nginx](https://www.nginx.com/).  

- Configure reverse proxy in Webserver

  Sample reverse proxy configuration for Nginx webserver. Let us consider "https://www.example.com" as webserver FQDN. Upon applying this configuration, when the webserver receives the HTTP request from Aruba Central with the Webhook URL "https://www.example.com/centralwebhook", the webserver will act as a reverse proxy and forward the request to the mentioned upstream server IP address and the port (port 8010 in this example). The sample web client application should run on this upstream IP address and the port.

  ```

  upstream centralwebhook { 
          server 127.0.0.1:8010;
  }

  server {
          listen 443 default_server;
          listen [::]:443 default_server;
          server_name _;

          ...

          location /centralwebhook {
              proxy_pass http://centralwebhook;
              proxy_redirect off;
              proxy_set_header Host $host;
          }
  ```

- Create Webhooks in the Aruba Central by following the steps [mentioned here](https://help.central.arubanetworks.com/latest/documentation/online_help/content/api/api_webhook.htm#). The URL will be the FQDN/IP where webserver will host this sample web application.

### Script Execution

Provide required information in the `input_info.json`

```
{
  "webclient_info": {
                      "host": "localhost",
                      "port": "<free-port-in-host>"
                    },
  "central_info": {
                    "webhook": { "name": "<name-of-the-webhook>",
                                 "token": "<token-of-the-webhook>"
                              }
                  }
}
```

- *free-port-in-host* is the port of your choice where the sample client application will run in the localhost upon execution.

- *name-of-the-webhook* is the name for the webhook in Aruba Central. This is optional and exists for your reference.

- *token-of-the-webhook* can be obtained from `ACCOUNT HOME -> GLOBAL SETTINGS -> WEBHOOKS -> Click on the edit icon of your webhook -> Copy the "Token" value`. For added security, this token value can also be refreshed when required by the user by following the steps mentioned in the [guide](https://help.central.arubanetworks.com/latest/documentation/online_help/content/api/api_webhook.htm#).

Command to execute the script:

```
python3 central_webhook_client.py -i=input_info.json
```

### Validating authenticity and integrity of the received data

The header of the received HTTP request from Aruba Central Webhook contains `X-Central-Signature`. This should be compared against the signature found by using HMAC algorithm and SHA256 hashing of the received data and webhook token in the input file as secret key. Refer the function `verifyHeaderAuth()` defined in the script on how to achieve this. 

If the signature obtained from HMAC algorithm is same as the X-Central-Signature in the header, both the integrity and the authenticity of the data are simultaneously considered verified.
