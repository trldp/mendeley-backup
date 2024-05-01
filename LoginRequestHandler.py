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

from http.server import BaseHTTPRequestHandler
import urllib

# Define request handler for local web server
class LoginRequestHandler(BaseHTTPRequestHandler):
    extra_body = ''

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        if url_parsed.query is not None:
            query = urllib.parse.parse_qs(url_parsed.query)
            if 'error' in query:
                self.send_response(500)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                message = f'{query["error"][0]}: {query["error_description"][0]}'
                self.wfile.write(b'<html><body><h1>Failed to log in!</h1>'
                                 b'<p>' + message.encode() + b'</p></body></html>')
                return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html>'
                         b'  <body>'
                         b'    <h1>Successfully logged in!</h1>'
                         b'    <p>You can close this tab</p>' + 
                         self.extra_body.encode() +
                         b'  </body>'
                         b'</html>')

class LoginRequestHandlerImplicit(LoginRequestHandler):
    extra_body = '''<script>
        if (window.location.hash != '') {
            const xhttp = new XMLHttpRequest();
            xhttp.open("GET", "oauth?" + window.location.hash.slice(1));
            xhttp.send();
        }
    </script>'''

    def do_GET(self):
        super().do_GET()
        url_parsed = urllib.parse.urlparse(self.path)
        self.server.query_string = None
        if url_parsed.query is not None and url_parsed.query != '':
            self.server.query_string = url_parsed.query


class LoginRequestHandlerAuthorizationCode(LoginRequestHandler):
    def do_GET(self):
        super().do_GET()
        self.server.auth_response_path = self.path