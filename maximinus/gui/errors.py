"""Formats an unexpected exception for on-screen display.

This is specifically for errors the rest of the code doesn't already
handle — a FixError/PoolError/EnrollmentError means something identified
and explained what went wrong; this is the catch-all for anything that
slips past that, so the GUI never just freezes or silently drops back to
a stale state with no explanation.

Three verbosity levels, so the amount of detail shown is a deliberate
choice rather than "whatever str(exc) happens to produce":
  1 - just says something went wrong and what was happening at the time.
  2 - adds the exception type and its message (default: enough to search
      for or report, without dumping a full traceback into the UI).
  3 - adds the full traceback, for actually debugging it.
"""

import traceback

DEFAULT_VERBOSITY = 2


def format_error(exc: Exception, context: str, verbosity: int = DEFAULT_VERBOSITY) -> str:
    base = f"Unexpected error while {context}."
    if verbosity <= 1:
        return base

    detail = f"{base} {type(exc).__name__}: {exc}"
    if verbosity <= 2:
        return detail

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{detail}\n\n{tb}"
