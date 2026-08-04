import sys

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Python 3.10 or newer is required (pycentral 2.0a22 needs >=3.10); "
        f"this interpreter is {sys.version.split()[0]}"
    )
