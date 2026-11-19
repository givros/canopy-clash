# Restoring the Unreal source assets

Project collaborators with access to the original assets can restore the editable characters, template assets and visual references after cloning the repository. Install Git LFS, Python 3.11 or newer, and GnuPG 2. Git for Windows includes GnuPG.

```sh
git lfs pull
python Tools/source_archives.py restore --key "/path/outside/repository/source-archives.key"
```

Obtain the key separately from the project owner. The default location on the owner's machine is `~/.codex/keys/canopy-clash/source-archives.key`. The command verifies each source file and restores it at its original project path. To restore to an empty directory, pass `--dest PATH`. Existing files with differing contents stop restoration before any files are copied.

After editing these assets, run `python Tools/source_archives.py refresh` with the same key. This updates only the groups whose source files changed. Commit the updated index, new parts and removed parts together. Each group consists of ordered parts of an AES-256 OpenPGP-encrypted gzip tar archive. The public website only needs the cooked game.
