import io
import json
import os
import tempfile
import unittest

import diskhog


def mk(root, rel, size=0):
    d = os.path.join(root, rel)
    os.makedirs(d, exist_ok=True)
    if size:
        with open(os.path.join(d, "f.bin"), "wb") as f:
            f.write(b"x" * size)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = self._t.name
        self.addCleanup(self._t.cleanup)
        self.excl_file = os.path.join(self._t.name + "-excl.txt")
        os.environ["DEVTOOLS_EXCLUDE_FILE"] = self.excl_file
        self.addCleanup(os.environ.pop, "DEVTOOLS_EXCLUDE_FILE", None)
        self.addCleanup(lambda: os.path.exists(self.excl_file)
                        and os.remove(self.excl_file))

    def run_main(self, args, stdin=""):
        out = io.StringIO()
        rc = diskhog.main(args, stdin=io.StringIO(stdin), out=out)
        return rc, out.getvalue()


class ScanTests(Base):
    def test_finds_sorted_largest_first(self):
        mk(self.root, "a/node_modules", 100)
        mk(self.root, "b/build", 300)
        mk(self.root, "c/src", 999)  # not a target
        res = diskhog.scan(self.root)
        self.assertEqual([s for _, s in res], [300, 100])
        self.assertTrue(res[0][0].endswith("build"))

    def test_no_nested_double_count(self):
        mk(self.root, "p/node_modules/x/node_modules", 50)
        res = diskhog.scan(self.root)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][1], 50)

    def test_skips_symlinks(self):
        real = mk(self.root, "real_store", 10)
        os.symlink(real, os.path.join(self.root, "node_modules"))
        mk(self.root, "other", 0)
        os.symlink(mk(self.root, "elsewhere/x", 5),
                   os.path.join(self.root, "other", "dist"))
        self.assertEqual(diskhog.scan(self.root), [])

    def test_excluded_arg(self):
        mk(self.root, "private-repo/app/build", 500)
        mk(self.root, "other/build", 10)
        res = diskhog.scan(self.root, excluded={"private-repo"})
        self.assertEqual([s for _, s in res], [10])

    def test_load_excludes_file(self):
        with open(self.excl_file, "w") as f:
            f.write("# comment\nprivate-repo\n\n  secret-app  # trailing\n")
        self.assertEqual(diskhog.load_excludes(), {"private-repo", "secret-app"})

    def test_load_excludes_missing_file(self):
        self.assertEqual(diskhog.load_excludes(), set())

    def test_size_ignores_symlinked_files(self):
        d = mk(self.root, "node_modules", 20)
        os.symlink(os.path.join(d, "f.bin"), os.path.join(d, "link"))
        self.assertEqual(diskhog.scan(self.root)[0][1], 20)


class CliTests(Base):
    def test_dry_run_default_deletes_nothing(self):
        d = mk(self.root, "a/dist", 10)
        rc, out = self.run_main([self.root])
        self.assertEqual(rc, 0)
        self.assertIn("Dry run", out)
        self.assertTrue(os.path.isdir(d))

    def test_clean_requires_confirmation(self):
        d = mk(self.root, "a/dist", 10)
        rc, _ = self.run_main([self.root, "--clean"], stdin="no\n")
        self.assertEqual(rc, 1)
        self.assertTrue(os.path.isdir(d))
        rc, _ = self.run_main([self.root, "--clean"], stdin="")
        self.assertEqual(rc, 1)
        self.assertTrue(os.path.isdir(d))

    def test_clean_with_typed_yes(self):
        d = mk(self.root, "a/dist", 10)
        keep = mk(self.root, "a/src", 10)
        rc, out = self.run_main([self.root, "--clean"], stdin="yes\n")
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(d))
        self.assertTrue(os.path.isdir(keep))
        self.assertIn(d, out)  # printed before deleting

    def test_clean_yes_flag(self):
        d = mk(self.root, "a/.next", 10)
        rc, _ = self.run_main([self.root, "--clean", "--yes"])
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(d))

    def test_clean_never_follows_symlink_target(self):
        outside = mk(self.root, "keepme", 10)
        scan_root = os.path.join(self.root, "scan")
        os.makedirs(scan_root)
        os.symlink(outside, os.path.join(scan_root, "build"))
        self.run_main([scan_root, "--clean", "--yes"])
        self.assertTrue(os.path.exists(os.path.join(outside, "f.bin")))

    def test_top_limits_clean_scope(self):
        big = mk(self.root, "a/build", 500)
        small = mk(self.root, "b/dist", 5)
        self.run_main([self.root, "--top", "1", "--clean", "--yes"])
        self.assertFalse(os.path.exists(big))
        self.assertTrue(os.path.exists(small))

    def test_exclude_flag_protects_dir(self):
        keep = mk(self.root, "private-repo/build", 500)
        gone = mk(self.root, "other/build", 10)
        self.run_main([self.root, "--exclude", "private-repo", "--clean", "--yes"])
        self.assertTrue(os.path.isdir(keep))
        self.assertFalse(os.path.exists(gone))

    def test_exclude_file_protects_dir(self):
        with open(self.excl_file, "w") as f:
            f.write("private-repo\n")
        keep = mk(self.root, "private-repo/build", 500)
        gone = mk(self.root, "other/build", 10)
        self.run_main([self.root, "--clean", "--yes"])
        self.assertTrue(os.path.isdir(keep))
        self.assertFalse(os.path.exists(gone))

    def test_json(self):
        mk(self.root, "a/build", 7)
        rc, out = self.run_main([self.root, "--json"])
        data = json.loads(out)
        self.assertEqual(data["total_bytes"], 7)
        self.assertEqual(data["items"][0]["bytes"], 7)
        self.assertTrue(data["dry_run"])


if __name__ == "__main__":
    unittest.main()
