import os
import itertools
import operator
import string

from pathlib import Path
from . import data
from collections import deque, namedtuple

def write_tree(directory='.'):
    entries = []
    # loops through the current working directory
    with os.scandir (directory) as it:
        for entry in it:
            full = os.path.join(directory, entry.name)
            # Checks if item is something in the 'gitIgnore' and just skips them (like .pygit directory)
            if is_ignored(full):
                continue
            # file found in the search after exploring the subfolders
            if entry.is_file(follow_symlinks=False):
                type_ = 'blob'
                # reading the contents
                with open (full, 'rb') as f:
                    # feeds it into the object hash function to get the oid (unique hash)
                    oid = data.hash_object(f.read ())
            elif entry.is_dir(follow_symlinks=False):
                type_ = 'tree'
                # this process is done recusively and called on all the subfolders until a file is reached
                oid = write_tree(full)
                # tree building step where all entires are sorted alphabethically into a strucutred plain text string
            entries.append((entry.name, oid, type_))

    tree = ''.join (f'{type_} {oid} {name}\n'
                    for name, oid, type_
                    in sorted (entries))
    return data.hash_object(tree.encode (), 'tree')

def _iter_tree_entries(oid):
    if not oid:
        return
    tree = data.get_object(oid, 'tree')
    for entry in tree.decode().splitlines():
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name

def get_tree(oid, base_path=''):
    result = {}
    for type_, oid, name in _iter_tree_entries(oid):
        assert '/' not in name
        assert name not in ('..', '.')
        path = base_path + name
        if type_ == 'blob':
            result[path] = oid
        elif type_ == 'tree':
            result.update(get_tree (oid, f'{path}/'))
        else:
            assert False, f'Unknown tree entry {type_}'
    return result

def _empty_current_directory():
    for root, dirnames, filenames in os.walk ('.', topdown=False):
        for filename in filenames:
            path = os.path.relpath (f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile (path):
                continue
            os.remove(path)
        for dirname in dirnames:
            path = os.path.relpath (f'{root}/{dirname}')
            if is_ignored(path):
                continue
            try:
                os.rmdir(path)
            except (FileNotFoundError, OSError):
                # Deletion might fail if the directory contains ignored files,
                # so it's OK
                pass

def read_tree(tree_oid):
    _empty_current_directory()
    for path, oid in get_tree(tree_oid, base_path='./').items():
        os.makedirs(os.path.dirname (path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object (oid))

def commit(message):
    commit = f'tree {write_tree ()}\n'
    HEAD = data.get_ref('HEAD').value
    if HEAD:
        commit += f'parent {HEAD}\n'
    commit += '\n'
    commit += f'{message}\n'
    oid = data.hash_object(commit.encode(), 'commit')
    data.update_ref('HEAD', data.RefValue (symbolic=False, value=oid))
    return oid

Commit = namedtuple('Commit', ['tree', 'parent', 'message'])

def get_commit(oid):
    parent = None

    commit = data.get_object (oid, 'commit').decode()
    lines = iter (commit.splitlines())
    for line in itertools.takewhile(operator.truth, lines):
        key, value = line.split(' ', 1)
        if key == 'tree':
            tree = value
        elif key == 'parent':
            parent = value
        else:
            assert False, f'Unknown field {key}'

    message = '\n'.join(lines)
    return Commit(tree=tree, parent=parent, message=message)

def checkout(oid):
    commit = get_commit(oid)
    read_tree(commit.tree)
    data.update_ref ('HEAD', data.RefValue (symbolic=False, value=oid))

def create_tag(name, oid):
    data.update_ref (f'refs/tags/{name}', data.RefValue (symbolic=False, value=oid))

def create_branch (name, oid):
    data.update_ref (f'refs/tags/{name}', data.RefValue (symbolic=False, value=oid))

def iter_commits_and_parents(oids):
    oids = deque(oids)
    visited = set()

    while oids:
        oid = oids.popleft()
        if not oid or oid in visited:
            continue
        visited.add(oid)
        yield oid

        commit = get_commit(oid)
        oids.appendleft(commit.parent)

def get_oid(name):
    if name == '@': name = 'HEAD'
    refs_to_try = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}',
    ]
    for ref in refs_to_try:
        if data.get_ref (ref).value:
            return data.get_ref (ref).value

    is_hex = all (c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    assert False, f'Unknown name {name}'

def is_ignored(path):
    return '.pygit' in Path(path).parts
