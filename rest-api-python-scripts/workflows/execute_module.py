import os, sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from importlib import import_module
import workflow_utils as utils
from pprint import pprint

def define_arguments():
    """
    Summary: Define arguments that this script will use.
    return: Populated argument parser
    """
    description = ("This is a HTTP Client application to make API calls "
                   "to Aruba Central API Gateway")
    parser = ArgumentParser(description=description,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--inventory', required=True,
                        help=('Inventory file in JSON format which has \
                              variables and configuration '
                              'required by this script.'))
    parser.add_argument('-m', '--moduleinput', required=False,
                        help=('moduleinput file in JSON format which has \
                              information required to make API calls '))
    return parser.parse_args()

if __name__ == "__main__":
    # Define Inventory Arguments
    main_logger = utils.console_logger("EXECUTE_MODULE")
    args = define_arguments()

    # Read inventory file and moduleinput file
    inventory_args = utils.get_file_content(args.inventory)
    module_args = None
    if args.moduleinput:
        module_args = utils.get_file_content(args.moduleinput)

    # Append lib path to sys path
    if "lib_path" in inventory_args:
        utils.update_sys_path(inventory_args["lib_path"])

    # Import Aruba Central Library
    from central_lib.arubacentral_base import ArubaCentralBase
    from central_lib.arubacentral_utilities import parseInputArgs

    # Connection object for Aruba Central as 'central'
    central_info = parseInputArgs(inventory_args["central_info"])
    token_store = None
    if "token_store" in inventory_args:
        token_store = inventory_args["token_store"]
    central_logger = utils.console_logger("ARUBA_CENTRAL_BASE")
    central_conn = ArubaCentralBase(central_info, token_store, central_logger)

    # Get sub-directory list of current dir
    dir_list = utils.get_subdir_list(dir_name='.', with_path=False)
    if "tasks" not in module_args:
        main_logger.error("tasks list not in moduleinput")
        exit("exiting...")

    tasks = module_args["tasks"]
    final_res = {"FAILED": 0, "SKIPPED": 0, "SUCCESS": 0}
    task_count = 0
    module_logger_store = {}
    for task in tasks:
        module_name = None
        if task.keys():
            module_name = list(task.keys())[0]
        if module_name and module_name in dir_list:
            dir_name = "./" + module_name
            f_list = utils.get_files_from_dir(dir_name,
                                              file_type=".py")
            exec_name = module_name + ".py"
            exec_index = None
            try:
                exec_index = [os.path.basename(f)
                              for f in f_list].index(exec_name)

                # Import module respective to the task
                import_name = module_name + "." + f_list[exec_index]
                module_handle = import_module(module_name)

                # Reuse old logger if repetitive task belong to same module
                module_logger = None
                if module_name not in module_logger_store:
                    module_logger = utils.console_logger(module_name.upper())
                    module_logger_store[module_name] = module_logger
                else:
                    module_logger = module_logger_store[module_name]

                # Execute the module
                task_args = task[module_name]
                task_count += 1
                str1 = "Start "
                str2 = "TASK_%d with module %s" % (task_count, module_name)
                main_logger.info(str1 + str2)
                mod_res = module_handle.run(central_conn, inventory_args,
                                            task_args, module_logger)

                # Handle final module results
                if mod_res and "code" in mod_res:
                    if str(mod_res["code"]) in utils.C_RES_CODE:
                        res_key = str(utils.C_RES_CODE[str(mod_res["code"])])
                        div_str = "==================================" + \
                                  "======="

                        if mod_res["code"] == 1:
                            str1 = "SUCCESS: "
                            main_logger.info(div_str)
                            main_logger.info(str1 + str2)
                            main_logger.info(div_str+"\n")
                        else:
                            str1 = "FAILURE: "
                            main_logger.error(div_str)
                            main_logger.error(str1 + str2)
                            main_logger.error(div_str+"\n")
                        final_res[res_key] += 1

            except ValueError:
                main_logger.error("Module executable file not found")
                final_res["FAILED"] += 1
            except Exception as err:
                main_logger.error("Error trying to executing module "
                                  "%s" % module_name)
                final_res["FAILED"] += 1
                raise err
        else:
            main_logger.error("Module %s not found" % module_name)
            final_res["FAILED"] += 1

    print("\nFINAL RESULTS")
    print("===== =======")
    sys.stdout.write(utils.C_COLORS["GREEN"])
    success_str = "SUCCESS: {}".format(final_res["SUCCESS"])
    print(success_str)

    sys.stdout.write(utils.C_COLORS["CYAN"])
    skipped_str = "SKIPPED: {}".format(final_res["SKIPPED"])
    print(skipped_str)

    sys.stdout.write(utils.C_COLORS["RED"])
    failed_str = "FAILED : {}".format(final_res["FAILED"])
    print(failed_str)

    sys.stdout.write(utils.C_COLORS["RESET"])
