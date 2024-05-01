#!/usr/bin/env python3

#
# Copyright (C) 2024 Tobe Deprez
# 
# This is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
 
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>. 

import argparse
import appdirs
import BackupWorker
import configparser
import Formatting
import json
import MendeleyLogin
import pathlib
import sys

PROGRAM_NAME = 'mendeley-backup'
DEFAULT_CLIENT_ID = 15049
DEFAULT_REDIRECTION_URI = 'http://localhost:5000/oauth'
DEFAULT_CONFIG_FILE = f'{appdirs.user_config_dir(PROGRAM_NAME)}/mendeley-backup.conf'
DEFAULT_TOKEN_FILE = f'token'
DEFAULT_BACKUP_LOCATION = 'backup'
DEFAULT_PATTERN = '%authors/%year - %title'

#TODO: implement a dry-run option
parser = argparse.ArgumentParser(description='Create a local backup of your Mendeley library.',
                                 usage='%(prog)s [options]')
parser.add_argument('-c', '--config-file', dest='config_file', metavar='FILE',
                    help=(f'Path to the configuration file (default: {DEFAULT_CONFIG_FILE}). If none is provided, and '
                          'the default file does not exist, then the default configuration is used.'))
group = parser.add_argument_group(title='Backup options', description='Configure the backup location and directory structure.')
group.add_argument('-o', '--output-dir', dest='output_dir', metavar='DIR',
                    help=('The directory of the local backup. If none is provided, then the directory from the '
                          f'configuration file is used, if any, or \'{DEFAULT_BACKUP_LOCATION}\'.'))
group.add_argument('-p', '--pattern', dest='pattern', metavar='PATTERN',
                    help=('The pattern to use for the directory structure of the backup. If none is provided, then '
                          f'default pattern \'{Formatting.escape_percent_signs(DEFAULT_PATTERN)}\' is used. '
                          'See documentation for a full list '
                          'placeholders that can be used in the pattern. If the backup location '
                          'already contains a backup, then this option is ignored in favor of the pattern that was '
                          'originally used in the backup.'))

group = parser.add_argument_group(title='Login options',
                                   description='Configure the login method. By default, a browser '
                                  'will open to login every time you run the program. Alternatively, you can register '
                                  'your own application on the Mendeley Developer Portal and provide the client ID, '
                                  'client secret and redirection URL here. In that case, a token file will also be '
                                  'created.')
group.add_argument('-i', '--client-id', dest='client_id', metavar='ID', type=int,
                   help=f'The client ID of the application as registered on the Mendeley Developer Portal.')
group.add_argument('-s', '--client-secret', dest='client_secret', metavar='SECRET',
                   help=f'The client secret of the application as registered on the Mendeley Developer Portal.')
group.add_argument('-r', '--redirect-uri', dest='redirect_uri', metavar='URI',
                   help=f'The redirection URI of the application as registered on the Mendeley Developer Portal. '
                   'Defaults to \'{DEFAULT_REDIRECTION_URI}\'.')
group.add_argument('-t', '--token-file', dest='token_file', metavar='FILE',
                    help=(f'The file where the OAuth token is stored if case a client secret is provided. '
                          f'The value is interpreted as a path relative to '
                          f'\'{appdirs.user_cache_dir(PROGRAM_NAME)}\', unless an absolute path is provided. '
                          f'If this option is not provided, '
                          f'then the file specified in the configuration file is used, if any, or '
                          f'\'{appdirs.user_cache_dir(PROGRAM_NAME)}/{DEFAULT_TOKEN_FILE}\'. Always store this file '
                          f'in a secure location!'))

args = parser.parse_args()

config_file = pathlib.Path(args.config_file or pathlib.Path(DEFAULT_CONFIG_FILE))
client_id = DEFAULT_CLIENT_ID
client_secret = None
redirect_uri = DEFAULT_REDIRECTION_URI
backup_location = DEFAULT_BACKUP_LOCATION
pattern = DEFAULT_PATTERN
token_file = DEFAULT_TOKEN_FILE
if config_file.exists():
    config = configparser.ConfigParser()
    try:
        with open(config_file, 'r') as f:
            config.read_file(f)
            if 'login-method' in config:
                login_method = config['login-method']
                client_id = login_method.getint('client-id', client_id)
                client_secret = login_method.get('client-secret', None)
                redirect_uri = login_method.get('redirect-uri', redirect_uri)
                token_file = login_method.get('token-file', token_file)
            if 'backup' in config:
                backup = config['backup']
                backup_location = backup.get('output-dir', backup_location)
                pattern = backup.get('pattern', pattern)
    except (configparser.Error, KeyError) as e:
        print(f'Failed to parse configuration file: {e}', file=sys.stderr)
        sys.exit(1)
if args.output_dir is not None:
    backup_location = args.output_dir
if args.pattern is not None:
    pattern = args.pattern
if args.token_file is not None:
    token_file = args.token_file
if args.client_id is not None:
    client_id = args.client_id
if args.client_secret is not None:
    client_secret = args.client_secret
if args.redirect_uri is not None:
    redirect_uri = args.redirect_uri
backup_location = pathlib.Path(backup_location)
token_file = pathlib.Path(appdirs.user_cache_dir(PROGRAM_NAME)).joinpath(token_file)

if backup_location is None:
    print('No backup location specified. Provide either a backup location in the configuration file or with '
          'the \'--output-dir\' option.', file=sys.stderr)
    sys.exit(1)

#TODO: at some point try to save the token using libsecret instead
if client_secret is None:
    session = MendeleyLogin.implicit_flow(client_id, redirect_uri)
else:
    if token_file.exists():
        with open(token_file, 'r') as f:
            token = json.load(f)
    else:
        token = None
    session = MendeleyLogin.authorization_code_flow(str(client_id), client_secret, redirect_uri, token)
    if not token_file.exists():
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, 'w') as f:
            json.dump(session.token, f)

worker = BackupWorker.BackupWorker(mendeley_session=session, backup_location=backup_location, 
                                   pattern=pattern)
history = worker.execute()
print(history.format_summary())
#TODO: when stopped in the middle, I should be able to continue where I left off (think about how to do it though)
#TODO: probably find a way to deal with two documents having the same name as according to the pattern