"""Command validation and execution logic."""

import re
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
    command_base = command.strip()
    for supported in supported_commands:
        literal_parts = re.split(r"\{\{[^{}]+\}\}", supported.strip())
        pattern = r"\S+".join(re.escape(part) for part in literal_parts)
        if re.fullmatch(pattern, command_base):
            return True
    return False


def validate_commands(
    commands: List[str], device_instance, log=print
) -> dict[str, bool]:
    """Validate a list of commands against device capabilities."""
    supported_commands = fetch_supported_commands(device_instance)
    log(f"Validating {len(commands)} commands against device...")

    validation_results = {}
    for command in commands:
        is_valid = validate_command(command, supported_commands)
        validation_results[command] = is_valid
        status = "\u2713 VALID" if is_valid else "\u2717 INVALID"
        log(f"  {status}: {command}")

    return validation_results


def _format_batched_item(command_output: dict) -> CommandResult:
    """Normalize one {command, output} batched item into CommandResult."""
    command = command_output.get("command", "")
    output = command_output.get("output")

    if output is None:
        return CommandResult(
            command=command,
            status="FAILED",
            error="No output returned for this command",
            raw_response=command_output,
        )

    if isinstance(output, str) and any(
        line.strip().casefold() == "% parse error."
        for line in output.splitlines()
    ):
        return CommandResult(
            command=command,
            status="FAILED",
            response=output,
            error="Invalid command: API returned % Parse error.",
            raw_response=command_output,
        )

    return CommandResult(
        command=command,
        status="COMPLETED",
        response=output,
        raw_response=command_output,
    )


def execute_commands_sequentially(
    commands: List[str], device_instance, log=print
) -> List[CommandResult]:
    """Execute validated commands in one batch using run_show_commands."""

    log(f"\nExecuting {len(commands)} command(s) in a single batch...")

    try:
        response = device_instance.run_show_commands(
            commands=commands,
            poll_interval=POLL_INTERVAL,
            max_attempts=MAX_ATTEMPTS,
        )
    except Exception as e:
        log(f"Error executing command batch: {e}")
        return [
            CommandResult(command=command, status="ERROR", error=str(e))
            for command in commands
        ]

    if not isinstance(response, dict):
        results = [
            CommandResult(
                command=command,
                status="FAILED",
                error="Unexpected response format returned by run_show_commands",
            )
            for command in commands
        ]
    else:
        output = response.get("output")
        items = output.get("results") if isinstance(output, dict) else None

        if not isinstance(items, list):
            results = [
                CommandResult(
                    command=command,
                    status="FAILED",
                    error="Unexpected response format: expected output.results list",
                    raw_response=response,
                )
                for command in commands
            ]
        else:
            results = [
                _format_batched_item(
                    command_output if isinstance(command_output, dict) else {}
                )
                for command_output in items
            ]

            if len(items) < len(commands):
                results.extend(
                    CommandResult(
                        command=command,
                        status="FAILED",
                        error="No result returned for this command",
                        raw_response=response,
                    )
                    for command in commands[len(items) :]
                )

            if len(items) > len(commands):
                log(
                    f"Warning: received {len(items)} results for {len(commands)} commands; extra results ignored"
                )

    for result in results:
        log(f"\n{'=' * 60}")
        log(f"Command: {result.command}")
        log(f"Status: {result.status}")
        if result.error:
            log(f"Error: {result.error}")
        log(f"{'=' * 60}")
        if result.response:
            log(result.response)
        elif result.error:
            log(f"[No output - command failed with error: {result.error}]")
        log(f"{'=' * 60}\n")

    return results
