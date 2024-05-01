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

import re
from string import Template

def format_authors(authors):
    if len(authors) == 0 or authors is None:
        return 'Unknown'
    if len(authors) == 1:
        return authors[0]
    if len(authors) <= 3:
        return ', '.join(authors[:-1]) + ' & ' + authors[-1]
    else:
        return f'{authors[0]} et al.'

escape_regexp = re.compile(r'[\/:*?"<>|]')
def replace_invalid_characters(path):
    return escape_regexp.sub('_', path)

def escape_percent_signs(s):
    return s.replace('%', '%%')

#Version 0.1
class PercentTemplate(Template):
    """A string template with %-based substitution instead of $-based substitution."""
    delimiter = '%'
    
    def __init__(self, template):
        Template.__init__(self, template)
        self._identifiers = None