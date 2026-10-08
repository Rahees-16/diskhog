#!/usr/bin/env python3
"""diskhog: report (and optionally remove) reclaimable build/dependency dirs."""
import argparse
import json
import os
import shutil
import sys

TARGETS = {"node_modules", "build", ".gradle", "__pycache__", ".venv",
           "target", "dist", ".next"}
DEFAULT_EXCLUDE_FILE = "~/.config/devtools/exclude"


def load_excludes(path=None):
    """Read excluded directory names (one per line, '#' comments).

    Path defaults to $DEVTOOLS_EXCLUDE_FILE, else ~/.config/devtools/exclude.
    A missing or unreadable file means no exclusions.
    """
    path = path or os.environ.get("DEVTOOLS_EXCLUDE_FILE") or DEFAULT_EXCLUDE_FILE
    names = set()
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    names.add(line)
    except OSError:
        pass
    return names


def dir_size(path):
    """Total bytes of regular files under path, not following symlinks."""
    total = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def scan(root, targets=TARGETS, excluded=frozenset()):
    """Return list of (path, size) for matching dirs, largest first.

    Symlinks are skipped; matched dirs are not descended into (no nesting).
    Directories whose name is in `excluded` are never scanned.
    """
    results = []
    stack = [os.path.abspath(root)]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if e.is_symlink() or not e.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if e.name in excluded:
                        continue
                    if e.name in targets:
                        results.append((e.path, dir_size(e.path)))
                    else:
                        stack.append(e.path)
        except OSError:
            pass
    results.sort(key=lambda r: (-r[1], r[0]))
    return results


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def clean(items):
    """Remove each (path, size); never follows symlinks. Returns freed bytes."""
    freed = 0
    for path, size in items:
        if os.path.islink(path) or not os.path.isdir(path):
            continue
        shutil.rmtree(path, ignore_errors=True)
        freed += size
    return freed


def main(argv=None, stdin=sys.stdin, out=sys.stdout):
    p = argparse.ArgumentParser(description="Report reclaimable space.")
    p.add_argument("root", nargs="?", default=os.path.expanduser("~/code"))
    p.add_argument("--top", type=int, metavar="N", help="show only N largest")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--clean", action="store_true",
                   help="delete listed dirs (dry run otherwise)")
    p.add_argument("--exclude", action="append", default=[], metavar="NAME",
                   help="directory name to never scan or clean (repeatable); "
                        "also read from " + DEFAULT_EXCLUDE_FILE)
    p.add_argument("--yes", action="store_true", help="skip confirmation")
    a = p.parse_args(argv)

    if not os.path.isdir(a.root):
        print(f"error: not a directory: {a.root}", file=sys.stderr)
        return 2

    found = scan(a.root, excluded=load_excludes() | set(a.exclude))
    total = sum(s for _, s in found)
    shown = found[:a.top] if a.top else found
    shown_total = sum(s for _, s in shown)

    if a.json:
        print(json.dumps({"root": os.path.abspath(a.root),
                          "items": [{"path": p_, "bytes": s} for p_, s in shown],
                          "total_bytes": total,
                          "shown_bytes": shown_total,
                          "dry_run": not a.clean}, indent=2), file=out)
    else:
        for path, size in shown:
            print(f"{human(size):>10}  {path}", file=out)
        print(f"{human(total):>10}  TOTAL ({len(found)} dirs)", file=out)
        if a.top and len(found) > len(shown):
            print(f"(showing top {len(shown)}: {human(shown_total)})", file=out)

    if not a.clean:
        if not a.json:
            print("Dry run. Use --clean to remove.", file=out)
        return 0
    if not shown:
        return 0

    if not a.yes:
        print(f"\nAbout to DELETE the {len(shown)} dirs listed above "
              f"({human(shown_total)}). Type 'yes' to confirm: ",
              end="", file=sys.stderr, flush=True)
        if stdin.readline().strip() != "yes":
            print("Aborted.", file=sys.stderr)
            return 1
    freed = clean(shown)
    print(f"Removed {len(shown)} dirs, freed {human(freed)}.",
          file=sys.stderr if a.json else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
