"""Maximinus GUI: a GTK3 front end over the same scan/plan/fixer machinery
the CLI uses.

Status: UI-complete, navigation-complete, NOT wired to real execution yet.
Listing data (the setup checklist, the judgment-call list) comes from the
real `collect_facts()`/`build_plan()`, so what you see reflects this
machine's actual state. Clicking "Start" or "OK" simulates applying the
selection (see pages/progress.py, pages/judgment.py) rather than calling
`fixer.apply()` / `apt-get install` for real — that's the next step once
the three-screen flow itself is settled.
"""
