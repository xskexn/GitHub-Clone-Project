The command line interface file processes the raw user text input, reads the argument, validate them and execute the correct python function.

Dynamic Dispatching is used to identify the commands and their relevant parameters : 
```powershell
pygit cat-file d672a8c
```

- `pygit` is the global executable command that triggers the `setup.py` package ([[Setup file]])
- `cat-file` this is the sub-command that identifies what function needs to be executed
- `d672a8c` the argument, which is the target value the sub-command acts upon

## Core Functions
### `init(args)`

```python
def init (args):

    data.init ()

    print (f'Initialized empty pygit repository in {os.getcwd()}/{data.GIT_DIR}')
```
Initializes the physical workspace by creating a folder to store structural data like object (`objects/`) and reference points (`refs/heads`).
### `hash-objects`

```python
def hash_object (args):

    with open (args.file, 'rb') as f:

        print (data.hash_object (f.read ()))
```
Takes a local file and compresses into pygit database by reading the raw contents of the target file, and generating a 40-characters SHA-1 cryptographic has of the file contents and saves it into `.pygit/objects/`, then prints it to the console

### `cat-file`

```python
def cat_file (args):

    sys.stdout.flush ()

    sys.stdout.buffer.write (data.get_object (args.object, expected=None))
```
Retrieves contents from the database, by taking a 40-character hash as argument looking up the specific file inside the `.python/objects`, reading its raw binary content and printing them back.

### `write-tree(args)`

```python
def write_tree (args):

    print(base.write_tree ())
```
Takes a snapshot of the current working directory structure its files and folders  creating a "tree" text file that combines the filenames and matching hashes into a single file then it hashes the whole tree file and stores it in the database.

### `read-tree(args)`

restores the project files from previously saved snapshots, by taking the tree object's hash parsing the tree file to find all the filename and content hashes and retrieving the content of those files from the databases and reconstructing them to onto the local disk.