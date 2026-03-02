"""Configuration constants for troubleshooting scripts."""

# API Configuration
POLL_INTERVAL = 10  # seconds between command status checks
MAX_ATTEMPTS = 10  # maximum polling attempts
MAX_COMMANDS_SUPPORTED = 20  # maximum troubleshooting commands per workflow run
MAX_CONCURRENT_DEVICE_FETCHES = 5  # parallel device API calls
MAX_CONCURRENT_DEVICE_EXECUTIONS = 5  # parallel device command execution workers

# Table Display Configuration
TABLE_FORMAT = "grid"
SEPARATOR_WIDTH = 80
WIDE_SEPARATOR_WIDTH = 140

# CSV Column Names
CSV_SERIAL_COLUMNS = ["serial_no", "serial_number", "serial"]

# File I/O
CSV_SAMPLE_SIZE = 1024  # bytes to read for CSV header detection
