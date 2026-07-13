import argparse, collections, difflib, enum, hashlib, operator, os, stat
import struct, sys, time, urllib.request, zlib

def init(repo):
    os.mkdir(repo)
    os.mkdir(os.path.join(repo, '.git'))
    for name in ['objects', 'refs', 'refs/heads']:
        os.mkdir(os.path.join(repo, '.git', name))
    write_file(os.path.join(repo, '.git', 'HEAD'), b'ref: refs/heads/master')
    print('initialized empty repository: {}'.format(repo))

def hash_object(data, obj_type, write=True):
    header = '{} {}'.format(obj_type, len(data)).encode()
    full_data = header + b'\x00' + data
    sha1 = hashlib.sha1(full_data).hexdigest()
    if write:
        path = os.path.join('.git', 'objects', sha1[:2], sha1[2:])
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            write_file(path, zlib.compress(full_data))
    return sha1

IndexEntry = collections.namedtuple('IndexEntry', [
    'ctime_s', 'ctime_n', 'mtime_s', 'mtime_n', 'dev', 'ino', 'mode',
    'uid', 'gid', 'size', 'sha1', 'flags', 'path',
])

def read_index():
    """Read git index file and return list of IndexEntry objects."""
    try:
        data = read_file(os.path.join('.git', 'index'))
    except FileNotFoundError:
        return []
    digest = hashlib.sha1(data[:-20]).digest()
    assert digest == data[-20:], 'invalid index checksum'
    signature, version, num_entries = struct.unpack('!4sLL', data[:12])
    assert signature == b'DIRC', \
            'invalid index signature {}'.format(signature)
    assert version == 2, 'unknown index version {}'.format(version)
    entry_data = data[12:-20]
    entries = []
    i = 0
    while i + 62 < len(entry_data):
        fields_end = i + 62
        fields = struct.unpack('!LLLLLLLLLL20sH',
                               entry_data[i:fields_end])
        path_end = entry_data.index(b'\x00', fields_end)
        path = entry_data[fields_end:path_end]
        entry = IndexEntry(*(fields + (path.decode(),)))
        entries.append(entry)
        entry_len = ((62 + len(path) + 8) // 8) * 8
        i += entry_len
    assert len(entries) == num_entries
    return entries

def commit(message, author):
    """Commit the current state of the index to master with given message.
    Return hash of commit object.
    """
    tree = write_tree()
    parent = get_local_master_hash()
    timestamp = int(time.mktime(time.localtime()))
    utc_offset = -time.timezone
    author_time = '{} {}{:02}{:02}'.format(
            timestamp,
            '+' if utc_offset > 0 else '-',
            abs(utc_offset) // 3600,
            (abs(utc_offset) // 60) % 60)
    lines = ['tree ' + tree]
    if parent:
        lines.append('parent ' + parent)
    lines.append('author {} {}'.format(author, author_time))
    lines.append('committer {} {}'.format(author, author_time))
    lines.append('')
    lines.append(message)
    lines.append('')
    data = '\n'.join(lines).encode()
    sha1 = hash_object(data, 'commit')
    master_path = os.path.join('.git', 'refs', 'heads', 'master')
    write_file(master_path, (sha1 + '\n').encode())
    print('committed to master: {:7}'.format(sha1))
    return sha1

def extract_lines(data):
    """Extract list of lines from given server data."""
    lines = []
    i = 0
    for _ in range(1000):
        line_length = int(data[i:i + 4], 16)
        line = data[i + 4:i + line_length]
        lines.append(line)
        if line_length == 0:
            i += 4
        else:
            i += line_length
        if i >= len(data):
            break
    return lines

def build_lines_data(lines):
    result = []
    for line in lines:
        result.append('{:04x}'.format(len(line) + 5).encode())
        result.append(line)
        result.append(b'\n')
    result.append(b'0000')
    return b''.join(result)

def http_request(url, username, password, data=None):
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, url, username, password)
    auth_handler = urllib.request.HTTPBasicAuthHandler(password_manager)
    opener = urllib.request.build_opener(auth_handler)
    f = opener.open(url, data=data)
    return f.read()


def get_remote_master_hash(git_url, username, password):
    url = git_url + '/info/refs?service=git-receive-pack'
    response = http_request(url, username, password)
    lines = extract_lines(response)
    assert lines[0] == b'# service=git-receive-pack\n'
    assert lines[1] == b''
    if lines[2][:40] == b'0' * 40:
        return None
    master_sha1, master_ref = lines[2].split(b'\x00')[0].split()
    assert master_ref == b'refs/heads/master'
    assert len(master_sha1) == 40
    return master_sha1.decode()


def find_tree_objects(tree_sha1):
    objects = {tree_sha1}
    for mode, path, sha1 in read_tree(sha1=tree_sha1):
        if stat.S_ISDIR(mode):
            objects.update(find_tree_objects(sha1))
        else:
            objects.add(sha1)
    return objects

def find_commit_objects(commit_sha1):
    objects = {commit_sha1}
    obj_type, commit = read_object(commit_sha1)
    assert obj_type == 'commit'
    lines = commit.decode().splitlines()
    tree = next(l[5:45] for l in lines if l.startswith('tree '))
    objects.update(find_tree_objects(tree))
    parents = (l[7:47] for l in lines if l.startswith('parent '))
    for parent in parents:
        objects.update(find_commit_objects(parent))
    return objects

def find_missing_objects(local_sha1, remote_sha1):
    local_objects = find_commit_objects(local_sha1)
    if remote_sha1 is None:
        return local_objects
    remote_objects = find_commit_objects(remote_sha1)
    return local_objects - remote_objects

def encode_pack_object(obj):
    """Encode a single object for a pack file and return bytes
    (variable-length header followed by compressed data bytes).
    """
    obj_type, data = read_object(obj)
    type_num = ObjectType[obj_type].value
    size = len(data)
    byte = (type_num << 4) | (size & 0x0f)
    size >>= 4
    header = []
    while size:
        header.append(byte | 0x80)
        byte = size & 0x7f
        size >>= 7
    header.append(byte)
    return bytes(header) + zlib.compress(data)

def create_pack(objects):
    """Create pack file containing all objects in given given set of
    SHA-1 hashes, return data bytes of full pack file.
    """
    header = struct.pack('!4sLL', b'PACK', 2, len(objects))
    body = b''.join(encode_pack_object(o) for o in sorted(objects))
    contents = header + body
    sha1 = hashlib.sha1(contents).digest()
    data = contents + sha1
    return data


def push(git_url, username, password):
    """Push master branch to given git repo URL."""
    remote_sha1 = get_remote_master_hash(git_url, username, password)
    local_sha1 = get_local_master_hash()
    missing = find_missing_objects(local_sha1, remote_sha1)
    lines = ['{} {} refs/heads/master\x00 report-status'.format(
            remote_sha1 or ('0' * 40), local_sha1).encode()]
    data = build_lines_data(lines) + create_pack(missing)
    url = git_url + '/git-receive-pack'
    response = http_request(url, username, password, data=data)
    lines = extract_lines(response)
    assert lines[0] == b'unpack ok\n', \
        "expected line 1 b'unpack ok', got: {}".format(lines[0])