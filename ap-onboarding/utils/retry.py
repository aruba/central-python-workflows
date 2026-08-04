import time


def retry_on_response(
    operation,
    is_success,
    should_retry,
    max_retries,
    pause_seconds,
    on_retry_message=None,
):
    """Run an operation and retry based on response predicates."""
    last_response = {}
    for attempt in range(1, max_retries + 1):
        response = operation() or {}
        last_response = response
        if is_success(response):
            return response
        if should_retry(response) and attempt < max_retries:
            if on_retry_message is not None:
                print(on_retry_message(response, attempt, max_retries))
            time.sleep(pause_seconds)
            continue
        break
    return last_response


def poll_until(operation, condition, max_retries, pause_seconds, on_retry_message=None):
    """Poll an operation until condition is met or retries are exhausted."""
    last_response = None
    for attempt in range(1, max_retries + 1):
        response = operation()
        last_response = response
        if condition(response):
            return True, response
        if attempt < max_retries:
            if on_retry_message is not None:
                print(on_retry_message(attempt, max_retries))
            time.sleep(pause_seconds)
    return False, last_response


def retry_on_exception(
    operation,
    max_retries,
    pause_seconds,
    on_retry_message=None,
):
    """Run an operation until it succeeds or the final exception is exhausted."""
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception:
            if attempt >= max_retries:
                raise
            if on_retry_message is not None:
                print(on_retry_message(attempt, max_retries))
            time.sleep(pause_seconds)
