The content-Addressable Storage system
Git will hash the content of the file to generate a unique key and save the content under the same key.

### `hash_object(data, type_='blob')` — Saving Data

```python
def hash_object (data, type_='blob'):
    obj = type_.encode () + b'\x00' + data
    oid = hashlib.sha1 (obj).hexdigest ()
    with open (f'{GIT_DIR}/objects/{oid}', 'wb') as out:
        out.write (obj)
    return oid
```

Takes the raw file data and compresses it into the `.pygit/objects` folder
- Git header prefix (`b'\x00'`): Before hashing git prepends a header to the raw data separated by a null byte.
- `hashlib.sha1(obj).hexdigest()` is the cryptographic function that generates the 40-character hex fingerprint
- The function saves the generated address in the `.pygit/objects/` folder using the hash as file name

### `get_object(oid, expected='blob')` — Reading Data


```python
def get_object (oid, expected='blob'):
    with open (f'{GIT_DIR}/objects/{oid}', 'rb') as f:
        obj = f.read ()

    type_, _, content = obj.partition (b'\x00')
    type_ = type_.decode ()

    if expected is not None:
        assert type_ == expected, f'Expected {expected}, got {type_}'
    return content
```

Exact reverse of `has_object`, it takes the object id and fetches the code content.
- `obj.partition(b'\x00')` searches for the null byte and splits the file into three parts: header + null byte + file contents
- Type guard (`assert`): verifies the expected object matches. 