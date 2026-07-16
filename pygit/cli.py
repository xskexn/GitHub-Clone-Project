import argparse
import textwarp
import os
import sys

from . import data
from . import base

def main():
    args = parse_args()
    args.func(args)

def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest='command')
    commands.required = True

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
    cat_file_parser.add_argument('object')

    write_tree_parser = commands.add_parser('write-tree')
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser('read-tree')
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument('tree')

    commit_parser = commands.add_parser('commit')
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument('-m', '--message', required=True)

    log_parser = commands.add_parser('log')
    log_parser.set_defaults(func=log)
    log_parser.add_argument ('oid', nargs='?')

    return parser.parse_args()

# Initialisation command creates a folder to store structural data
def init(args):
    data.init()
    print (f'Initialised empty pygit repository in {os.getcwd()}/{data.GIT_DIR}')

# Compresses target file into 40-char sha-1 crypto file and saves into object folder
def hash_object(args):
    with open(args.file, 'rb') as f:
        print(data.hash_object (f.read ()))

# Retrives content of the file by feeding it the 40-char address
def cat_file(args):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object (args.object, expected=None))

# Takes a snapshot of the current working directory 
def write_tree(args):
    print(base.write_tree())

# Restores the project files to previously saved snapshots
def read_tree(args):
    base.read_tree(args.tree)

# Creates a new object that stores all the information like author, time and hash address in a key value format
def commit(args):
    print(base.commit(args.message))

# Walks the list of commits and prints them 
def log(args):
    oid = args.oid or data.get_HEAD ()
    while oid:
        commit = base.get_commit(oid)

        print(f'commit {oid}\n')
        print(textwrap.indent(commit.message, '    '))
        print('')

        oid = commit.parent