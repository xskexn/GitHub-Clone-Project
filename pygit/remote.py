# This section handles the raw HTTP requests to the remote server, including passing usernames and passwords.
import struct
import zlib
import urllib.request
from . import data
from . import base

# Git Packfile Object Type Mapping
OBJECT_TYPES = {
    'commit': 1,
    'tree': 2,
    'blob': 3,
    'tag': 4,
}

# A wrapper around python built-in around urllib that securely transmits data 
def http_request(url, username=None, password=None, data=None):
    # Executes an HTTP request with optional authentication
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    if username and password:
        password_manager.add_password(None, url, username, password)
    auth_handler = urllib.request.HTTPBasicAuthHandler(password_manager)
    opener = urllib.request.build_opener(auth_handler)
    

    req = urllib.request.Request(url, data=data)
    if data:
        req.add_header('Content-Type', 'application/x-git-receive-pack-request')
    
    with opener.open(req) as f:
        return f.read()

def extract_lines(data):
    # Parses incoming pkt-line formatted payload from server response
    lines = []
    i = 0
    while i < len(data):
        # reads first 4 bytes and convers them form hext to int
        line_length = int(data[i:i + 4], 16)
        if line_length == 0:
            lines.append(b'')
            i += 4
        else:
            line = data[i + 4:i + line_length]
            lines.append(line)
            i += line_length
    return lines

def build_lines_data(lines):
    # Encodes outgoing raw byte lines into Git pkt-line hex format
    result = []
    for line in lines:
        length = len(line) + 4
        result.append(f'{length:04x}'.encode() + line)
    # Flush packet, stop signal for the server
    result.append(b'0000')  
    return b''.join(result)

# Syncronisation hustory engine
def get_remote_master_hash(git_url, username=None, password=None):
    # Queries the remote HTTP server to find the current hash of refs/heads/main or master
    url = f"{git_url.rstrip('/')}/info/refs?service=git-receive-pack"
    response = http_request(url, username, password)
    lines = extract_lines(response)
    
    if not lines or lines[0] != b'# service=git-receive-pack\n':
        raise ValueError("Invalid Git HTTP service response")
        
    for line in lines[2:]:
        if not line:
            continue
        parts = line.split(b'\x00')[0].split()
        if len(parts) == 2:
            sha1, ref = parts[0].decode(), parts[1].decode()
            if ref in ('refs/heads/main', 'refs/heads/master'):
                return sha1 if sha1 != '0' * 40 else None
    return None

def _get_all_objects_for_commit(commit_oid):
    # Recursively collects all commit, tree, and blob hashes reachable from a commit
    objects = {commit_oid}
    commit = base.get_commit(commit_oid)
    
    # Collect tree objects recursively
    def _collect_tree(tree_oid):
        objects.add(tree_oid)
        for type_, oid, _ in base._iter_tree_entries(tree_oid):
            if type_ == 'tree':
                _collect_tree(oid)
            else:
                objects.add(oid)

    _collect_tree(commit.tree)
    return objects

def find_missing_objects(local_sha1, remote_sha1):
    # Calculates missing local objects that the remote repository does not have
    local_objects = set()
    for commit_oid in base.iter_commits_and_parents({local_sha1}):
        local_objects.update(_get_all_objects_for_commit(commit_oid))
        
    if not remote_sha1:
        return local_objects
        
    remote_objects = set()
    for commit_oid in base.iter_commits_and_parents({remote_sha1}):
        remote_objects.update(_get_all_objects_for_commit(commit_oid))
    # Calculates the exact list of files to upload with set difference operaion
    return local_objects - remote_objects

# builds binary header for a file using bitwise operations
def encode_pack_object(oid):
    # Try fetching object type and data from pygit data store
    obj_type, raw_data = _read_object_raw(oid)
    type_num = OBJECT_TYPES[obj_type]
    size = len(raw_data)
    
    # variable lenght interger encoder used to package object type and size into a single byte
    byte = (type_num << 4) | (size & 0x0F)
    size >>= 4
    header = bytearray()
    while size:
        header.append(byte | 0x80)
        byte = size & 0x7F
        size >>= 7
    header.append(byte)
    
    return bytes(header) + zlib.compress(raw_data)

def _read_object_raw(oid):
    # Retrieves raw type and payload for encoding
    for possible_type in ['commit', 'tree', 'blob']:
        try:
            content = data.get_object(oid, expected=possible_type)
            return possible_type, content
        except Exception:
            continue
    raise ValueError(f"Unknown or corrupt object {oid}")

# Generates a complete binary Git .pack file payload
def create_pack(objects):
    header = struct.pack('!4sLL', b'PACK', 2, len(objects))
    body = b''.join(encode_pack_object(o) for o in sorted(objects))
    contents = header + body
    sha1 = data.hash_object(contents, write=False)
    return contents + bytes.fromhex(sha1)

# Main push command to upload missing commits and objects over HTTP by packing them into a binary .pack
def push(git_url, username=None, password=None, ref_name='refs/heads/main'):
    local_sha1 = base.get_oid('@')
    remote_sha1 = get_remote_master_hash(git_url, username, password)
    
    missing = find_missing_objects(local_sha1, remote_sha1)
    if not missing:
        print("Everything up-to-date")
        return

    print(f"Packing {len(missing)} objects...")
    ref_line = f"{remote_sha1 or ('0' * 40)} {local_sha1} {ref_name}\x00 report-status".encode()
    payload = build_lines_data([ref_line]) + create_pack(missing)
    
    url = f"{git_url.rstrip('/')}/git-receive-pack"
    print(f"Pushing to {url}...")
    response = http_request(url, username, password, data=payload)
    
    lines = extract_lines(response)
    if lines and b'unpack ok' in lines[0]:
        print(f"Successfully pushed to {git_url} ({ref_name})")
    else:
        print("Push failed or received unexpected server response.")