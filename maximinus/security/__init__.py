"""Privilege and credential handling.

Design constraints (do not relax these without re-reading the rationale):

- We never write the user's sudo password or LUKS passphrase to disk, to
  an env var, or to a log. Passphrases exist only as local variables for
  the duration of the one command that needs them.
- Privilege elevation reuses sudo's own ticket cache (`sudo -v`) instead of
  inventing a second credential store. If the user already has a live sudo
  ticket, they are not prompted again.
- Drive "unlock once, don't ask again" is implemented by enrolling a new
  random keyfile into the LUKS header (via cryptsetup, authenticated with
  the passphrase the user typed) and registering it in /etc/crypttab so
  the kernel unlocks the drive automatically on boot. The passphrase is
  never stored — only a freshly generated, unrelated keyfile is.
"""
