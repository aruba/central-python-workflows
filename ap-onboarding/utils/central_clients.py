"""One scoped New Central client, shared by every request path that needs one.

Building the client costs a token mint plus scope population. routers/creates.py,
routers/lookups.py, and routers/run.py were each paying that on every request.
They now all route through here, so the cost is paid once and invalidated
together when credentials change.
"""

import threading

from pycentral import NewCentralBase

from paths import CREDS_PATH

_connection = None
_lock = threading.Lock()


def _close(connection) -> None:
    close = getattr(connection, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        pass


def _build():
    connection = NewCentralBase(
        token_info=CREDS_PATH,
        log_level="ERROR",
        enable_scope=True,
    )
    if getattr(connection, "token_file_path", None):
        # pycentral rewrites the credential YAML during a 401 refresh, so two
        # threads refreshing at once corrupt it. Callers fan out (lookups runs
        # seven reads in parallel), so serialize the refresh at the client.
        refresh_lock = threading.Lock()
        create_token = connection.create_token

        def create_token_serially(app_name):
            with refresh_lock:
                return create_token(app_name)

        connection.create_token = create_token_serially
    return connection


def invalidate_scoped_connection() -> None:
    """Discard the shared client so the next caller builds from current files.

    Must be called whenever the credential files are replaced: a client built
    from a revoked credential would otherwise keep being reused.
    """
    global _connection
    with _lock:
        connection = _connection
        _connection = None
        if connection is not None:
            _close(connection)


def with_scoped_connection(work):
    """Run `work(connection)` against the shared scoped client.

    A raising `work` discards the client, so one bad connection cannot wedge
    every later request. Raise nothing for expected outcomes -- a conflict or a
    validation failure should be returned, not thrown, or it throws away a
    healthy client.

    ponytail: one global lock, so concurrent callers serialize on Central I/O.
    This is a single-operator tool and the alternative is a client per caller,
    which is what we just removed. Revisit if it ever serves more than one
    browser.
    """
    global _connection
    with _lock:
        if _connection is None:
            _connection = _build()
        try:
            return work(_connection)
        except Exception:
            connection = _connection
            _connection = None
            _close(connection)
            raise
