# Inventory to Excel Workflows

This README presupposes general knowledge of how to use ArubaCentral API's and execute workflow scripts.  Please see [here](https://github.com/aruba/pycentral/blob/master/README.md)
for detailed information on installing pycentral and getting setup to execute workflow scripts.

Inventory to excel workflows are used to create excel files populated with device details from devices currently in inventory.

### Workflow Functionality

1. This workflow should be used to collect all device details from devices in an account's inventory and export this data to an excel workbook. 

2. Device details included are: Aruba Part Number, Customer ID, Customer Name, Device Type,  IMEI, Mac Address, Model, Serial, Services, Subscription Key, and Tier type.

3. Device types received from inventory can be filtered using the sku_type CLI argument described in section 2 of [executing the workflow](#executing-the-workflow).
   
4. Additonal CLI options are available including: config filepath, excel filename, limit, offset.

### How To Install
In order to run the workflow script please install the requirements which includes Pycentral.  Please refer to the link
above for more information on installing Pycentral.
1. Clone the repository.
   ```
   git clone https://github.com/aruba/central-python-workflows.git
   cd inventory_to_excel
   ```

2. install requirements.txt. Make sure python version 3 is installed in system.
    ```
    $ pip install -r .\requirements.txt
    ```

### Other Setup
A config file containing credential information for your Aruba Central account is required to run this workflow.  The details and structure
for how to create this can be found [here](https://github.com/aruba/pycentral/tree/master/sample_scripts).  The config filename should be passed as a CLI argument during execution.
```python
--central_auth <"path to config file">
```

Now you can start executing the script.

### Executing The Workflow
1. The workflow can be ran as is with a config file named central_token.yaml in the working directory.
    
    ```
    $ python inventory_excel_workflow.py
    ```

    This will create a new .xlsx document named inventory.xlsx in the working directory.
    The .xlsx file will contain the details for all devices in inventory as documented in the [API](https://developer.arubanetworks.com/aruba-central/reference/acp_servicenb_apiapidevice_inventoryget_devices).


2. Providing input variables to the workflow is optional. One or multiple of the following options can be used through CLI arguments.
    * Flags

        Output format:
            By default the workflow outputs an excel file in the .xlsx filetype. Output format can be changed optionally with the -c flag to output as .csv instead.  If the -c flag is set the workflow will output the new file as a .csv.
        ```
        $ python inventory_excel_workflow.py -c
        ```
    
    * Provide variables to script upon execution
        
        central_auth:
            Sets the file path to central credential file.
        ```
        $ python inventory_excel_workflow.py --central_auth <path/to/file>
        ```
        
        filename:
            Sets the name of the output file.
        ```
        $ python inventory_excel_workflow.py --filename <filename>
        ```

        sku_type parameters:
            Sets the specific device type to pull device details for. Only one option at a time is currently supported.
            Valid inputs: all, iap, switch, controller, gateway, **vgw, cap, boc, all_ap, all_controller, others.
        ```
        $ python inventory_excel_workflow.py --sku_type <sku>
        ```

        limit and offset parameters:
            Sets pagination for API calls.  Should be used together.
        ```
        $ python inventory_excel_workflow.py --limit <int> --offset <int>
        ```

        **See Known Bugs section

## Documentation:
* **Python package documentation:** [pycentral module documentation](https://pycentral.readthedocs.io/en/latest/)
* **Use-Cases and Workflows:** [Aruba Developer Hub](https://developer.arubanetworks.com/aruba-central)
* **API Reference:** [New Device Inventory](https://developer.arubanetworks.com/aruba-central/reference/acp_servicenb_apiapidevice_inventoryget_devices)

## Troubleshooting Issues
If you encounter module import errors, make sure that the package has been installed correctly.

## Known Bugs
1. sku_type 'vgw' currently does not work.  It should exit with a bad request error and a response code of 500.
