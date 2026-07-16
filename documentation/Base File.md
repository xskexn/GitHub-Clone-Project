**`base.py`** understands structure. It reads files and folders, organises them into hierarchical lists, writes them as recursive `tree` objects, and knows how to restore them back onto the disk.
### `write_tree(directory='.')` — Snapping the Workspace
```python
def write_tree (directory='.'):
    entries = []
    # loops through the current working directory
    with os.scandir (directory) as it:
        for entry in it:
            full = os.path.join(directory, entry.name)
            # Checks if item is something in the 'gitIgnore' and just skips them (like .pygit directory)
            if is_ignored (full):
                continue
            # file found in the search after exploring the subfolders
            if entry.is_file (follow_symlinks=False):
                type_ = 'blob'
                # reading the contents of the target file
                with open (full, 'rb') as f:
                    # feeds it into the object hash function to get the oid (unique hash address)
                    oid = data.hash_object (f.read ())
            elif entry.is_dir (follow_symlinks=False):
                type_ = 'tree'
                # this process is done recusively and called on all the subfolders until a file is reached
                oid = write_tree (full)
                # tree building step where all entires are sorted alphabethically into a strucutred plain text string
            entries.append ((entry.name, oid, type_))
    tree = ''.join (f'{type_} {oid} {name}\n'
                    for name, oid, type_
                    in sorted (entries))
    return data.hash_object (tree.encode (), 'tree')
```
**Example output**:
```plaintext
blob 4b825dc642cb6eb9a0d9e54eef7d3d509f1b2d4b index.html
tree a3f98216bcd3f218acbde02f1b829381c828d928 src
```
A Git `commit` hash is ultimately just pointing to a parent `tree` hash. If you change a single character in a file, its `blob` hash changes. Because that blob hash changes, the text of the `tree` changes, which changes the `tree` hash, which changes the `commit` hash. This is how Git guarantees absolute security nothing can be modified in secret!

### `get_tree` and `read_tree` — Restores old commits

`_iter_tree_entries(oid)` is a generator that read a stored tree object, split its text line-by-line and parses out the metadata: the type, the hash and the filename
**`get_tree(oid)`**: This recursively reads through the tree listings and flattens them into a Python dictionary structure of paths and target file hashes:
```python
{
    'index.html': '4b825dc642cb6eb9a...',
    'src/main.py': '8c2ef83920dc1ab8...'
}
```
- **`read_tree(tree_oid)`**: This takes that dictionary, physically writes those file contents back onto your hard drive