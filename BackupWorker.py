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

import arrow
import ActionHistory
from BackupInfo import BackupInfo
from datetime import datetime
from DocumentInfo import DocumentInfo
import Formatting
import hashlib
import os
import pathlib
import requests
import shutil

def calculate_checksum(filename):
    """Calculates a checksum of a given file"""
    hash = hashlib.sha1()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    
    return hash.hexdigest()

class BackupWorker:
    def _get_document_path(self, backup_info, document):
        authors_last_names = Formatting.format_authors([a.last_name for a in document.authors] if document.authors else [])
        output_path = backup_info.pattern.substitute({'authors': Formatting.replace_invalid_characters(authors_last_names),
                                                    'year': document.year,
                                                    'title': Formatting.replace_invalid_characters(document.title)})
        #TODO: add other fields to the pattern
        return output_path
    
    def _get_document_info_path(self, document_path):
        return document_path.joinpath('info.json')

    def _download_file(self, file, file_path):
        try:
            with requests.get(file.download_url, stream=True) as response:
                with open(file_path, 'wb') as downloaded_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded_file.write(chunk)
            return True
        except Exception as e:
            print(f'WARNING: failed to download file {file.file_name} at {file_path}: {e}')
            file_path.unlink()
            return False

    def _file_needs_update(self, file, file_path):
        return file.filehash != calculate_checksum(file_path)
            

    def _handle_document(self, document, document_path):
        document_path_full = self.backup_location.joinpath(document_path)
        document_path_full.mkdir(parents = True, exist_ok = True)
        document_info_path = self._get_document_info_path(document_path_full)
        if document_info_path.exists():
            try:
                document_files = DocumentInfo.load_files(document_info_path)
                document_info = DocumentInfo(document, document_files)
            except:
                print(f'WARNING: could not parse {document_info_path.name} in {document_path_full}. '
                      'Handling as new document...')
                document_info = DocumentInfo(document)
        else:
            document_info = DocumentInfo(document)

        file_ids_remote = set()
        temporary_stored_files = {}
        for file in document.files.iter():
            file_ids_remote.add(file.id)
            file_path_full = document_path_full.joinpath(file.file_name)
            if file_path_full.is_relative_to('.temp'):
                print(f'ERROR: file {file.file_name} of document at {document_path_full} would be stored relative to '
                      'the temporary directory .temp. This is not allowed. The file will be ignored')
                continue
            if document_info.used_by_other_file(file.id, file.file_name):
                temporary_stored_files[file.id] = file.file_name
                file_path_full = document_path_full.joinpath(f'.temp/{file.id}')

            if file.id in document_info.files:
                previous_file_name = document_info.files[file.id]
                if file.file_name != previous_file_name:
                    previous_file_path_full = document_path_full.joinpath(previous_file_name)
                    if previous_file_path_full.exists():
                        os.rename(previous_file_path_full, file_path_full)
                        document_info.files[file.id] = file.file_name
                        if self._file_needs_update(file, file_path_full):
                            self._download_file(file, file_path_full)
                    else:
                        print(f'WARNING: file {file.file_name} of document at {document_path_full} used to be at '
                            f'{previous_file_name}, but does not exist anymore. Redownloading the file...')
                        self._download_file(file, file_path_full)
                else:
                    if file_path_full.exists():
                        if self._file_needs_update(file, file_path_full):
                            self._download_file(file, file_path_full)
                    else:
                        print(f'WARNING: file {file.file_name} of document at {document_path_full} does not exist anymore. '
                               'Redownloading the file...')
                        self._download_file(file, file_path_full)
            else:
                self._download_file(file, file_path_full)
                document_info.files[file.id] = file.file_name
        
        removed_file_ids = set(document_info.files.keys()) - file_ids_remote
        for file_id in removed_file_ids:
            file_name = document_info.files.pop(file_id)
            file_path_full = document_path_full.joinpath(file_name)
            if file_path_full.exists():
                file_path_full.unlink()
            else:
                print(f'WARNING: file {file_name} of document at {document_path_full} used to exist, but does not exist anymore. '
                       'Skipping removal...')
        
        for file_id, file_name in temporary_stored_files.items():
            if document_info.used_by_other_file(file.id, file_name):
                print(f'WARNING: file {file.file_name} of document at {document_path_full} is already used by a file '
                       'with another id. Does the document contain duplicate files? Skipping...')
                del document_info.files[file_id]
                continue

            file_path_full = document_path_full.joinpath(file_name)
            os.rename(f'.temp/{file_id}', file_path_full)
            document_info.files[file_id] = file_name

        temp_dir = document_path_full.joinpath('.temp')
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        #TODO: maybe I should add support for two files with the same name (but different ids) in the same document (then probably use a checksum to check that it isn't a duplicate)
        document_info.save(self._get_document_info_path(document_path_full))

    def _remove_recursive_if_empty(self, dir):
        """Remove dir and all of its parents up to self.backup_location if they are empty."""
        assert(dir.is_relative_to(self.backup_location))
        while dir != self.backup_location and not any(dir.iterdir()):
                dir.rmdir()
                dir = dir.parent

    def _move_document_dir(self, previous_dir, new_dir, remove_previous_dir_parent_if_empty=True):
        previous_full_dir = self.backup_location.joinpath(previous_dir)
        new_full_dir = self.backup_location.joinpath(new_dir)
        if not previous_full_dir.exists():
            print(f'WARNING: document {new_dir} used to be at {previous_dir}, but that directory does not exist anymore. '
                   'Handling as new document...')
            new_full_dir.mkdir(parents=True, exist_ok=True)
            return

        new_full_dir.parent.mkdir(parents=True, exist_ok=True)
        os.rename(previous_full_dir, new_full_dir)
        if remove_previous_dir_parent_if_empty:
            self._remove_recursive_if_empty(previous_full_dir.parent)

    def _remove_document_dir(self, dir):
        full_dir = self.backup_location.joinpath(dir)
        if not full_dir.exists():
            print(f'WARNING: a removed document used to be at {dir}, but that directory does not exist anymore. '
                   'Skipping removal...')
            return

        shutil.rmtree(full_dir)
        self._remove_recursive_if_empty(full_dir.parent)

    def _remove_unaccounted_files_in_document_dir(self, dir):
        document_info_path = self._get_document_info_path(dir)
        if not document_info_path.exists():
            print(f'WARNING: directory {dir} does not contain a document info file. Removing...')
            shutil.rmtree(dir)
            return
        
        document_files = DocumentInfo.load_files(document_info_path)
        for file in dir.iterdir():
            if file.name == 'info.json':
                continue
            if file.name not in document_files.inverse:
                print(f'WARNING: file {file} does not correspond to any mendeley file. Removing...')
                if file.is_dir():
                    shutil.rmtree(file)
                else:
                    file.unlink()
    
    def _remove_unaccounted_files_in_non_document_dir(self, backup_info, dir, ignore_info_file):
        for file in dir.iterdir():
            if ignore_info_file and file.name == 'info.json':
                continue
            elif not file.is_dir():
                print(f'WARNING: file {file} is not in any document directory. Removing...')
                file.unlink()
                continue

            file_relative = file.relative_to(self.backup_location)
            if str(file_relative) in backup_info.documents.inverse:
                self._remove_unaccounted_files_in_document_dir(file)
            elif backup_info.contains_documents(file_relative):
                self._remove_unaccounted_files_in_non_document_dir(backup_info, file, False)
            else:
                print(f'WARNING: directory {file} does not contain any known mendeley documents. Removing...')
                shutil.rmtree(file)

    def _remove_unaccounted_files(self, backup_info: BackupInfo):
        """Check whether there are any files in the backup location that should not be there according to the 
        backup info."""
        self._remove_unaccounted_files_in_non_document_dir(backup_info, self.backup_location, True)
    
    def execute(self):
        self.backup_location.mkdir(parents=True, exist_ok=True)

        backup_info_path = self.backup_location.joinpath('info.json')
        if backup_info_path.exists():
            backup_info = BackupInfo.load(backup_info_path)
            print(f'Last backup time: {backup_info.last_backup_time}')
            if self.pattern_option_provided:
                print('WARNING: provided pattern option will be ignored in favor of previously used pattern')
            #TODO: also allow full checksum backups and allow to set a time to configure how often such a backup should be done
        else:
            backup_info = BackupInfo(self.pattern)
        
        self._remove_unaccounted_files(backup_info)

        new_backup_time = datetime.utcnow()
        history = ActionHistory.ActionHistory()
        new_document_ids = set()
        modified_document_ids = set()
        unmodified_document_ids = set()
        for doc in self.mendeley_session.documents.iter():
            if doc.id in backup_info.documents:
                if doc.last_modified >= arrow.get(backup_info.last_backup_time):
                    modified_document_ids.add(doc.id)
                else:
                    unmodified_document_ids.add(doc.id)
                    history.add_action(ActionHistory.NoneAction(doc.id))
            else:
                new_document_ids.add(doc.id)
        removed_document_ids = set(backup_info.documents.keys()) - (modified_document_ids | unmodified_document_ids)

        for doc_id in removed_document_ids:
            old_document_path = backup_info.documents.pop(doc_id)
            self._remove_document_dir(old_document_path)
            history.add_action(ActionHistory.RemoveAction(doc_id, old_document_path))
        
        temporary_stored_documents = {}
        for doc_id in modified_document_ids:
            doc = self.mendeley_session.documents.get(doc_id, view='all')
            old_document_path = backup_info.documents[doc.id]
            document_path = self._get_document_path(backup_info, doc)
            
            if old_document_path != document_path:
                if pathlib.Path(document_path).is_relative_to('.temp'):
                    print(f'ERROR: document {document_path} would be stored relative to the temporary directory .temp. This '
                           'is not allowed. Specify another pattern. The document will be skipped.')
                    self._remove_document_dir(old_document_path)
                    history.add_action(ActionHistory.RemoveAction(doc_id, old_document_path))
                    del backup_info.documents[doc_id]
                    continue

                if backup_info.used_by_other_document(doc.id, document_path):
                    temporary_stored_documents[doc_id] = document_path
                    document_path = f'.temp/{doc_id}'
                
                self._move_document_dir(old_document_path, document_path)
                history.add_action(ActionHistory.MoveAndUpdateAction(doc.id, old_document_path, document_path))
            else:
                history.add_action(ActionHistory.UpdateAction(doc.id, document_path))
            
            self._handle_document(doc, document_path)
            backup_info.documents[doc.id] = document_path
        
        for doc_id in new_document_ids:
            doc = self.mendeley_session.documents.get(doc_id, view='all')
            document_path = self._get_document_path(backup_info, doc)
            if pathlib.Path(document_path).is_relative_to('.temp'):
                print(f'ERROR: document {document_path} would be stored relative to the temporary directory .temp. This '
                        'is not allowed. Specify another pattern. The document will be skipped.')
                continue

            if backup_info.used_by_other_document(doc.id, document_path):
                temporary_stored_documents[doc_id] = document_path
                document_path = f'.temp/{doc_id}'
            history.add_action(ActionHistory.AddAction(doc.id, document_path))
            self._handle_document(doc, document_path)
            backup_info.documents[doc.id] = document_path

        for doc_id, document_path in temporary_stored_documents.items():
            if backup_info.used_by_other_document(doc.id, document_path):
                print(f'WARNING: document {document_path} is already used by a mendeley document with another id. '
                       'Duplicate document in your library? Skipping...')
                history.remove_action(doc_id)
                del backup_info.documents[doc_id]
                continue

            self._move_document_dir(f'.temp/{doc_id}', document_path, remove_previous_dir_parent_if_empty=False)
            history.get_action(doc_id).path = document_path
            backup_info.documents[doc.id] = document_path
        
        temp_dir = self.backup_location.joinpath('.temp')
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        #TODO: maybe provide an option to not remove unknown files, but give a warning instead
        #TODO: when doing a 'full' backup, also check the files in backup-info that aren't in the library anymore
        #TODO: also support for folders
        #TODO: also download trashed files?
        backup_info.last_backup_time = new_backup_time
        backup_info.save(backup_info_path)
        #TODO: test updating, adding and removing documents (see notes on remarkable for possible tests)
        #TODO: write unit tests for all these scenarios (with some kind of fake mendeley session)

        return history
        #TODO: do I need to separately backup the groups? (or maybe allow a command line arguemnt to also include the groups or something)

    def __init__(self, mendeley_session, backup_location, pattern, pattern_option_provided=False):
        """Initialize a new BackupWorker.

        :param mendeley_session: the mendeley session to use for the backup
        :param backup_location: the location to store the backup
        :param pattern: the pattern to use for the backup
        :param pattern_option_provided: whether the pattern was provided as a command line option
        """
        self.mendeley_session = mendeley_session
        self.backup_location = backup_location
        self.pattern = pattern
        self.pattern_option_provided = pattern_option_provided