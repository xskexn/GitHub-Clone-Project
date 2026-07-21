"""Handles core logic layer of your version control system  
 and the construction of the Directed Acyclic Graph (DAG) 
and manipulates the local files on the drive"""
import os
import itertools
import operator
import string

from pathlib import Path
from . import data
from . import diff
from collections import deque, namedtuple

def init ():
    data.init()
    data.update_ref('HEAD', data.RefValue (symbolic=True, value='refs/heads/master'))

# converts incex into nested dictonary strucutre representing folder structure
def write_tree():
    # Index is flat, we need it as a tree of dicts
    index_as_tree = {}
    with data.get_index() as index:
        for path, oid in index.items():
            path = path.split('/')
            dirpath, filename = path[:-1], path[-1]

            current = index_as_tree
            # Find the dict for the directory of this file
            for dirname in dirpath:
                current = current.setdefault(dirname, {})
            current[filename] = oid

    def write_tree_recursive(tree_dict):
        entries = []
        for name, value in tree_dict.items():
            if type (value) is dict:
                type_ = 'tree'
                oid = write_tree_recursive(value)
            else:
                type_ = 'blob'
                oid = value
            entries.append((name, oid, type_))
        # recursive helprer function that formats folder contents into a (type hash filename) before hashing it into the database. 
        tree = ''.join (f'{type_} {oid} {name}\n' for name, oid, type_ in sorted(entries))
        return data.hash_object(tree.encode(), 'tree')

    return write_tree_recursive(index_as_tree)

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

def get_working_tree():
    result = {}
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            with open (path, 'rb') as f:
                result[path] = data.hash_object (f.read ())
    return result

def get_index_tree ():
    with data.get_index () as index:
        return index

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

def read_tree(tree_oid, update_working=False):
    with data.get_index() as index:
        index.clear()
        index.update(get_tree(tree_oid))

        if update_working:
            _checkout_index(index)


def read_tree_merged(t_base, t_HEAD, t_other, update_working=False):
    with data.get_index() as index:
        index.clear()
        index.update(diff.merge_trees (get_tree(t_base), get_tree(t_HEAD), get_tree(t_other)))

        if update_working:
            _checkout_index(index)


def _checkout_index(index):
    _empty_current_directory()
    for path, oid in index.items():
        os.makedirs(os.path.dirname(f'./{path}'), exist_ok=True)
        with open (path, 'wb') as f:
            f.write(data.get_object(oid, 'blob'))

# Builds the commit text block and updates the current branch pointer.
def commit(message):
    # writes tree <hash> containing the current workspace snapshot
    commit = f'tree {write_tree()}\n'
    HEAD = data.get_ref('HEAD').value
    # If a previous commit exists in HEAD, it adds a line saying parent <hash>
    if HEAD:
        commit += f'parent {HEAD}\n'
    
    # builds the mathematical graph (DAG)
    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        commit += f'parent {MERGE_HEAD}\n'
        data.delete_ref('MERGE_HEAD', deref=False)

    commit += '\n'
    commit += f'{message}\n'
    # hashes  text file into .pygit/objects directory and points HEAD directly to new commit hash
    oid = data.hash_object(commit.encode(), 'commit')
    data.update_ref('HEAD', data.RefValue (symbolic=False, value=oid))
    return oid

# Status command to print infromation about the current working directory
def get_branch_name():
    HEAD = data.get_ref('HEAD', deref=False)
    if not HEAD.symbolic:
        return None
    HEAD = HEAD.value
    assert HEAD.startswith('refs/heads/')
    return os.path.relpath(HEAD, 'refs/heads')


Commit = namedtuple('Commit', ['tree', 'parents', 'message'])

# parses commit text file into py object
def get_commit(oid):
    parents = []
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
            parents.append(value)
        else:
            assert False, f'Unknown field {key}'
    # commit message parsing (after the blaknk line)
    message = '\n'.join(lines)
    return Commit(tree=tree, parents=parents, message=message)

# fetches the commit and restores its file 
def checkout(name):
    oid = get_oid(name)
    # gets parsed commit data
    commit = get_commit(oid)
    # cleans the project folder and unpackages the historical files
    read_tree(commit.tree)
    # update the head to new active position

    if is_branch(name):
        HEAD = data.RefValue(symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = data.RefValue(symbolic=False, value=oid)
    # unpacks files, updates the head to point to new location
    data.update_ref('HEAD', HEAD, deref=False)

def reset(oid):
    data.update_ref('HEAD', data.RefValue(symbolic=False, value=oid))

def merge(other):
    HEAD = data.get_ref('HEAD').value
    assert HEAD
    merge_base = get_merge_base (other, HEAD)
    c_other = get_commit(other)

    # Handles fast-forward merge
    if merge_base == HEAD:
        read_tree(c_other.tree)
        data.update_ref('HEAD', data.RefValue(symbolic=False, value=other))
        print('Fast-forward merge, no need to commit')
        return

    data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False, value=other))

    c_base = get_commit(merge_base)
    c_HEAD = get_commit(HEAD)
    read_tree_merged(c_base.tree, c_HEAD.tree, c_other.tree)
    print('Merged in working tree\nPlease commit')

def get_merge_base(oid1, oid2):
    parents1 = set(iter_commits_and_parents({oid1}))

    for oid in iter_commits_and_parents({oid2}):
        if oid in parents1:
            return oid
        
def is_ancestor_of(commit, maybe_ancestor):
    return maybe_ancestor in iter_commits_and_parents({commit})

def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', data.RefValue (symbolic=False, value=oid))

def create_branch(name, oid):
    data.update_ref (f'refs/heads/{name}', data.RefValue (symbolic=False, value=oid))

def iter_branch_names ():
    for refname, _ in data.iter_refs ('refs/heads/'):
        yield os.path.relpath (refname, 'refs/heads/')

def is_branch (branch):
    return data.get_ref (f'refs/heads/{branch}').value is not None

# used to build and draw visual graphical DAG representation of the commit history
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
        # Return first parent next
        oids.extendleft(commit.parents[:1])
        # Return other parents later
        oids.extend(commit.parents[1:])

def iter_objects_in_commits(oids):
    visited = set()

    def iter_objects_in_tree(oid):
        visited.add(oid) 
        # Must yield the oid before acccessing it (to allow caller to fetch it if needed)
        yield oid

        for type_, oid, _ in _iter_tree_entries(oid):
            if oid not in visited:
                if type_ == 'tree':
                    yield from iter_objects_in_tree(oid)
                else:
                    visited.add(oid)
                    yield oid

    for oid in iter_commits_and_parents(oids):
        yield oid
        commit = get_commit(oid)

        if commit.tree not in visited:
            yield from iter_objects_in_tree(commit.tree)


# translator used to prevent the constant input of 40-char hashes
def get_oid(name):
    # '@' shortcut to directly check HEAD
    if name == '@': name = 'HEAD'
    # list of accepted alphanumeric input
    refs_to_try = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}',
    ]

    for ref in refs_to_try:
        if data.get_ref(ref, deref=False).value:
            return data.get_ref (ref).value
    # if the list fails it check for hex inputs
    is_hex = all (c in string.hexdigits for c in name)

    if len(name) == 40 and is_hex:
        return name

    assert False, f'Unknown name {name}'

# Processes user provided files and directories and adds them to the index memory  
def add(filenames):
    def add_file(filename):
        # Normalize path
        filename = os.path.relpath(filename)
        with open (filename, 'rb') as f:
            oid = data.hash_object (f.read())
        index[filename] = oid

    def add_directory(dirname):
        for root, _, filenames in os.walk(dirname):
            for filename in filenames:
                # Normalize path
                path = os.path.relpath(f'{root}/{filename}')
                if is_ignored(path) or not os.path.isfile (path):
                    continue
                add_file(path)

    with data.get_index() as index:
        for name in filenames:
            if os.path.isfile(name):
                add_file(name)
            elif os.path.isdir(name):
                add_directory(name)

# checks path against .pygit folder 
def is_ignored(path):
    return '.pygit' in Path(path).parts
