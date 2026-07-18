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

    print (f'Initialised empty pygit repository in {os.getcwd()}/{data.GIT_DIR}')
```
Initialises the physical workspace by creating a folder to store structural data like object (`objects/`) and reference points (`refs/heads`).
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

```python
def read_tree (args):

    base.read_tree (args.tree)
```
Restores the project files from previously saved snapshots, by taking the tree object's hash parsing the tree file to find all the filename and content hashes and retrieving the content of those files from the databases and reconstructing them to onto the local disk.

### `commit(arg)`

```python
def commit(args):

    print(base.commit(args.message))
```
Records a permanent snapshot of the workspace along with a descriptive message and historical timeline, i calls `write_tree` logic to snapshot the current working directory. The current  `HEAD` hash will serve as the 'parent' reference link.
The function also requires a mandatory message string `-m` and bundles all this metadata (message, parent hash, tree hash) into a plain text string, hashes it into an object, and then moves `HEAD` forward to point to this brand-new commit hash.

### `log(args)`

```python
def log(args):

    for oid in base.iter_commits_and_parents({args.oid}):

        commit = base.get_commit(oid)

  

        print(f'commit {oid}\n')

        print(textwrap.indent(commit.message, '    '))

        print('')
```
Walks backward through the project's historical timeline and prints a text audit trail of how the code changed.
It accepts optional string hash which defaults to the current commit and passes it to the generator function `base.iter_commits_and_parents`, which loops from commit to parent commit extracting metadata via the `base.get_commit(oid)` function, to then cleanly printing it out.

### `checkout(args)`

```python
def checkout (args):

    base.checkout(args.oid)
```
Travels in a timeline the physical working directory to match the exact state of a given historical commit, updating active status. It calls `base.checkout(args.oid)` which unpackages the commit object located at that hash, reads the embedded `tree` hash inside it, then uses `read_tree` logic to wipe and overwrite the local files. 

### `tag(args)`

```python
def tag(args):

    base.create_tag(args.name, args.oid)
```
Appends a permanent alias to a specific commit hash to prevent the memorisation of the 40-character hash string. it accepts a name string and a target has defaulting to the current location `@` and creates a small static file inside `.pygit/refs/tags/` registry .

### `branch (args)`

```python
def branch (args):

    base.create_branch(args.name, args.start_point)

    print (f'Branch {args.name} created at {args.start_point[:10]}')
```
It accepts a branch name and a starting point (defaulting to the current working directory `@`). It triggers `base.create_branch(args.name, args.start_point)` it behaves identically to a tag by writing a reference file inside `.pygit/refs/heads/`, with the structural difference of the pointer that will automatically slide forward every time `pygit commit` is ran.

### `k(args)`

```python
def k(args):

    dot = 'digraph commits {\n'

    oids = set()

  

    for refname, ref in data.iter_refs():

        dot += f'"{refname}" [shape=note]\n'

        dot += f'"{refname}" -> "{ref.value}"\n'

        oids.add (ref.value)

  
  

    for oid in base.iter_commits_and_parents(oids):

        commit = base.get_commit(oid)

        dot += f'"{oid}" [shape=box style=filled label="{oid[:10]}"]\n'

        if commit.parent:

            dot += f'"{oid}" -> "{commit.parent}"\n'

  

    dot += '}'

    print(dot)

  

    try:

        with subprocess.Popen(

            ['dot', '-Tpng', '-o', '.gitgraph.png'],

            stdin=subprocess.PIPE) as proc:

            proc.communicate(dot.encode())

        # Automatically open the generated graph image in Windows

        os.startfile('.gitgraph.png')

    except FileNotFoundError:

        print("Error: Graphviz is not installed or 'dot' is not in your system PATH.")
```
This is a visual tool that compiles all branches, tags, HEAD pointers and historical commit blocks into an DAG  graph image. It builds a data block structured in DOT language syntax by looping through active references via `data.iter_refs()` to draw branches or tag labels and walks down the commit history via `base.iter_commits_and_parents` to draw boxes for each commit. It passes this string dynamically to an external Graphviz `dot` process via a Python `subprocess.Popen` pipeline to render a `.gitgraph.png` file.