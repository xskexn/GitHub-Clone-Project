import sys
import argparse
import textwrap
import subprocess
import os

from . import data
from . import base
from . import diff
from . import remote

def main():
    with data.change_git_dir('.'):
        args = parse_args()
        args.func(args)

def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest='command')
    commands.required = True

    oid = base.get_oid

    init_parser = commands.add_parser('init')
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser('hash-object')
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument('file')

    #Creating the subcommand name
    cat_file_parser = commands.add_parser('cat-file')
    # Attaches the command to the actual python function
    cat_file_parser.set_defaults(func=cat_file)
    # Registering the expected variable
    cat_file_parser.add_argument('object', type=oid)

    write_tree_parser = commands.add_parser('write-tree')
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser('read-tree')
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument('tree', type=oid)

    commit_parser = commands.add_parser('commit')
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument('-m', '--message', required=True)

    log_parser = commands.add_parser('log')
    log_parser.set_defaults(func=log)
    log_parser.add_argument('oid', default='@', type=oid, nargs='?')

    show_parser = commands.add_parser('show')
    show_parser.set_defaults(func=show)
    show_parser.add_argument('oid', default='@', type=oid, nargs='?')

    checkout_parser = commands.add_parser('checkout')
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument('commit')

    tag_parser = commands.add_parser ('tag')
    tag_parser.set_defaults(func=tag)
    tag_parser.add_argument('name')
    tag_parser.add_argument('oid', default='@', type=oid, nargs='?')

    k_parser = commands.add_parser('k')
    k_parser.set_defaults(func=k)

    branch_parser = commands.add_parser('branch')
    branch_parser.set_defaults(func=branch)
    branch_parser.add_argument('name', nargs='?')
    branch_parser.add_argument('start_point', default='@', type=oid, nargs='?')

    status_parser = commands.add_parser('status')
    status_parser.set_defaults(func=status)

    diff_parser = commands.add_parser('diff')
    diff_parser.set_defaults(func=_diff)
    diff_parser.add_argument ('--cached', action='store_true')
    diff_parser.add_argument ('commit', nargs='?')

    reset_parser = commands.add_parser('reset')
    reset_parser.set_defaults(func=reset)
    reset_parser.add_argument('commit', type=oid)

    merge_parser = commands.add_parser ('merge')
    merge_parser.set_defaults (func=merge)
    merge_parser.add_argument ('commit', type=oid)

    merge_base_parser = commands.add_parser('merge-base')
    merge_base_parser.set_defaults(func=merge_base)
    merge_base_parser.add_argument('commit1', type=oid)
    merge_base_parser.add_argument('commit2', type=oid)

    fetch_parser = commands.add_parser('fetch')
    fetch_parser.set_defaults(func=fetch)
    fetch_parser.add_argument('remote')

    push_parser = commands.add_parser('push')
    push_parser.set_defaults(func=push)
    push_parser.add_argument('remote')
    push_parser.add_argument('branch')

    add_parser = commands.add_parser('add')
    add_parser.set_defaults(func=add)
    add_parser.add_argument('files', nargs='+')

    return parser.parse_args()

# Initialisation command creates a folder to store structural data
def init(args):
    base.init()
    print (f'Initialised empty pygit repository in {os.getcwd()}/{data.GIT_DIR}')

# Compresses target file into 40-char sha-1 crypto file and saves into object folder
def hash_object(args):
    with open(args.file, 'rb') as f:
        print(data.hash_object (f.read ()))

# Retrives content of the file by feeding it the 40-char address
def cat_file(args):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object(args.object, expected=None))

# Takes a snapshot of the current working directory 
def write_tree(args):
    print(base.write_tree())

# Restores the project files to previously saved snapshots
def read_tree(args):
    base.read_tree(args.tree)

# Creates a new object that stores all the information like author, time and hash address in a key value format
def commit(args):
    print(base.commit(args.message))

# prints commits message in a clean format
def _print_commit(oid, commit, refs=None):
    refs_str = f'({", ".join (refs)})' if refs else ''
    print(f'commit {oid}{refs_str}\n')
    print(textwrap.indent(commit.message, '    '))
    print('')

# Walks the list of commits and prints them 
def log(args):
    refs = {}
    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for oid in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(oid)
        _print_commit(oid, commit, refs.get(oid))

# The function shows various types of commit objects
def show(args):
    if not args.oid:
        return
    
    commit = base.get_commit(args.oid)
    parent_tree = None

    if commit.parents:
        parent_tree = base.get_commit(commit.parents[0]).tree

    _print_commit(args.oid, commit)
    result = diff.diff_trees(base.get_tree(parent_tree), base.get_tree(commit.tree))
    sys.stdout.flush()
    sys.stdout.buffer.write(result)

# Keeps track of all the changes by comparing working tree to commits
def _diff(args):
    oid = args.commit and base.get_oid(args.commit)

    if args.commit:
        # If a commit was provided explicitly, diff from it
        tree_from = base.get_tree(oid and base.get_commit (oid).tree)

    if args.cached:
        tree_to = base.get_index_tree()
        if not args.commit:
            # If no commit was provided, diff from HEAD
            oid = base.get_oid('@')
            tree_from = base.get_tree(oid and base.get_commit (oid).tree)
    else:
        tree_to = base.get_working_tree()
        if not args.commit:
            # If no commit was provided, diff from index
            tree_from = base.get_index_tree()

    result = diff.diff_trees(tree_from, tree_to)
    sys.stdout.flush()
    sys.stdout.buffer.write(result)

# Restores previous snapshot to the desired commit by taking 
def checkout(args):
    base.checkout(args.commit)

# Adds an alias to the target commit facilitating checkouts by aliases
def tag(args):
    base.create_tag(args.name, args.oid)

# Creating a new branch to facilitate the chekcout feature
def branch(args):
    if not args.name:
        current = base.get_branch_name()
        for branch in base.iter_branch_names():
            prefix = '*' if branch == current else ' '
            print (f'{prefix} {branch}')
    else:
        base.create_branch(args.name, args.start_point)
        print(f'Branch {args.name} created at {args.start_point[:10]}')

# Prints information about the current working directory
def status(args):
    HEAD = base.get_oid('@')
    branch = base.get_branch_name()
    if branch:
        print(f'On branch {branch}')
    else:
        print(f'HEAD detached at {HEAD[:10]}')

    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        print(f'Merging with {MERGE_HEAD[:10]}')

    print('\nChanges to be committed:\n')
    HEAD_tree = HEAD and base.get_commit(HEAD).tree
    for path, action in diff.iter_changed_files(base.get_tree(HEAD_tree), base.get_index_tree()):
        print(f'{action:>12}: {path}')

    print('\nChanges not staged for commit:\n')
    for path, action in diff.iter_changed_files(base.get_index_tree(), base.get_working_tree()):
        print(f'{action:>12}: {path}')

# Visualisation tool that draws all the refs and commits pointed by the ref
def k(args):
    dot = 'digraph commits {\n'
    oids = set()

    for refname, ref in data.iter_refs(deref=False):
        dot += f'"{refname}" [shape=note]\n'
        dot += f'"{refname}" -> "{ref.value}"\n'
        if not ref.symbolic:
            oids.add(ref.value)

    for oid in base.iter_commits_and_parents(oids):
        commit = base.get_commit(oid)
        dot += f'"{oid}" [shape=box style=filled label="{oid[:10]}"]\n'
        for parent in commit.parents:
            dot += f'"{oid}" -> "{parent}"\n'

    dot += '}'
    print(dot)

    try:
        with subprocess.Popen(['dot', '-Tpng', '-o', '.gitgraph.png'], stdin=subprocess.PIPE) as proc:
            proc.communicate(dot.encode()) 
            
        # Automatically open the generated graph image in Windows
        os.startfile('.gitgraph.png')
        
    except FileNotFoundError:
        print("Error: Graphviz is not installed or 'dot' is not in your system PATH.")

# Reverts workspace status to a previous commits and unliks the 'HEAD'
def reset(args):
    base.reset(args.commit)

# Merges commits together
def merge(args):
    base.merge(args.commit)

# Finds common ancestor of a commit and merges them
def merge_base(args):
    print(base.get_merge_base(args.commit1, args.commit2))

# Syncronisation tool that allows fetching from other extrenal local directories
def fetch (args):
    remote.fetch (args.remote)

# Uploads objects and synchronises local refs 
def push(args):
    remote.push(args.remote, f'refs/heads/{args.branch}')

# Creates a JSON index of the changed files
def add(args):
    base.add(args.files)