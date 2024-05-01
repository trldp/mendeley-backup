# Backup your Mendeley library

This program allows you to backup your Mendeley library locally. It will download all your documents including all metadata and files in each document (like pdf or other files). It can update your local backup when changes occurred remotely since the last run. Local changes will not be uploaded to the Mendeley library though.

No history will be saved in the local backup. If you want to keep a history of your library, use this program together with a regular (versioned) backup program for local files (i.e. first download all files using `mendeley-backup` and then make a back-up of the resulting directory using the other program), or turn the backup directory into a git repository.

## How to run

This program depends on the `mendeley` python package. If it is not included in any of your distributions
packages, it is recommended to install it in a virtual environment. One can do this as follows.

First, create a new virtual environment in the same directory as this script

```bash
python -m venv --system-site-packages venv
```

The `--system-site-packages` option is optional. It allows you to use the packages that are installed system-wide
inside this environment. Without this option, the virtual environment will not have access to any of those
packages, and you will have to install all dependencies manually. Then, activate the environment

```bash
source venv/bin/activate
```

and install `mendeley` using

```bash 
pip install mendeley
```

Now, run the program with (after all other dependencies are also installed either inside the environment or system-wide)

```bash
./mendeley-backup.py
```

Note that you might get an error here because of incompatibility of the `requests` package with your python version. The steps in [incompatible request version](#incompatible-requests-version) might solve the problem.

Finally, to deactivate the virtual environment, run

```bash
deactivate
```

### Configuring the program

Several configuration options are available for `mendeley-backup`. You can either specify them as command-line arguments, or create a configuration file. By default, the configuration file is located at `[USER_CONFIGURATION_DIR]/mendeley-backup/mendeley-backup.conf`, which on linux resolves to `~/.config/mendeley-backup/mendeley-backup.conf`. Command-line argument will always take precedence over the configuration file.

The configuration file has the following format, compatible with python's `configparser` module
```ini
[login-method]
client-id=[CLIENT_ID]
client-secret=[CLIENT_SECRET]
redirect-url=[REDIRECT_URL]
token-file=[TOKEN_FILE]

[backup]
output-dir=[OUTPUT_DIR]
pattern=[PATTERN]
```
Every option is optional and can be left out.

#### Backup options

The section `[backup]` in the configuration file allows you to set several options related to the backup itself, like the backup location and the directory structure. The option `pattern` specifies
how your documents are structured in your local backup. Currently, the following placeholders are supported

- `%author`: the authors of the document. Only the last name is included, separated by commas and \&. If more than three authors are provided, only the first author is used, followed by 'et al.',
- `%title`: the documents title,
- `%year`: the documents year.

The characters `[\/:*?"<>|]` in the placeholders will be escaped, but can be used outside of the placeholders.

#### Login method

The section `[login-method]` allows you to configure the method that is used to login to mendeley. The default method will work out-of-the-box, but will open a browser window for you to login every time.

Alternatively, you can use the method with a `client-secret`, which requires you to have an application registered with Mendeley. In order to do that, you need to make an account on [Mendeley's developers portal](https://dev.mendeley.com/), and under *My Apps* register a new application. You can then provide the resulting ID, secret and redirect URL as the 
`client-id`, `client-secret` and `redirect-url` options. Note that for redirect URL, you can best take one on localhost,
as this will allow `mendeley-backup` to detect when a login was successful.

When using the login method with a `client-secret`, a token file will be created locally containing the token that can be used to login and hence does not require you to re-login every time the program is run. Make sure to store this token file on a secure location.

### Incompatible requests version

Since the mendeley packages still mentions an old version of `requests` in its dependencies which is incompatible with
recent python versions, you might get an error when executing the program. On python 3.10 the error looks as follows

```
Traceback (most recent call last):
  File "/home/trldp/Projects/mendeley-backup/./mendeley-backup.py", line 5, in <module>
    import BackupWorker
  File "/home/trldp/Projects/mendeley-backup/BackupWorker.py", line 5, in <module>
    from DocumentInfo import DocumentInfo
  File "/home/trldp/Projects/mendeley-backup/DocumentInfo.py", line 4, in <module>
    import mendeley
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/mendeley/__init__.py", line 7, in <module>
    from mendeley.auth import MendeleyClientCredentialsAuthenticator, \
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/mendeley/auth.py", line 4, in <module>
    from requests.auth import HTTPBasicAuth
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/__init__.py", line 58, in <module>
    from . import utils
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/utils.py", line 26, in <module>
    from .compat import parse_http_list as _parse_list_header
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/compat.py", line 7, in <module>
    from .packages import chardet
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/packages/__init__.py", line 3, in <module>
    from . import urllib3
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/packages/urllib3/__init__.py", line 10, in <module>
    from .connectionpool import (
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/packages/urllib3/connectionpool.py", line 38, in <module>
    from .response import HTTPResponse
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/packages/urllib3/response.py", line 5, in <module>
    from ._collections import HTTPHeaderDict
  File "/home/trldp/Projects/mendeley-backup/venvtest/lib/python3.10/site-packages/requests/packages/urllib3/_collections.py", line 1, in <module>
    from collections import Mapping, MutableMapping
ImportError: cannot import name 'Mapping' from 'collections' (/usr/lib/python3.10/collections/__init__.py)
```

To solve this error, try upgrading `requests` using

```bash
pip install -U requests
```

or remove the packages to use your system-wide version (requires that your environment was created with `--system-site-packages`)

```bash
pip uninstall requests
```

### Dependencies

The program uses the following python packages

- appdirs (tested with 1.4.4)
- bidict (tested with 0.23.1)
- mendeley (tested with 0.3.2)
- requests (tested with 2.31.0)

## Running the tests

Some integration tests can be found under `tests/integration-tests`. They can be run with a simple

```bash
python tests.py
```

command. However, you will need to set up a configuration file `mendeley-backup-tests.py` file in that directory with the following

```Ini
[login-method]
client-id=[YOUR_CLIENT_ID]
client-secret=[YOUR_CLIENT_SECRET]
redirect-uri=http://localhost:5000/oauth
```

See [login method](#login-method) on how to obtain such a client id and client secret. Running the tests will create a token file at `token.json` in the same directory. Note that the tests will **wipe your entire account**, so only use it on a special-purpose account!

## License

All code in this repository is licensed under GPL-3+, see [here](https://www.gnu.org/licenses/gpl-3.0.html) for more information.