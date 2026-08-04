import os
import sys

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

GREEN = "\033[92m" if _USE_COLOR else ""
RED = "\033[91m" if _USE_COLOR else ""
YELLOW = "\033[93m" if _USE_COLOR else ""
DIM = "\033[2m" if _USE_COLOR else ""
RESET = "\033[0m" if _USE_COLOR else ""


def phase_header(label, index=None, total=None):
    heading = f"[{index}/{total}] {label}" if index is not None and total is not None else label
    print(f"\n==== {heading} ====")


def subheader(label):
    print(f"\n-- {label} --")


def step_ok(serial, message):
    tag = f"{GREEN}[OK]{RESET}" if _USE_COLOR else "[OK]"
    print(f"{tag}   {serial:<12} {message}")


def step_skip(serial, reason):
    tag = f"{DIM}[SKIP]{RESET}" if _USE_COLOR else "[SKIP]"
    print(f"{tag} {serial:<12} {reason}")


def step_fail(serial, step, error):
    tag = f"{RED}[FAIL]{RESET}" if _USE_COLOR else "[FAIL]"
    print(f"{tag} {serial:<12} {step}: {error}")


def step_progress(serial, message, attempt, max_attempts):
    print(f"[..]   {serial:<12} {message} (attempt {attempt}/{max_attempts})")


def step_progress_str(serial, message, attempt, max_attempts):
    """Return a formatted progress string without printing (for use in retry lambdas)."""
    return f"[..]   {serial:<12} {message} (attempt {attempt}/{max_attempts})"


def info(message):
    print(f"[INFO] {message}")


def warn(message):
    tag = f"{YELLOW}[WARN]{RESET}" if _USE_COLOR else "[WARN]"
    print(f"{tag} {message}")


def error(message):
    tag = f"{RED}[FAIL]{RESET}" if _USE_COLOR else "[FAIL]"
    print(f"{tag} {message}")


def colorize_status(val):
    """Colorize a status string (Success/Failed/Skipped) for use in tabulate cells."""
    if val == "Success":
        return f"{GREEN}Success{RESET}"
    elif val == "Failed":
        return f"{RED}Failed{RESET}"
    elif val == "WARNING":
        return f"{YELLOW}WARNING{RESET}"
    elif val == "Skipped":
        return "Skipped"
    return val or ""
