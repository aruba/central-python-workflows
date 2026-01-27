"""Command validation and execution logic."""

from typing import List
from .models import CommandResult
from .config import POLL_INTERVAL, MAX_ATTEMPTS


def fetch_supported_commands(device_instance) -> List[str]:
    """Fetch supported commands for the device using SDK."""
    try:
        supported_commands_response = device_instance.list_show_commands()
        return [
            command_dict["command"]
            for category in supported_commands_response
            for command_dict in category.get("commands", [])
        ]
    except Exception as e:
        print(f"Error fetching supported commands: {e}")
        return []


def validate_command(command: str, supported_commands: List[str]) -> bool:
    """Validate if a command is supported by the device."""
    command_base = command.strip().lower()
    return any(
        command_base in supported.lower() or supported.lower().startswith(command_base)
        for supported in supported_commands
    )


def validate_commands(commands: List[str], device_instance) -> dict[str, bool]:
    """Validate a list of commands against device capabilities."""
    supported_commands = fetch_supported_commands(device_instance)
    print(f"Validating {len(commands)} commands against device...")

    validation_results = {}
    for command in commands:
        is_valid = validate_command(command, supported_commands)
        validation_results[command] = is_valid
        status = "✓ VALID" if is_valid else "✗ INVALID"
        print(f"  {status}: {command}")

    return validation_results


def execute_command(command: str, device_instance) -> CommandResult:
    """Execute a single command on the device."""
    try:
        response = device_instance.run_show_command(
            command=command, poll_interval=POLL_INTERVAL, max_attempts=MAX_ATTEMPTS
        )

        if response.get("failReason"):
            print(f"Command '{command}' failed: {response['failReason']}")
            return CommandResult(
                command=command,
                status="FAILED",
                error=response.get("failReason"),
                raw_response=response,
            )

        if response.get("status") != "COMPLETED":
            print(f"Command '{command}' did not complete successfully.")
            print(response)
            return CommandResult(
                command=command,
                status=response.get("status", "FAILED"),
                error=f"Command did not complete successfully. Status: {response.get('status', 'UNKNOWN')}",
                raw_response=response,
            )

        return CommandResult(
            command=response.get("output", {}).get("command", command),
            status=response.get("status", "COMPLETED"),
            response=response.get("output", {}).get("response", ""),
            raw_response=response,
        )
    except Exception as e:
        print(f"Error executing command '{command}': {e}")
        return CommandResult(
            command=command,
            status="ERROR",
            error=str(e),
        )


def execute_commands_sequentially(
    commands: List[str], device_instance
) -> List[CommandResult]:
    """Execute validated commands sequentially and collect results."""
    results = []
    print(f"\nExecuting {len(commands)} commands sequentially...")

    for i, command in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] Processing: {command}")
        result = execute_command(command, device_instance)
        results.append(result)

        # Display output
        print(f"\n{'=' * 60}")
        print(f"Command: {result.command}")
        print(f"Status: {result.status}")
        if result.error:
            print(f"Error: {result.error}")
        print(f"{'=' * 60}")
        if result.response:
            print(result.response)
        elif result.error:
            print(f"[No output - command failed with error: {result.error}]")
        print(f"{'=' * 60}\n")

    return results
