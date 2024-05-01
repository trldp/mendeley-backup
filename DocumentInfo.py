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
import bidict
import json
import mendeley
import pathlib

class DocumentEncoder(json.JSONEncoder):
    def default(self, obj):
        #TODO: no support for groups or annotations yet
        #TODO: also add collection (i.e. folder) support
        if isinstance(obj, arrow.Arrow):
            return obj.isoformat()
        elif isinstance(obj, mendeley.models.common.Person):
            return {'first_name': obj.first_name, 'last_name': obj.last_name}
        elif isinstance(obj, DocumentInfo):
            return {'document': obj.document,
                    'files': obj.files}
        elif isinstance(obj, mendeley.models.documents.UserDocument):
            converted = {'authors': obj.authors,
                         'id': obj.id,
                         'title': obj.title,
                         'type': obj.type,
                         'source': obj.source,
                         'year': obj.year,
                         'identifiers': obj.identifiers,
                         'keywords': obj.keywords,
                         'abstract': obj.abstract,
                         'authors': obj.authors,
                         'created': obj.created,
                         'last_modified': obj.last_modified}
            if isinstance(obj, mendeley.models.documents.UserBibView):
                converted.update({'pages': obj.pages,
                                  'volume': obj.volume,
                                  'issue': obj.issue,
                                  'websites': obj.websites,
                                  'month': obj.month,
                                  'publisher': obj.publisher,
                                  'day': obj.day,
                                  'city': obj.city,
                                  'edition': obj.edition,
                                  'institution': obj.institution,
                                  'series': obj.series,
                                  'chapter': obj.chapter,
                                  'revision': obj.revision,
                                  'accessed': obj.accessed,
                                  'editors': obj.editors})
            if isinstance(obj, mendeley.models.documents.UserClientView):
                converted.update({'file_attached': obj.file_attached,
                                  'read': obj.read,
                                  'starred': obj.starred,
                                  'authored': obj.authored,
                                  'confirmed': obj.confirmed,
                                  'hidden': obj.hidden})
            if isinstance(obj, mendeley.models.documents.UserTagsView):
                converted.update({'tags': obj.tags})
            
            return converted
        elif isinstance(obj, bidict.bidict):
            return dict(obj)

        return json.JSONEncoder.default(self, obj)
encoder = DocumentEncoder(indent = '  ')

class DocumentInfo:
    def used_by_other_file(self, id, filename):
        """Whether the given file is used by another file in the same document."""
        return filename in self.files.inverse and self.files.inverse[filename] != id

    def save(self, filename: pathlib.Path):
        with open(filename, 'w') as f:
            encoded = encoder.encode(self)
            f.write(encoded)
    
    def load_files(filename) -> bidict.bidict:
        """Load the files from a document info file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        return bidict.bidict(data['files'])

    def __init__(self, document: mendeley.models.documents.UserDocument, files: dict = {}):
        self.document = document
        self.files = bidict.bidict(files)