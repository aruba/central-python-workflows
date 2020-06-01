import os
import sys
import json
import logging
import glob
from os.path import dirname, basename, isfile, join

C_LOG_LEVEL = {
  "CRITICAL": 50,
  "ERROR": 40,
  "WARNING": 30,
  "INFO": 20,
  "DEBUG": 10,
  "NOTSET":	0
}

def update_sys_path(path):
    """
    Summary: Function to insert Aruba Central library path to sys path.
    """
    sys.path.insert(1, path)

def get_subdir_list(dir_name, with_path=True):
    subdir_list = []
    d = dir_name
    if with_path:
        subdir_list = [os.path.join(d, o) for o in os.listdir(d)
                       if os.path.isdir(os.path.join(d,o))]
    else:
        subdir_list = [o for o in os.listdir(d)
                       if os.path.isdir(os.path.join(d,o))]
    return subdir_list

def get_files_from_dir(dir_name=".", file_type=".py"):
    d = dir_name
    file_list = [os.path.join(d, f) for f in os.listdir(d)
                 if isfile(join(d, f)) and f.endswith(file_type)]
    return file_list

def get_file_content(file_name):
    """
    Summary: Function to open a file and return the contents of the file
    """
    input_args = ""
    try:
        with open(file_name, "r") as fp:
            input_args = json.loads(fp.read())
        return input_args
    except Exception as err:
        exit("exiting.. Unable to open file %s!" % file_name)

def console_logger(name, level="DEBUG"):
    """
    Summary: This method create an instance of console logger.
    Parameters:
        name (str): Parent name for log
        level (str): One valid logging level [CRITICAL, ERROR, WARNING, INFO
                     DEBUG, NOTSET]. All logs above and equal to provided level
                     will be processed
    Returns:
        logger (class logging): An instance of class logging
    """
    channel_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s - %(name)s -"
                                  " %(levelname)s - %(message)s")
    channel_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(C_LOG_LEVEL[level])
    logger.addHandler(channel_handler)

    return logger
