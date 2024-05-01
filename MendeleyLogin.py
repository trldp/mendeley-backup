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

from http.server import HTTPServer
import json
from LoginRequestHandler import LoginRequestHandlerImplicit, LoginRequestHandlerAuthorizationCode
import mendeley
from requests_oauthlib import OAuth2Session
import urllib
import webbrowser

#TODO: try to make it not print the requests to terminal
#TODO: maybe switch to https://github.com/ipums/mendeley-python-sdk

class AuthorizationCodeTokenRefresher(mendeley.auth.MendeleyAuthorizationCodeTokenRefresher):
    def refresh(self, *args, **kwargs):
        super().refresh(*args, **kwargs)
        if self.token_file is not None:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump(self.session.token, f)

    def __init__(self, token_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_file = token_file

def implicit_flow(client_id, redirect_uri):
    """Login to mendeley using the implicit grant type and return a mendeley session object."""
    redirect_uri_parsed = urllib.parse.urlparse(redirect_uri, scheme='http')
    if not redirect_uri_parsed.scheme == 'http':
        raise ValueError('Redirect URI must be http')

    m = mendeley.Mendeley(client_id, redirect_uri=redirect_uri)
    auth = m.start_implicit_grant_flow()
    login_uri = auth.get_login_url()
    webbrowser.open(login_uri)
    print('A browser window will open to login to Mendeley. When you are done, the programm will continue.')
    
    server = HTTPServer((redirect_uri_parsed.hostname, redirect_uri_parsed.port or 80), LoginRequestHandlerImplicit)
    while True:
        server.handle_request()
        if server.query_string is not None:
            break
    auth_response = f'{redirect_uri}#{server.query_string}'

    return auth.authenticate(auth_response)

def authorization_code_flow(client_id, client_secret, redirect_uri, saved_token=None,
                            token_file=None):
    """Login to mendeley using the authorization code grant type and return a mendeley session object.
    
    If saved_token is None, the user will be asked to login. If saved_token is not None, the refresh token will be 
    used to login."""
    redirect_uri_parsed = urllib.parse.urlparse(redirect_uri, scheme='http')
    if not redirect_uri_parsed.scheme == 'http':
        raise ValueError('Redirect URI must be http')
    
    m = mendeley.Mendeley(client_id, client_secret, redirect_uri=redirect_uri)
    auth = m.start_authorization_code_flow()
    if saved_token is not None:
        auth.oauth.saved_token = saved_token
    else:
        login_uri = auth.get_login_url()
        webbrowser.open(login_uri)
        print('A browser window will open to login to Mendeley. When you are done, the programm will continue.')
        
        server = HTTPServer((redirect_uri_parsed.hostname, redirect_uri_parsed.port or 80),
                            LoginRequestHandlerAuthorizationCode)
        server.handle_request()
        auth_response = urllib.parse.urlunparse(redirect_uri_parsed._replace(path=server.auth_response_path))
        
        saved_token = auth.oauth.fetch_token(auth.token_url, 
                                             authorization_response=auth_response,
                                             auth=auth.auth,
                                             scope=['all'])
    
    return mendeley.session.MendeleySession(m,
                                            saved_token,
                                            client=auth.client,
                                            refresher=AuthorizationCodeTokenRefresher(token_file, auth))