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

class MoveAndUpdateAction:
    def __init__(self, document_id, old_path, path):
        self.document_id = document_id
        self.old_path = path
        self.path = path

class AddAction:
    def __init__(self, document_id, path):
        self.document_id = document_id
        self.path = path

class RemoveAction:
    def __init__(self, document_id, old_path):
        self.document_id = document_id
        self.old_path = old_path

class UpdateAction:
    def __init__(self, document_id, path):
        self.document_id = document_id
        self.path = path

class NoneAction:
    def __init__(self, document_id):
        self.document_id = document_id

class ActionHistory:
    def remove_action(self, doc_id):
        del self.actions[doc_id]

    def get_action(self, doc_id):
        return self.actions[doc_id]

    def add_action(self, action):
        self.actions[action.document_id] = action

    def format_summary(self):
        additions = 0
        removals = 0
        updates = 0
        move_and_updates = 0
        for action in self.actions.values():
            if isinstance(action, AddAction):
                additions += 1
            elif isinstance(action, RemoveAction):
                removals += 1
            elif isinstance(action, UpdateAction):
                updates += 1
            elif isinstance(action, MoveAndUpdateAction):
                move_and_updates += 1
        
        return (f'{additions} new documents were added\n'
                f'{removals} documents were removed\n'
                f'{updates} documents were updated\n'
                f'{move_and_updates} documents were moved and possibly updated')

    def __init__(self):
        self.actions = {}