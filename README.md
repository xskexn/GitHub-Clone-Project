# Content-Addressable Storage & Version Control Engine

A fully functional, low-level Distributed Version Control System (DVCS) built from scratch in Python. This project reconstructs the internal “plumbing” and “synchronisation” commands of Git, demonstrating a deep understanding of file systems, data integrity, and system architecture.

## Core Architecture & Features

* Content-Addressable Storage: Implemented a secure object database using SHA-1 cryptographic hashing to guarantee data integrity across project snapshots.
* Merkle Tree Directory Mapping: Designed Recursive directory tree generation to serialise folder structures into flat, byte-aligned database entries.
* Directed Acyclic Graph (DAG) History: Modelled commit history as a DAG, enabling branching, time travel (checkout), and history lookups.
* Binary Index Parsing: Developed a high-performance binary parser using Python’s struct interface to deserialise the staging area (DIRC format) mapped to strict 8-byte alignment boundaries.
* Visual History Graphing: Integrated Graphviz to dynamically render the commit history and branch pointers into a visual DAG image.

## Tech Stack

* Language: Python 3 (Standard Library Only)
* Systems Programming: hashlib (SHA-1), zlib (Compression), struct (Binary Packing), os/sys (File System I/O)
* Visualisation: Graphviz (dot)

---

## Project Structure

How the internal .pygit database mimics real Git’s physical layout:

```plaintext
.pygit/
├── HEAD                # Pointer to the currently checked-out branch
├── index               # Binary staging area mapping files to object hashes
├── objects/            # The Content-Addressable Database (Blobs, Trees, Commits)
│   │   └── 72a8c...    # Zlib-compressed file content
└── refs/
    ├── heads/          # Local branch pointers (e.g., main, feature-branch)
    └── tags/           # Named pointers to specific historical commits
```
Commands

## Initialisation and hashing

```python
> pygit init # Initialises an empty .pygit repository in the current directory.

> pygit hash-object <file> # Compresses file, writes to database, and outputs the 40-char SHA-1 hash.

> pygit cat-file <hash> # Reads a compressed object from the database and prints its actual content.
```

## Commits & History

```python
> pygit commit -m "<msg>" # Snapshots the working directory into a Tree, creates a Commit object, and updates HEAD.

> pygit log  # Walks the parent links of the commit and prints the history.

> pygit status # Compares working directory, index, and HEAD to show modified files.

> pygit diff # Prints uncommitted changes to the terminal.
```


## Branching and navigation

```python
> pygit branch <name> # Creates a new branch in refs/heads/ pointing to the current commit.

> pygit checkout <branch> # Wipes the working directory and restores files to match the target commit state.

> pygit k # Generates a visual map of all branches and commits.
```


Testing

```python
python -m unittest discover -s tests
```
