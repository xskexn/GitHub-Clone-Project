import os
import sys
import shutil
import tempfile
import unittest

# Ensure pygit modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cli
import base
import data


class TestPyGitCore(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_init(self):
        """Test repository initialisation"""
        data.init()
        self.assertTrue(os.path.exists('.git'))
        self.assertTrue(os.path.exists(os.path.join('.git', 'objects')))
        self.assertTrue(os.path.exists(os.path.join('.git', 'refs')))
        self.assertTrue(os.path.exists(os.path.join('.git', 'HEAD')))

    def test_hash_object(self):
        """Test hashing a file into an object"""
        data.init()
        file_path = 'hello.txt'
        content = b'Hello, PyGit World!\n'

        with open(file_path, 'wb') as f:
            f.write(content)

        oid = data.hash_object(content, 'blob')
        self.assertIsNotNone(oid)
        self.assertEqual(len(oid), 40)
        self.assertTrue(data.object_exists(oid))

    def test_write_tree_and_commit(self):
        """Test writing a tree and creating a commit."""
        data.init()

        # Create sample workspace
        with open('file1.txt', 'w') as f:
            f.write("First file content")
        with open('file2.txt', 'w') as f:
            f.write("Second file content")

        tree_oid = base.write_tree()
        self.assertIsNotNone(tree_oid)
        self.assertTrue(data.object_exists(tree_oid))

        commit_oid = base.commit("Initial commit")
        self.assertIsNotNone(commit_oid)
        self.assertEqual(data.get_HEAD().value, commit_oid)

    def test_checkout_and_branching(self):
        """Test branch creation and switching commits/branches."""
        data.init()

        # Commit 1
        with open('feature.txt', 'w') as f:
            f.write("Version 1")
        commit1_oid = base.commit("Commit 1")

        # Create branch 'feature-branch'
        base.create_branch('feature-branch', commit1_oid)
        self.assertTrue(data.get_ref('refs/heads/feature-branch').value == commit1_oid)

        # Commit 2 on master
        with open('feature.txt', 'w') as f:
            f.write("Version 2")
        commit2_oid = base.commit("Commit 2")

        # Checkout commit 1 / branch
        base.checkout('feature-branch')
        with open('feature.txt', 'r') as f:
            content = f.read()
        self.assertEqual(content, "Version 1")

    def test_tags(self):
        """Test creating annotated tags."""
        data.init()
        with open('version.txt', 'w') as f:
            f.write("v1.0.0")
        commit_oid = base.commit("Version release")

        base.create_tag('v1.0', commit_oid)
        tag_ref = data.get_ref('refs/tags/v1.0')
        self.assertEqual(tag_ref.value, commit_oid)


if __name__ == '__main__':
    unittest.main()