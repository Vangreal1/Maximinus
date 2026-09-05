# Maximinus

Maximinus inspects a Linux Mint machine — hardware, connected drives, and
filesystem state — and proposes the minimal set of packages/actions needed
to make everything work (drive integration, drivers, etc.). It never
installs anything the machine doesn't actually need.

This is the prototype stage: a CLI that detects conditions, matches them
against declarative rules, and prints a proposed action plan. It does not
install or change anything yet.

## Usage

```bash
python3 -m maximinus.cli
```

Add `--json` to get the plan as JSON instead of a human-readable list.

## GUI (`maximinus gui` / `maximinus-gui`)

A GTK3 front end, styled dark, monochrome, and sharp-edged (no rounded
corners, no accent color — Blender's UI was the reference point, with red
reserved as the one deliberate exception for error text). Requires
PyGObject (`sudo apt install python3-gi`, already present on any Mint
desktop). The full pipeline:

**Credentials → Setup → Progress → Judgment calls → Progress → Opt-in features → Progress → Reboot**

0. **Credentials** (first screen) — enter your sudo password once; it's
   used immediately to authenticate (a real `sudo -k -S -v` call) and then
   discarded, relying on sudo's own ticket cache the same way the CLI
   does. Any encrypted drives found each get their own field, labeled
   with the drive and its type, used immediately to actually unlock that
   drive for real:
   - **LUKS**: a real `cryptsetup open` ([security/luks_enroll.py](maximinus/maximinus/security/luks_enroll.py)'s `unlock_device`).
   - **BitLocker**: a real `dislocker-fuse` call ([security/bitlocker.py](maximinus/maximinus/security/bitlocker.py)'s `unlock_device`), the common case being a dual-boot Windows drive. Accepts either the account password or the 48-digit recovery key, auto-detected by format.

   Either way, success or failure *is* the correctness check — the unlock
   tool itself rejects a wrong secret, no separate verification needed.
   A rejection shows up directly under the specific field that failed,
   not as one shared banner, so it's unambiguous which one to fix. The
   secret is never stored anywhere, not even in memory past that one
   call; only *which* devices are now unlocked is kept (see
   [maximinus/gui/session.py](maximinus/maximinus/gui/session.py)'s
   `Session.unlocked_devices`). See
   [maximinus/gui/pages/credentials.py](maximinus/maximinus/gui/pages/credentials.py).
1. **Setup** — every safe/automatic item (package installs, registered
   fixers) as a checkbox, all pre-selected (per the Risk Taking level, see
   below), editable before you commit.
2. **Progress** — a status line stating exactly what's happening right
   now, above a progress bar, with a running log of completed steps below.
   Reused for three separate passes (steps 4 and 6 too).
3. **Judgment calls** — everything that needs a human decision (driver
   conflicts, audio/firewall changes), nothing pre-selected by default,
   each row showing the exact consequence text from `rules.yaml`. Clicking
   OK hands your selection straight to the progress screen.
4. **Progress, again** — the judgment-call items you just opted into
   (skipped entirely if you selected nothing).
5. **Opt-in features** — storage pooling, on its own dedicated screen; see
   the section below. Skipped if nothing's available.
6. **Progress, a third time** — whichever opt-in features you turned on
   (skipped if none).
7. **Reboot recommended** — a closing screen noting that some changes
   (drivers, GRUB, swap, storage pools) only take full effect after a
   restart, with two buttons: **Reboot** and **Later**.

A **Risk Taking** dropdown (Never/Low/Medium/High) on the setup screen
controls what starts pre-checked there and on the judgment screen — see
[maximinus/gui/risk.py](maximinus/maximinus/gui/risk.py) for the exact
mapping. It never changes what's offered, only the defaults. It has no
effect on the opt-in features screen, which always starts unchecked.

**Status: everything from the setup screen through the opt-in features
screen is simulated — except the credentials screen and the reboot
button, which are both real.** Every screen is populated from the real
`collect_facts()`/`build_plan()`, so what you see reflects this machine's
actual state, but clicking "Start"/"OK"/"Enable selected" on the way
there walks through the selection with a short delay instead of actually
running `apt-get`/`fixer.apply()`. The two exceptions:

- The credentials screen genuinely authenticates with `sudo` and
  genuinely unlocks each drive with `cryptsetup open` (see above) — there
  isn't a meaningful "simulated" version of checking a password or a
  passphrase; the whole point is finding out whether it's actually right.
- The **Reboot** button on the final screen genuinely calls
  `systemctl reboot`, the same mechanism a desktop's own restart menu
  item uses (no sudo needed on a normal desktop session, via polkit).
  It's gated behind an in-app confirmation dialog first, since this is
  the one action anywhere in the GUI that's immediate and cannot be
  undone. **Later** does not loop back to setup — it closes the program.
  See [maximinus/gui/pages/reboot.py](maximinus/maximinus/gui/pages/reboot.py).

Any unexpected error along the way (not one of the project's own
FixError/PoolError/EnrollmentError types) shows up as red text with the
exception type and message rather than freezing the screen or vanishing
into the terminal; see [maximinus/gui/errors.py](maximinus/maximinus/gui/errors.py).

## How it works

1. **Detectors** (`maximinus/detectors/`) probe the system — PCI devices,
   attached drives/filesystems — and produce a flat set of *facts* (e.g.
   `gpu.nvidia`, `fs.ntfs_present`).
2. **Rules** (`maximinus/rules/rules.yaml`) declare `when: [facts...]` →
   `actions: [...]`. A rule fires only if every fact it requires is present.
3. The engine matches facts against rules and produces a plan: what would
   be installed/configured, and why (which fact triggered it).

## Permissions and encrypted drives

Maximinus asks for credentials at most once per run, and never stores them:

- **sudo password**: `maximinus enroll-drive` calls `sudo -v` up front, which
  uses sudo's own ticket cache — the same mechanism sudo already gives you
  at a normal shell. No separate password store.
- **LUKS-encrypted drives**: `maximinus enroll-drive [/dev/sdXN]` asks for
  your existing passphrase once, uses it only to authenticate a
  `cryptsetup luksAddKey` call that adds a freshly generated random
  keyfile to the drive, installs that keyfile at `/etc/maximinus/keys/`
  (root-owned, mode 0400), and registers it in `/etc/crypttab`. The kernel
  then unlocks the drive automatically on every future boot. Your original
  passphrase still works too — this only adds a second way in. The
  passphrase itself is never written to disk, logged, or cached; see
  [maximinus/security/](maximinus/security/) for the implementation.

## Fixing common fresh-install problems

`maximinus fix <id>` applies a real, specific fix for a detected problem —
`maximinus fix --list` shows every available fix and whether it's
currently detected on this machine. Each one asks for confirmation (skip
with `-y`), then `ensure_sudo()` once, same as `enroll-drive`/`pool-drives`.

Auto-fixable (standard, well-documented, reversible — see
[maximinus/fixes/](maximinus/fixes/)):

- **`apt-broken-state`** — an interrupted dpkg/apt run left packages
  half-configured. Runs the official remedy: `dpkg --configure -a` then
  `apt-get install -f`.
- **`dkms-headers-missing`** — DKMS modules (NVIDIA, VirtualBox, ...) are
  registered but the matching `linux-headers-$(uname -r)` package isn't
  installed, so they silently fail to build. Installs it.
- **`time-sync-disabled`** — NTP is off, which causes confusing apt/TLS
  failures from clock drift right after a fresh install. Runs
  `timedatectl set-ntp true`.
- **`grub-os-prober-disabled`** — a likely dual-boot OS was found (an NTFS
  partition for Windows, or a second Linux install's own `EFI/<name>`
  directory on the EFI System Partition, read only — nothing new is
  mounted to check this) but GRUB won't list it, because os-prober isn't
  installed or is explicitly disabled in `/etc/default/grub`. Installs
  os-prober, re-enables it, and runs `update-grub`.
- **`low-memory-no-swap`** — under 4 GiB of RAM and no swap configured at
  all, which usually means slowdowns or crashes once memory runs out.
  Creates a 2 GiB `/swapfile`, enables it, and adds it to `/etc/fstab`
  with `nofail`. This one creates new content rather than editing existing
  config, so undoing it is three plain commands: `sudo swapoff /swapfile`,
  remove the `/etc/fstab` line, `sudo rm /swapfile`.

Guidance-only (surfaced via `scan`, not auto-fixed, because the fix itself
carries real risk):

- **PulseAudio + PipeWire both installed** — purging the old one while
  audio is actively playing can interrupt the session.
- **ufw installed but inactive** — enabling it without first allowing SSH
  (if you rely on it) could lock you out of a remote session.

## `maximinus cleanup` — sweep everything in one pass

Running `scan` and picking through individual `fix <id>`/`enroll-drive`/
`pool-drives` commands one at a time works, but `maximinus cleanup` is the
one command meant to be run at any point — right after a fresh install, or
months later to catch anything new — to check every condition this tool
knows about and settle whatever's safe to settle automatically:

- Every recommended package (drivers, filesystem support tools) gets
  installed.
- Every registered fix (`apt-broken-state`, `dkms-headers-missing`,
  `time-sync-disabled`, `grub-os-prober-disabled`) gets applied.
- Everything that genuinely needs a human call — a NVIDIA driver conflict
  that requires picking which version to keep, an audio server conflict
  that could interrupt a live session, ufw activation that could lock out
  SSH — is listed with its exact remediation command, not touched.

One confirmation covers the whole batch (skip it with `-y`), and one sudo
prompt covers every privileged step, same as everywhere else in Maximinus.
It's idempotent and safe to re-run any time: every check re-reads live
system state, so anything already fixed, already installed, or already
pooled is simply left alone on the next pass.

## A few more fresh-install gaps

Smaller, standalone checks in [maximinus/detectors/extras.py](maximinus/maximinus/detectors/extras.py),
all surfaced as ordinary `apt_install` recommendations (so `cleanup` and
the GUI's setup screen install them like any other package):

- **Laptop power management** — a battery is present but neither `tlp` nor
  Mint's own default, `power-profiles-daemon`, is active. If
  `power-profiles-daemon` is already handling it, nothing is recommended;
  if both `tlp` and `power-profiles-daemon` end up active at once (a real,
  known conflict since they fight over the same hardware controls), that's
  flagged as a judgment call instead of silently installing on top.
- **Firmware updates** — no `fwupd`/`fwupdmgr`, so there's no way to check
  for or apply firmware updates from Linux.
- **Media codecs** — `libavcodec-extra` isn't installed, so some
  audio/video files may not play.
- **Printing** — no `cups`, so printers won't work at all yet.

## Adapting to changes you already made

A few checks and fixers specifically look for signs that something was
already set up differently before assuming a "clean slate," since a real
machine rarely is one:

- **Power management**: won't recommend `tlp` if `power-profiles-daemon`
  is already active (see above), and flags it as a conflict rather than a
  recommendation if both end up running.
- **Firewall**: won't suggest enabling `ufw` if `firewalld` is already the
  active firewall manager.
- **Audio conflict**: won't flag PulseAudio vs. PipeWire if `pulseaudio`'s
  service is already masked, a common sign someone already migrated away
  from it deliberately and just never purged the package.
- **Dual-boot / GRUB**: skips the os-prober check entirely on a system
  that isn't using GRUB at all (e.g. systemd-boot), instead of proposing a
  fix that would only fail.
- **LUKS enrollment**: if a previous run's keyfile exists but never made
  it into `/etc/crypttab` (interrupted run, or a hand-edited crypttab
  later), `enroll-drive` finishes the job using the existing keyfile
  instead of treating the half-finished state as done, or asking for the
  passphrase again unnecessarily.
- **Storage pooling**: refuses to mount a pool over a path that already
  has something else mounted there directly (checked against the live
  mount table, not just `/etc/fstab`, so a manual mount the user set up by
  hand is still caught).
- **Swap file creation**: falls back to `dd` if `fallocate` is refused (a
  known btrfs limitation for swap files), and marks the file no-COW
  first, which btrfs requires for a working swap file.

## Driver health checks

`maximinus scan` doesn't just check whether a driver package is installed —
it checks whether it's actually the one running, and whether it conflicts
with something else. This is what catches the classic Mint/Ubuntu failure
mode of ending up with two NVIDIA driver packages installed at once, which
leaves *neither* one working:

- **Conflicting packages**: more than one `nvidia-driver-*`/legacy
  `nvidia-NNN` package installed simultaneously.
- **Module vs. package mismatch**: a driver package is installed but its
  kernel module isn't actually loaded.
- **nouveau vs. nvidia**: the open-source nouveau driver loaded instead of
  the installed proprietary one — they can't both drive the same GPU.
- **Secure Boot**: enabled with the nvidia module not loaded, the most
  common silent cause (an unsigned proprietary module gets refused with no
  obvious error).
- **`nvidia-smi` failing**: the kernel module is loaded but userspace can't
  talk to it — typically a version mismatch between the module and the
  installed libraries.
- **AMD**: neither `amdgpu` nor `radeon` loaded, or both loaded at once.
- **CPU microcode**: the wrong vendor's microcode package installed (e.g.
  `intel-microcode` on an AMD CPU).

See [maximinus/detectors/driver_health.py](maximinus/maximinus/detectors/driver_health.py).
Every finding here is read-only detection — remediation (purging a
package, blacklisting nouveau, enrolling a MOK key) can affect whether the
display comes up at all, so it's reported as a specific command for you to
run, never executed automatically.

## Drive integration (storage pooling) — a separate, explicit opt-in

Storage pooling changes an ongoing part of how your files behave (every
time you open a merged folder from now on, not just once), so it's kept
out of `scan`, `cleanup`, and the ordinary judgment-call list entirely.
It only ever runs when you explicitly ask for it:

- **CLI**: `maximinus pool-drives` is its own command, never bundled into
  `cleanup`. It prints a full explanation of exactly what will change
  before asking for confirmation, not just a one-line description.
- **`cleanup`**: if pooling is available, it's listed in its own
  clearly-separated "Optional features" section, explicitly called out as
  *not* included in whatever `cleanup` is about to do.
- **GUI**: pooling gets its own screen after the judgment-call screen,
  never mixed into that list. Unlike judgment calls, it starts unchecked
  at every Risk Taking level, including High — turning it on always
  requires reading the explanation and checking the box yourself.

`maximinus pool-drives` makes several drives *act like* one pool of
storage, without moving or copying a single file:

- It looks for category folders (Downloads, Documents, Pictures, Videos,
  Music, Desktop) that exist in more than one place — e.g. `~/Downloads`
  on this install and `Downloads` under a second Mint install's home
  partition — and only proposes pooling folders whose structure already
  matches.
- It merges them using [mergerfs](https://github.com/trapexit/mergerfs), a
  FUSE union filesystem: the merged folder shows the combined contents of
  every branch (so a file browser sees one `Downloads`, not two), and free
  space reported for it is the sum across branches — new files land on
  whichever branch has the most room (`category.create=mfs`).
- The mount point is the original folder itself, which is included as one
  of the branches, so nothing currently in it becomes hidden or
  inaccessible — it's just now part of a bigger merged view.
- This is purely a live view: unmounting the pool (or removing the
  `/etc/fstab` line it adds) instantly returns every folder to exactly how
  it looked before, because the underlying files never moved.
- **Boot safety**: every pool's `/etc/fstab` line is written with `nofail`
  and one `x-systemd.requires-mounts-for=<branch>` per branch, plus short
  device/mount timeouts. This tells systemd to order the pool mount after
  each branch is mounted, wait only briefly for a slow branch, and — the
  important part — never block or fail the boot if a branch (a second
  drive that's unplugged, a partition that isn't mounted yet, mergerfs
  itself) doesn't come up in time. Worst case the merged folder just isn't
  mounted yet; it can't turn into an unbootable system or an emergency
  shell. `pool-drives` also warns (without blocking) if a branch lives on
  a drive that has no `/etc/fstab` entry of its own, since that branch
  won't be there yet at boot until it's mounted by other means.

See [maximinus/storage/](maximinus/storage/) for the implementation.

## Extending

Add new facts to a detector, then add a rule in `rules.yaml` that reacts to
them. No code changes needed for new hardware/software mappings — only new
rules.

## Roadmap

- [x] CLI prototype: detect + propose plan (dry run only)
- [ ] Execute plan behind confirmation (apt install, mount config, etc.)
- [ ] GTK visual menu to review/toggle proposed actions before applying
- [ ] Broader distro support beyond Linux Mint
