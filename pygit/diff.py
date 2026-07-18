from collections import defaultdict

# Takes a list of tree and returns them grouped by filename
def compare_trees(*trees):
    entries = defaultdict(lambda: [None] * len (trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield(path, *oids)

# displays all the chnaged files
def diff_trees(t_from, t_to):
    output = ''
    # returns all entries with different OID
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += f'changed: {path}\n'
    return output