"""
Github interface which uses Github App's to authenthicate.

Note : This should not be used by users as it should be unecessary.

This is a fallback option for developpers who need to raise their API cap.
"""


import aiohttp
import jwt
import time
from aiohttp.web import Application

class GitHubAppClient:
    def __init__(self, app: Application):
        self.app = app
        self.session = aiohttp.ClientSession()

        # Set GitHub app credentials if provided
        blade_config = self.app.get('blade', {})
        blade_config = blade_config['static_cluster_configuration']
        self.app_id = blade_config.get('github_app_id')
        self.private_key = blade_config.get('github_private_key')

        # Initialize GitHub App authentication tokens storage
        self.jwt_token = None
        self.installation_access_token = None
        self.installation_token_expires = time.time()

    async def close(self):
        await self.session.close()

    async def fetch(self, url: str, method: str = 'GET', **kwargs):
        # If GitHub App credentials are provided and token is expired, refresh it
        if self.app_id and self.private_key and self.installation_id:
            if time.time() >= self.installation_token_expires:
                await self.refresh_github_app_authentication()

            # Add the GitHub App installation access token to headers
            headers = kwargs.get('headers', {})
            headers['Authorization'] = f'token {self.installation_access_token}'
            headers['Accept'] = 'application/vnd.github.v3+json'
            kwargs['headers'] = headers

        # Perform the HTTP request using the aiohttp session
        async with self.session.request(method, url, **kwargs) as response:
            return await response.json()

    async def refresh_github_app_authentication(self):
        if self.app_id and self.private_key and self.installation_id:
            # Generate a new JWT using the private key and APP ID
            jwt_payload = {
                'iat': int(time.time()) - 60,
                'exp': int(time.time()) + (10 * 60),
                'iss': self.app_id
            }
            self.jwt_token = jwt.encode(jwt_payload, self.private_key, algorithm='RS256')

            # Use the JWT to get a new installation access token
            token_url = f'https://api.github.com/app/installations/{self.installation_id}/access_tokens'
            headers = {
                'Authorization': f'Bearer {self.jwt_token}',
                'Accept': 'application/vnd.github.v3+json',
            }
            async with self.session.post(token_url, headers=headers) as response:
                token_response = await response.json()
                self.installation_access_token = token_response.get('token')
                # Set the token expiry time
                self.installation_token_expires = time.time() + 3600

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

