# Aruba Central REST API Python Scripts
### **[Download as Zip File](https://downgit.github.io/#/home?url=https://github.com/aruba/central-examples-only/tree/public-devel/rest-api-python-scripts)**

Aruba Central is a cloud-based network management and configuration platform.
Aruba Central offers a REST API, allowing programmatic interaction with the platform for the collection of data and configuration of assets. The API is secured using OAuth 2.0, which provides authorization based on tokens issued to applications.

This guide is split into two parts and the objectives are as follows:

1. Getting Started with Aruba Central API. This part provides an overview of Aruba Central's implementation of OAuth 2.0 Authorization framework.
   - Create a new application in Aruba Central
   - OAuth 2.0 Workflow
2. Getting Started with Automation using Aruba Central API. This part, 
   - **api_tutorial:** Learn Aruba Central API OAUTH login and making an API Call with multiple programming approaches.
   - **central_modules:** Provides ready to use modules based on *central_lib* which can be used to automate configuration tasks without programming.
   - **central_lib:** Provides Python based library to kick start with automation. This library manages login, managing and refreshing tokens, making an API calls to Aruba Central.

## Getting Started with Aruba Central API

This section is aimed at beginners to get started with the Aruba Central API. A key aspect of creating an automated workflow to interact with Aruba Central API is the acquistion, management and refresh of OAuth tokens. 

Two workflows are described in this section.

- OAuth 2.0 Workflow
- Refresh Token Workflow

As a pre-requisite both the workflows require some variables.

 * Aruba Central *Base URL*
 * API Gateway *Client ID*
 * API Gateway *Client Secret*
 * Aruba Central *Customer ID* 
 * Aruba Central *User Name* and *User Password*
 
The variables can be obtained by following the below mentioned steps.

### Create a new application in Aruba Central

To interact with the Aruba Central API programmatically one must create an application that will be granted authorization to generate access and refresh tokens. During the application creation process all of the required variables, except the username and password, can be obtained.
 
To create a new application:

a) Log in to Aruba Central using your username & password.
b) On the Front Panel screen, click the 'Account Home' icon.

 ![Account Home](pictures/1-frontpage.png)  

c) Click 'API Gateway'

![API Gateway](pictures/2-api-gateway.png).

d) The API Gateway will display the 'base_url' variable. Look for the URL under the 'Documentation' header. Truncate this to end with '.com' E.G. 'https://eu-apigw.central.arubanetworks.com/swagger/central/' must be truncated to 'https://eu-apigw.central.arubanetworks.com'.
e) Next click 'System Apps & Tokens'.

![System Apps](pictures/3-base_url.png).

f) Click 'Add Apps & Tokens' and create a new application.
g) Once the new app is created, it will be displayed in the 'System Apps & Tokens' table, along with the 'client_id' and 'client_secret'.

![App Client Info](pictures/4-clientx.png)

h)  Finally, to obtain the 'customer_id', click on the figure of a person, top right. A table will be displayed for the logged in user. This contains the 'customer_id'.
   
   ![Customer ID](pictures/5-customer-id.png)

### OAuth 2.0 Workflow

The Central REST API utilises an OAuth 2.0 authorization framework. Authorization is requested and granted in accordance with the defined steps and, if successful, two tokens will be issued by the Authorization Server:

* Access token - this is end result of a successful authentication and authorization process. The access token is combined with subsequent API calls, allowing users access to configure, manage and receive data from the API. However, the access token is time-limited.
* Refresh token - this token is issued at the same time as the access token but is not subject to the same strict time limitations as the access token. The refresh token can be used to request a new access token.

For more information about OAuth 2 frameworks please refer to the the following link:

https://www.digitalocean.com/community/tutorials/an-introduction-to-oauth-2


The full authentication and authorization workflow is as follows:

#### 1. Log in using User Credentials

The user combines the required variables with their Aruba Central password and sends a call to the REST API login URI.
Upon successful authentication, a valid session key and CSRF token is returned in the HTTP response cookies.

#### 2. Authorization Call

The second API call requests an authorization code and includes the received CSRF and session information.
If successful, the server will return an authorization code which expires in 300 seconds. The authorization code is used in the next step to generate access token.

#### 3. Generate the Access and Refresh Tokens

A final API call is then made to request the access token by including the authorization code. If successful the access token and refresh token are the response to this call. The user can combine the access token with their API calls for authorized access to their Aruba Central assets' configuration and data.

The access token expires in 2 hours and upon expiry older refresh token can be used to obtain new access and refresh token. The user needs to store the new access and refresh token securely for future refresh and access other API endpoints in Aruba Central.

### Refresh Token Workflow

If the user is in possession of a refresh token, the authorization process is truncated:

1. The user must still gather the required variables, as detailed in `Create a new application in Aruba Central`.
2. The user combines the refresh token with the required variables to create a HTTP request to refresh API endpoint.
3. If successful, the refresh API will issue a new refresh token and access token.
4. The user must manage the two tokens as detailed in the full authentication workflow.

## Getting Started with Automation using Aruba Central API

This section provides information regarding source code available in this repository. Users with multiple programming skill levels can leverage this for their Aruba Central automation journey.  

**Recommended Python Version is 3.5+**

#### Setting Up Python environment and Installing Requirements

To create the Python environment (macOS shown):

```bash
cd central-api-getting-started
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 1. [api_tutorial](/rest-api-python-scripts/api_tutorial)

The aim of this section is to provide walkthrough and educate users to obtain API access token and make an API call using simple programming. Three different progamming approaches for authentication and authorization are shown.

They all use Python and offers the same set of operations. 
   - OAUTH Authorization (three steps involved are login, auth and access)
   - Refreshing access token
   - Making an API call

a. [api_tutorial/central_global] - offers operations in a single Python file and all commands in global namespace.  

b. [api_tutorial/central_function] - offers operations using Python functions()

c. [api_tutorial/central_class] - offers operations using Python Class.

### 2. [central_modules](/rest-api-python-scripts/central_modules)

This section contains ready to use modules built for commonly and widely used automation tasks. The modules are written in Python and is based on *central_lib*. Each module is built on a purpose and automates one or more tasks. They all follow same structure and execute the same way.

Users need not know programming to use these modules. The modules are usefule for users to perform repetitive operation like renaming hundreds of Access Points(AP) or doing a simple multi-step configuration like creating group, moving device to a group, creating site, adding device to a site without needing to write a program.

### 3. [central_lib](rest-api-python-scripts/central_lib)

Once the user learns what is OAUTH login, obtain API access_token and know how to make an API call using **api_tutorial**, they can make use of **central_lib**.

This can be used in two different ways
 - Use the library as is. It simplifies and abstracts OAUTH 2.0 (login, auth and access), storing and managing tokens, refreshing expired access token and making an API call.
 - Extend the `ArubaCentralBase` class to add features based on user's requirement. 

## Security Considerations

To fulfil the project's aim of explaining the operations involved in accessing the API, the examples given do not adhere to strict security concerns. Certain examples of code are considered unsafe and a security threat. There are warnings within the code when this is the case. These unsafe examples are for educational purposes only and should not be used outside of the context of a learning exercise.  

Please note that for the purposes of this project the term **required variables** will be used to denote those pieces of information that are required to interact with the Aruba Central API.  
The required variables are:

      1. username
      2. password
      3. customer ID
      4. client ID
      5. client secret
      6. access token
      7. refresh token
   
* The required variables to interact with the Aruba Central API must be treated with the same care as the user's password.  
* The required variables must not be shared or copied to public sites, blogs etc.  
* Do not include the required variables in your scripts. The examples in this project that do so are for educational purposes only and are unsafe.  
* Take care not to check in to version control documents that contain your required variables.

In addition the user should follow the following guidelines to ensure they are not placing the security of their access to the Aruba Central API platform at risk:

* If using git, use the .gitignore file to ignore the locally stored required variables file.
* Also, alway use `git add <my-file-name>` to stage only the required files for check in to a git server.
* Do not use `git add *` or other forms of wildcard that risk unwittingly staging sensitive files.

## Contributing Authors

@joeneville_ <joe.neville@hpe.com>

@karthikeyan-dhandapani <karthikeyan.dhandapani@hpe.com>
