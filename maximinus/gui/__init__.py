"""Maximinus GUI: a GTK3 front end over the same scan/plan/fixer machinery
the CLI uses.

Status: the interface and screen flow are done, but nothing here actually
executes yet. The lists on the setup and judgment screens come from the
real `collect_facts()`/`build_plan()`, so what you see reflects this
machine's actual state. Clicking "Start" or "OK" simulates applying the
selection (see pages/progress.py, pages/judgment.py) instead of calling
`fixer.apply()` or `apt-get install` for real. That wiring is the next
step, once the three-screen flow itself is settled.
"""
