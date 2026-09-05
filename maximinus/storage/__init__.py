"""Storage pooling: make several drives act like one, without moving data.

Uses mergerfs (a FUSE union filesystem) to present multiple existing
directories — e.g. ~/Downloads on this install and Downloads on a second
Mint install's home partition — as a single merged folder. Nothing is
copied or moved: mergerfs just forwards reads/writes to whichever branch
already has (or, for new files, is chosen to receive) the file. Free space
reported for the pool is the sum across branches, which is what makes it
"act like" one combined pool of storage instead of one partition's worth.
"""
