```python
from setuptools import setup

setup (name = 'pygit',
       version = '1.0',
       packages = ['pygit'],
       entry_points = {
           'console_scripts' : [
               'pygit = pygit.cli:main'
           ]
       })
```

`setup.py` is a configuration file that uses python standard packaging tool `setuptools` to run pygit immediately from the terminal and avoid typing `python pygit/cli.py`.

Installation command: `pip install -e .`
