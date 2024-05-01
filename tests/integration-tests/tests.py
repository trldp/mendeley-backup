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

import configparser
from datetime import datetime, timedelta
import hashlib
import json
import mendeley
import pathlib
import re
import unittest
import shutil
import subprocess
import sys

sys.path.append(f'{pathlib.Path(__file__).parent.parent.parent}')
import MendeleyLogin

CONFIG_FILE = r'tests/integration-tests/mendeley-backup-tests.conf'
OUTPUT_DIR = r'tests/integration-tests/backup'
TOKEN_FILE = rf'{pathlib.Path(__file__).parent.joinpath("token.json")}'
OUTPUT_PATTERN = r'%authors/%year - %title'
DOCUMENT_TITLE_PREFIX = 'mendeley-backup test document'

def login():
    with open(CONFIG_FILE, 'r') as f:
        config = configparser.ConfigParser()
        with open(CONFIG_FILE, 'r') as f:
            config.read_file(f)
            login_method = config['login-method']
            client_id = login_method.getint('client-id')
            client_secret = login_method.get('client-secret')
            redirect_uri = login_method.get('redirect-uri')
        
    if pathlib.Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, 'r') as f:
            token = json.load(f)
    else:
        token = None
    session = MendeleyLogin.authorization_code_flow(str(client_id), client_secret, redirect_uri, token)
    if not pathlib.Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, 'w') as f:
            json.dump(session.token, f)
    
    return session

def clear_library(session):
    for doc in session.documents.iter():
        if not doc.title.startswith(DOCUMENT_TITLE_PREFIX):
            raise Exception('The test library is not empty')
        doc.delete()

def clear_backup():
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

def hash(filename):
    with open(filename, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.session = login()
        clear_library(self.session)
        clear_backup()

    def tearDown(self):
        clear_library(self.session)
        clear_backup()
    
    def check_document(self, dir, title, type, authors, year, files):
        """Check whether the document in the directory has the correct info.json file and files.
        
        Args:
            dir (pathlib.Path): The directory of the document.
            title (str): The title of the document.
            type (str): The type of the document.
            authors (list): A list of tuples of the form (first_name, last_name) of the authors of the document.
            year (int): The year of the document.
            files (set): A set of filenames of the document
        """
        self.assertTrue(dir.exists(), 'The directory of the document does not exist')
        self.assertTrue(dir.joinpath('info.json').exists(), 'The info.json file of the document does not exist')
        with open(dir.joinpath('info.json'), 'r') as f:
            info = json.load(f)
            document = info['document']
            self.assertEqual(document['title'], title, 'The title of the document is incorrect')
            self.assertEqual(document['type'], type, 'The type of the document is incorrect')
            self.assertEqual(len(document['authors']), len(authors), 'The number of authors of the document is incorrect')
            for i, (real_author, expected_author) in enumerate(zip(document['authors'], authors)):
                self.assertEqual(real_author['first_name'], expected_author[0], 
                                 f'The first name of the {i+1}th author of the document is incorrect')
                self.assertEqual(real_author['last_name'], expected_author[1], 
                                 f'The last name of the {i+1}th author of the document is incorrect')
            self.assertEqual(document['year'], year, 'The year of the document is incorrect')
            
            self.assertEqual(len(info['files']), len(files), 'The number of files of the document is incorrect')
            for filename in info['files'].values():
                self.assertTrue(filename in files, f'The file {filename} is not in the document')
                self.assertEqual(hash(dir.joinpath(filename)), 
                                 hash(pathlib.Path(r'tests/integration-tests/files/', filename)),
                                 f'The file {filename} was not downloaded correctly')

    def check_backup_info(self, expected_documents, expected_last_backup_time_lower):
        output_path = pathlib.Path(OUTPUT_DIR)
        with open(output_path.joinpath('info.json'), 'r') as f:
            info = json.load(f)
            self.assertEqual(info['pattern'], OUTPUT_PATTERN, 'The pattern is incorrect')
            self.assertEqual(len(info['documents']), len(expected_documents), 'The number of documents is incorrect')
            for document_location in info['documents'].values():
                self.assertIn(document_location, expected_documents, 'Unexpected document')
                expected_documents.remove(document_location)
            
            last_backup_time = datetime.fromisoformat(info['last_backup_time'])
            self.assertLess(last_backup_time, datetime.utcnow(), 'The last backup time is incorrect')
            self.assertGreater(last_backup_time, expected_last_backup_time_lower)
    
    def check_stdout(self, stdout, expected_nr_new_documents, expected_nr_removed_documents, expected_nr_updated_documents,
                     expected_nr_moved_documents):
        match = re.search(r'^(?P<new>[0-9]+) new documents were added$', stdout, re.MULTILINE)
        self.assertIsNotNone(match, 'The number of new documents was not printed')
        self.assertEqual(int(match.group('new')), expected_nr_new_documents, 
                         'The number of new documents is incorrect')

        match = re.search(r'^(?P<removed>[0-9]+) documents were removed$', stdout, re.MULTILINE)
        self.assertIsNotNone(match, 'The number of removed documents was not printed')
        self.assertEqual(int(match.group('removed')), expected_nr_removed_documents,
                            'The number of removed documents is incorrect')

        match = re.search(r'^(?P<updated>[0-9]+) documents were updated$', stdout, re.MULTILINE)
        self.assertIsNotNone(match, 'The number of updated documents was not printed')
        self.assertEqual(int(match.group('updated')), expected_nr_updated_documents,
                            'The number of updated documents is incorrect')

        match = re.search(r'^(?P<moved>[0-9]+) documents were moved and possibly updated$', stdout, re.MULTILINE)
        self.assertIsNotNone(match, 'The number of moved documents was not printed')
        self.assertEqual(int(match.group('moved')), expected_nr_moved_documents,
                            'The number of moved documents is incorrect')

    
    def test_initial_backup(self):
        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 1', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document1.pdf')

        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 2', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe'),
                                                mendeley.models.common.Person.create(first_name='Jane', last_name='Doe')],
                                       year=2024)

        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 3', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document3.pdf')
        doc.attach_file(r'tests/integration-tests/files/document32.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 3, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2',
                                f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})
        
    def test_document_added(self):
        #Initial setup
        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 1', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document1.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 1, 0, 0, 0)

        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1'],
                                expected_last_backup_time_lower=expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        
        #Add a new document without any files
        self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 2', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe'),
                                                mendeley.models.common.Person.create(first_name='Jane', last_name='Doe')],
                                       year=2024)
        
        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 1, 0, 0, 0)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2'],
                                expected_last_backup_time_lower=expected_last_backup_time_lower)
        
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        
        #Add a new document with two files
        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 3', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document3.pdf')
        doc.attach_file(r'tests/integration-tests/files/document32.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 1, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2',
                                f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})


    
    def test_document_removal(self):
        #Initial setup
        doc1 = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 1', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc1.attach_file(r'tests/integration-tests/files/document1.pdf')

        doc2 = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 2', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe'),
                                                mendeley.models.common.Person.create(first_name='Jane', last_name='Doe')],
                                       year=2024)
        
        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 2, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2'],
                                expected_last_backup_time_lower=expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        
        #Delete document 1
        doc1.delete()
        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 1, 0, 0)
        self.check_backup_info([f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2'],
                               expected_last_backup_time_lower=expected_last_backup_time_lower)
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        self.assertFalse(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1').exists(),
                            'Document 1 was not removed')

        #Move document 2 to trash
        doc2.move_to_trash()
        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 1, 0, 0)
        self.check_backup_info([],
                               expected_last_backup_time_lower=expected_last_backup_time_lower)
        self.assertFalse(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2').exists(),
                            'Document 2 was not removed')

    def test_document_update(self):
        #Initial setup
        doc1 = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 1', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc1.attach_file(r'tests/integration-tests/files/document1.pdf')

        doc2 = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 2', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe'),
                                                mendeley.models.common.Person.create(first_name='Jane', last_name='Doe')],
                                       year=2024)

        doc3 = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 3', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc3.attach_file(r'tests/integration-tests/files/document3.pdf')
        doc3.attach_file(r'tests/integration-tests/files/document32.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 3, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe & Doe/2024 - {DOCUMENT_TITLE_PREFIX} 2',
                                f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'working_paper', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.check_document(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', [('John', 'Doe'), ('Jane', 'Doe')], 2024, set())
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})
        
        #Update type of document 1 and add an author to document 2
        doc1.update(type = 'generic')
        
        doc2_authors = doc2.authors
        doc2_authors.append(mendeley.models.common.Person.create(first_name='Jannet', last_name='Dow'))
        doc2.update(authors=doc2_authors)

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 0, 1, 1)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 1',
                                f'Doe, Doe & Dow/2024 - {DOCUMENT_TITLE_PREFIX} 2',
                                f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)

        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 1'),
                            f'{DOCUMENT_TITLE_PREFIX} 1', 'generic', [('John', 'Doe')], 2024, {'document1.pdf'})
        self.assertFalse(output_path.joinpath('Doe & Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 2').exists(), 
                         'The document was not moved')
        self.check_document(output_path.joinpath('Doe, Doe & Dow', f'2024 - {DOCUMENT_TITLE_PREFIX} 2'),
                            f'{DOCUMENT_TITLE_PREFIX} 2', 'working_paper', 
                            [('John', 'Doe'), ('Jane', 'Doe'), ('Jannet', 'Dow')], 2024, set())
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})

    def test_file_added(self):
        #Initial setup
        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 3', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document3.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 1, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)
        
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf'})
        
        #Add a file to the document
        doc.attach_file(r'tests/integration-tests/files/document32.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 0, 1, 0)
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})
        
    def test_file_removed(self):
        #Initial setup
        doc = self.session.documents.create(title=f'{DOCUMENT_TITLE_PREFIX} 3', type='working_paper', 
                                       authors=[mendeley.models.common.Person.create(first_name='John', last_name='Doe')],
                                       year=2024)
        doc.attach_file(r'tests/integration-tests/files/document3.pdf')
        doc.attach_file(r'tests/integration-tests/files/document32.pdf')

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 1, 0, 0, 0)
        
        self.assertTrue(pathlib.Path(OUTPUT_DIR).exists(), 'The output directory does not exist')
        output_path = pathlib.Path(OUTPUT_DIR)
        
        self.check_backup_info([f'Doe/2024 - {DOCUMENT_TITLE_PREFIX} 3'],
                                expected_last_backup_time_lower)
        
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document3.pdf', 'document32.pdf'})
        
        #Remove file document3.pdf
        file = next(x for x in doc.files.iter() if x.file_name == 'document3.pdf')
        file.delete()

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 0, 1, 0)
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {'document32.pdf'})
        self.assertFalse(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3', 'document3.pdf').exists(),
                         'The file document3.pdf was not removed')
        
        #Remove file document32.pdf
        file = next(x for x in doc.files.iter() if x.file_name == 'document32.pdf')
        file.delete()

        expected_last_backup_time_lower = datetime.utcnow()
        output = subprocess.check_output(['python3', 'mendeley-backup.py', '--config-file', CONFIG_FILE, 
                                          '--output-dir', OUTPUT_DIR, '--pattern', OUTPUT_PATTERN,
                                          '--token-file', TOKEN_FILE])
        self.check_stdout(output.decode('utf-8'), 0, 0, 1, 0)
        self.check_document(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3'),
                            f'{DOCUMENT_TITLE_PREFIX} 3', 'working_paper', [('John', 'Doe')], 2024, 
                            {})
        self.assertFalse(output_path.joinpath('Doe', f'2024 - {DOCUMENT_TITLE_PREFIX} 3', 'document32.pdf').exists(),
                         'The file document32.pdf was not removed')

if __name__ == '__main__':
    unittest.main()