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

import bidict
from datetime import datetime
from Formatting import PercentTemplate
import json
import pathlib

class BackupInfoEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BackupInfo):
            return {'last_backup_time': obj.last_backup_time,
                    'documents': obj.documents,
                    'pattern': obj.pattern}
        elif isinstance(obj, bidict.bidict):
            return dict(obj)
        elif isinstance(obj, PercentTemplate):
            return obj.template
        elif isinstance(obj, datetime):
            return obj.isoformat()
        
        return json.JSONEncoder.default(self, obj)

    def __init__(self, indent = None):
        super().__init__(indent = indent)
encoder = BackupInfoEncoder(indent = '  ')

class BackupInfo:
    def contains_documents(self, dir):
        """Whether any documents are in the given directory"""
        return any(pathlib.Path(d).is_relative_to(dir) for d in self.documents.values())

    def used_by_other_document(self, id, path):
        return path in self.documents.inverse and self.documents.inverse[path] != id

    def save(self, filename):
        with open(filename, 'w') as f:
            encoded = encoder.encode(self)
            f.write(encoded)

    def load(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
        obj = BackupInfo(data['pattern'])
        obj.last_backup_time = datetime.fromisoformat(data['last_backup_time'])
        obj.documents = bidict.bidict(data['documents'])

        return obj

    def __init__(self, pattern):
        self.last_backup_time = None
        self.documents = bidict.bidict()
        self.pattern = PercentTemplate(pattern)