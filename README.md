# diskhog

Finds reclaimable build and dependency directories (`node_modules`, `build`,
`.gradle`, `__pycache__`, `.venv`, `target`, `dist`, `.next`) under a root
directory (default `~/code`), sorted largest first with a total. Optionally
deletes them.

## Install

No dependencies beyond Python 3 (standard library only).

    git clone https://github.com/Rahees-16/diskhog.git
    cd diskhog
    python3 diskhog.py --help

## Usage

    python3 diskhog.py                         # dry run on ~/code
    python3 diskhog.py ~/projects --top 10     # 10 largest only
    python3 diskhog.py ~/projects --json       # machine-readable output
    python3 diskhog.py ~/projects --clean      # lists dirs, asks you to type 'yes'
    python3 diskhog.py ~/projects --clean --yes   # no prompt

`--clean` only deletes the directories shown, so `--top N` limits what is removed.

## Excluding directories

Excluded directory names are never scanned or cleaned. Use the repeatable flag:

    python3 diskhog.py ~/code --exclude private-repo --exclude other-repo

or list names in `~/.config/devtools/exclude` (one per line, `#` for comments;
a missing file means no exclusions). This file is read by default. Set
`DEVTOOLS_EXCLUDE_FILE` to use a different path.

    # ~/.config/devtools/exclude
    private-repo   # never touch this one

## Safety

- Dry run by default; nothing is deleted without `--clean`.
- `--clean` requires typing `yes`, or passing `--yes`.
- Symlinks are skipped and never followed, for both scanning and deletion.
- Matched directories are not descended into, so nothing is double counted.

## Tests

    python3 -m unittest -v

## License

MIT, see [LICENSE](LICENSE).
