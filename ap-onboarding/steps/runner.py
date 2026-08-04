from steps import STEPS
from utils.print_helpers import step_progress_str
from utils.retry import retry_on_exception


def run_add_on_steps(
    device,
    device_object,
    tracker,
    *,
    max_retries,
    pause_seconds,
):
    """Run registered add-ons in order without failing the device lane."""
    serial = device["serial_number"]
    for step in STEPS:
        if step.key not in device:
            continue
        try:
            retry_on_exception(
                lambda: step.run(device_object, device[step.key]),
                max_retries=max_retries,
                pause_seconds=pause_seconds,
                on_retry_message=lambda attempt, total_attempts: step_progress_str(
                    serial,
                    f"{step.label} failed, retrying in {pause_seconds}s",
                    attempt,
                    total_attempts,
                ),
            )
            tracker.mark_step(serial, step.key, "Success", add_on=True)
        except Exception as exc:
            tracker.mark_step(
                serial,
                step.key,
                "Failed",
                str(exc),
                add_on=True,
            )
