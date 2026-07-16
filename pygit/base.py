import os
from pathlib import Path

from . import data

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
                # reading the contents
                with open (full, 'rb') as f:
                    # feeds it into the object hash function to get the oid (unique hash)
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

def _iter_tree_entries (oid):
    if not oid:
        return
    tree = data.get_object (oid, 'tree')
    for entry in tree.decode ().splitlines ():
        type_, oid, name = entry.split (' ', 2)
        yield type_, oid, name

def get_tree (oid, base_path=''):
    result = {}
    for type_, oid, name in _iter_tree_entries (oid):
        assert '/' not in name
        assert name not in ('..', '.')
        path = base_path + name
        if type_ == 'blob':
            result[path] = oid
        elif type_ == 'tree':
            result.update (get_tree (oid, f'{path}/'))
        else:
            assert False, f'Unknown tree entry {type_}'
    return result

def read_tree (tree_oid):
    for path, oid in get_tree (tree_oid, base_path='./').items ():
        os.makedirs (os.path.dirname (path), exist_ok=True)
        with open (path, 'wb') as f:
            f.write (data.get_object (oid))

def is_ignored (path):
    return '.pygit' in Path(path).parts
