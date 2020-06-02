import os
import sys
import json
import logging
import glob
from os.path import dirname, basename, isfile, join
try:
    from pip import get_installed_distributions
except:
    from pip._internal.utils.misc import get_installed_distributions

C_LOG_LEVEL = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET":	0
}

C_RES_CODE = {
    "-1": "FAILED",
    "0": "SKIPPED",
    "1": "SUCCESS"
}

C_COLORS = {
    "RED": "\033[1;31m",
    "BLUE": "\033[1;34m",
    "CYAN": "\033[1;36m",
    "GREEN": "\033[0;32m",
    "RESET": "\033[0;0m",
    "BOLD": "\033[;1m",
    "REVERSE": "\033[;7m"
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
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = '%Y-%m-%d %H:%M:%S'
    installed_packages = get_installed_distributions()
    f = format
    if 'colorlog' in [package.project_name for package in installed_packages]:
        import colorlog
        cformat = '%(log_color)s' + format
        f = colorlog.ColoredFormatter(cformat, date_format,
              log_colors = { 'DEBUG'   : 'bold_cyan', 'INFO' : 'blue',
                             'WARNING' : 'yellow', 'ERROR': 'red',
                             'CRITICAL': 'bold_red' })
    else:
        f = logging.Formatter(format, date_format)
    channel_handler.setFormatter(f)

    logger = logging.getLogger(name)
    logger.setLevel(C_LOG_LEVEL[level])
    logger.addHandler(channel_handler)

    return logger
