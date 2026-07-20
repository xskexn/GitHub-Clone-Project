import os
import shutil
import tempfile
import unittest

from pygit import data


class TestPygitData(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory before each test."""
        self.test_dir = tempfile.mkdtemp()
        self.old_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Restore previous working directory and clean up temp folder."""
        os.chdir(self.old_dir)
        shutil.rmtree(self.test_dir)

    def test_init_creates_pygit_structure(self):
        """Verify that init() creates .pygit and objects folder."""
        data.init()
        self.assertTrue(os.path.exists(".pygit"))
        self.assertTrue(os.path.exists(".pygit/objects"))

    def test_hash_and_get_object(self):
        """Verify hashing data stores it correctly and retrieves exact contents."""
        data.init()
        content = b"Unit test payload sample"

        # Hash object
        oid = data.hash_object(content, type_="blob")

        # Retrieve object
        retrieved_content = data.get_object(oid, expected="blob")

        self.assertEqual(content, retrieved_content)


if __name__ == "__main__":
    unittest.main()