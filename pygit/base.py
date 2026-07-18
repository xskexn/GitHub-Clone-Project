import os
import itertools
import operator
import string

from pathlib import Path
from . import data
from collections import deque, namedtuple

def init ():
    data.init ()
    data.update_ref ('HEAD', data.RefValue (symbolic=True, value='refs/heads/master'))

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

# Used to clean up the file strucuture before reconstructing past version of the code
def _empty_current_directory():
    # taverses file system from bottom up 
    for root, dirnames, filenames in os.walk ('.', topdown=False):
        for filename in filenames:
            path = os.path.relpath (f'{root}/{filename}')
            # calls is_ignored to see if .pygit directory and files meant to be kept and skips over them
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
                pass

def read_tree(tree_oid):
    _empty_current_directory()
    for path, oid in get_tree(tree_oid, base_path='./').items():
        os.makedirs(os.path.dirname (path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object (oid))

# Build data structure that budles a directory snapshot to a historical timeline
def commit(message):
    # writes tree <hash> containing the current workspace snapshot
    commit = f'tree {write_tree ()}\n'
    HEAD = data.get_ref('HEAD').value
    # If a previous commit exists in HEAD, it adds a line saying parent <hash>
    if HEAD:
        commit += f'parent {HEAD}\n'
    commit += '\n'
    commit += f'{message}\n'
    # hashes  text file into .pygit/objects directory and points HEAD directly to new commit hash
    oid = data.hash_object(commit.encode(), 'commit')
    data.update_ref('HEAD', data.RefValue (symbolic=False, value=oid))
    return oid

# Status command to print infromation about the current working directory
def get_branch_name ():
    HEAD = data.get_ref ('HEAD', deref=False)
    if not HEAD.symbolic:
        return None
    HEAD = HEAD.value
    assert HEAD.startswith ('refs/heads/')
    return os.path.relpath (HEAD, 'refs/heads')


Commit = namedtuple('Commit', ['tree', 'parent', 'message'])

def get_commit(oid):
    parent = None
    # reads commit by parsing the custom text layout 
    commit = data.get_object (oid, 'commit').decode()
    lines = iter (commit.splitlines())
    # reads all the lines until the blank newline added in the commit text layout
    for line in itertools.takewhile(operator.truth, lines):
        key, value = line.split(' ', 1)
        # header parsing 
        if key == 'tree':
            tree = value
        elif key == 'parent':
            parent = value
        else:
            assert False, f'Unknown field {key}'
    # commit message parsing (after the blaknk line)
    message = '\n'.join(lines)
    return Commit(tree=tree, parent=parent, message=message)

def checkout(name):
    oid = get_oid(name)
    # gets paesed commit data
    commit = get_commit(oid)
    # cleans the project folder and unpackages the historical files
    read_tree(commit.tree)
    # update the head to new active position

    if is_branch (name):
        HEAD = data.RefValue (symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = data.RefValue (symbolic=False, value=oid)

    data.update_ref ('HEAD', HEAD, deref=False)

def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', data.RefValue (symbolic=False, value=oid))

def create_branch(name, oid):
    data.update_ref(f'refs/heads/{name}', data.RefValue (symbolic=False, value=oid))

def iter_branch_names ():
    for refname, _ in data.iter_refs ('refs/heads/'):
        yield os.path.relpath (refname, 'refs/heads/')

def is_branch (branch):
    return data.get_ref (f'refs/heads/{branch}').value is not None


# used to build and draw cisual graphical DAG representation of the commit history
def iter_commits_and_parents(oids):
    oids = deque(oids)
    visited = set()
    # walks back through commit history from commit to parent
    while oids:
        oid = oids.popleft()
        if not oid or oid in visited:
            continue
        visited.add(oid)
        yield oid

        commit = get_commit(oid)
        oids.appendleft(commit.parent)

# translator used to prevent the constant input of 40-char hashes
def get_oid(name):
    # '@' shortcut to directly check HEAD
    if name == '@': name = 'HEAD'
    # accepts alphanumeric input
    refs_to_try = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}',
    ]
    for ref in refs_to_try:
        if data.get_ref(ref, deref=False).value:
            return data.get_ref (ref).value
    # accepts hexadecimal inputs
    is_hex = all (c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    assert False, f'Unknown name {name}'

def is_ignored(path):
    return '.pygit' in Path(path).parts
