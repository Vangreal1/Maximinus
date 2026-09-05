"""Drive the GUI through its full
Setup -> Progress -> Judgment -> Progress -> Reboot pipeline (past the
credentials screen, which has its own dedicated tests) on a real GTK main
loop, with scan data mocked to a small known set, and prove that nothing
actually executes: subprocess.run is patched to raise if called, so any
accidental real apt-get/sudo/cryptsetup call fails the test immediately
instead of silently touching the machine.
"""

import time
from unittest.mock import patch

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    Gtk.init_check()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(not _HAS_DISPLAY, reason="no display available")


def _pump_until(condition, timeout_s=6):
    ctx = GLib.MainContext.default()
    deadline = time.time() + timeout_s
    while not condition():
        if time.time() > deadline:
            raise AssertionError(f"timed out waiting for {condition}")
        if ctx.pending():
            ctx.iteration(False)
        else:
            time.sleep(0.02)


def _fake_plan_facts():
    """A small, deterministic set covering all three lanes: an apt-install
    item, a registered-fixer item, and a judgment-call item."""
    return {
        "fs.exfat_present",       # -> apt_install exfatprogs (setup screen)
        "time.ntp_disabled",      # -> registered fixer (setup screen)
        "fs.luks_present",        # -> manual_step, no fixer (judgment screen)
    }


def _no_real_commands_allowed(*args, **kwargs):
    raise AssertionError(f"a real subprocess call was attempted: {args!r} {kwargs!r}")


def test_full_flow_never_shells_out(tmp_path):
    with patch("subprocess.run", side_effect=_no_real_commands_allowed):
        with patch("maximinus.gui.window.collect_facts", return_value=_fake_plan_facts()), patch(
            "maximinus.gui.window.list_encrypted_devices", return_value=[]
        ):
            from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

            _load_css()
            app = MaximinusApp()
            win = MaximinusWindow(app)
            win.show_all()
            win.present()
            win._go_to_setup()

            # --- Setup screen: expect exactly the 2 safe items ---
            setup = win.setup_page
            assert len(setup._rows) == 2, [p.rule_id for _r, _k, p in setup._rows]
            kinds = {kind for _row, kind, _payload in setup._rows}
            assert kinds == {"apt", "fixer"}
            assert all(row.selected for row, _k, _p in setup._rows)  # pre-selected

            setup.start_button.clicked()
            assert win.stack.get_visible_child_name() == "progress"

            # --- Progress screen (pass 1): runs to completion on its own timers ---
            _pump_until(lambda: win.stack.get_visible_child_name() == "judgment")

            # --- Judgment screen: exactly the 1 risky item, unselected ---
            judgment = win.judgment_page
            assert len(judgment._rows) == 1
            assert judgment._rows[0].item.rule_id == "luks-auto-unlock"
            assert not judgment._rows[0].selected  # nothing pre-selected

            # Selecting it and clicking OK sends it through the progress
            # screen a second time, not straight to a result.
            judgment._rows[0].check.set_active(True)
            judgment.ok_button.clicked()
            assert win.stack.get_visible_child_name() == "progress"

            # --- Progress screen (pass 2): no opt-in features in this fact
            # set, so it lands directly on the reboot screen. ---
            _pump_until(lambda: win.stack.get_visible_child_name() == "reboot")

            win.destroy()


def test_declining_all_setup_items_skips_straight_to_judgment():
    with patch("subprocess.run", side_effect=_no_real_commands_allowed):
        with patch("maximinus.gui.window.collect_facts", return_value=_fake_plan_facts()), patch(
            "maximinus.gui.window.list_encrypted_devices", return_value=[]
        ):
            from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

            _load_css()
            app = MaximinusApp()
            win = MaximinusWindow(app)
            win.show_all()
            win.present()
            win._go_to_setup()

            for row, _kind, _payload in win.setup_page._rows:
                row.check.set_active(False)
            win.setup_page.start_button.clicked()

            _pump_until(lambda: win.stack.get_visible_child_name() == "judgment")
            assert len(win.judgment_page._rows) == 1

            win.destroy()


def test_judgment_ok_with_nothing_selected_skips_progress_and_goes_to_reboot():
    with patch("subprocess.run", side_effect=_no_real_commands_allowed):
        with patch("maximinus.gui.window.collect_facts", return_value=_fake_plan_facts()), patch(
            "maximinus.gui.window.list_encrypted_devices", return_value=[]
        ):
            from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

            _load_css()
            app = MaximinusApp()
            win = MaximinusWindow(app)
            win.show_all()
            win.present()
            win._go_to_setup()

            win.setup_page.start_button.clicked()
            _pump_until(lambda: win.stack.get_visible_child_name() == "judgment")

            # nothing checked — OK should skip the progress screen entirely
            # (no opt-in features in this fact set either, so straight to
            # the reboot screen) rather than showing an empty progress run.
            win.judgment_page.ok_button.clicked()
            assert win.stack.get_visible_child_name() == "reboot"

            win.destroy()
