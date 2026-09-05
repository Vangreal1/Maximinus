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

## Drive integration (storage pooling)

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
