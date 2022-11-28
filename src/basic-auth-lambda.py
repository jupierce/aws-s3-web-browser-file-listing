# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import boto3
import base64
import hmac
from typing import Dict, List, Optional
from urllib.parse import quote, unquote_plus

# A dict of usernames and passwords which can be populated from AWS Secrets Manager.
# Unauthenticated users can only access content under 'pub/' in the S3 bucket. If a user
# attempts to access elsewhere, they must provide basic auth credentials.
# Place key/value pairs in ${S3Bucket}-basic-auth/accounts in Secrets Manager.
PRIVATE_USER_ACCOUNTS = None

# Redirect to this S3 bucket if the request comes from an EC2 IP
S3_BUCKET_NAME = "${S3Bucket}"
S3_REGION_NAME = '${AWS::Region}'


def unauthorized():
    return {
        'status': 401,
        'statusDescription': 'Unauthorized',
        'headers': {
            'www-authenticate': [{
                'key': 'WWW-Authenticate',
                'value': 'Basic'
            }],
        }
    }


def redirect(uri: str, code: int = 302, description="Found"):
    return {
        'status': code,
        'statusDescription': description,
        'headers': {
            "location": [{
                'key': 'Location',
                "value": str(uri)
            }],
        }
    }


def get_secrets_manager_secret_dict(secret_name):
    import json
    # We need to read in the secret from AWS SecretManager
    secrets_client = boto3.client(
        service_name='secretsmanager',
        region_name='${AWS::Region}'
    )
    try:
        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_name
        )
    except:
        raise
    else:
        # Assume it is a key/value pair secret and parse as json
        username_password_keypairs_str = get_secret_value_response['SecretString']
        return json.loads(username_password_keypairs_str)


def lambda_handler(event: Dict, context: Dict):
    global PRIVATE_USER_ACCOUNTS

    request: Dict = event['Records'][0]['cf']['request']
    uri: str = request['uri']
    headers: Dict[str, List[Dict[str, str]]] = request['headers']
    request_ip = request['clientIp']

    # Prefixes that should be swapped on access. This provides rudimentary symlink-like
    # behavior on S3 when populated.
    links = {
    }

    for prefix, link in links.items():
        if uri.startswith(prefix):
            uri = link + uri[len(prefix):]
            break

    if not uri.startswith('/pub') and uri != '/favicon.ico':
        # Anything not in /pub requires basic auth header
        authorization = headers.get("authorization", [])
        if not authorization:
            if uri == '/':
                # The one exception is if the user hits / without auth, we try to be friendly and redirect them..
                return redirect("/pub/")
            return unauthorized()
        auth_split = authorization[0]["value"].split(maxsplit=1)  # Basic <base64> => ['Basic', '<base64>']
        if len(auth_split) != 2:
            return unauthorized()
        auth_schema, b64_auth_val = auth_split
        if auth_schema.lower() != "basic":
            return unauthorized()
        auth_val: str = base64.b64decode(b64_auth_val).decode()
        auth_val_split = auth_val.split(':', maxsplit=1)
        if len(auth_val_split) != 2:
            return unauthorized()
        username, password = auth_val_split

        authorized = False

        if not PRIVATE_USER_ACCOUNTS:
            PRIVATE_USER_ACCOUNTS = get_secrets_manager_secret_dict(
                '${S3Bucket}-basic-auth/accounts')

        if username in PRIVATE_USER_ACCOUNTS:
            # like `==`, but in a timing-safe way
            if hmac.compare_digest(password, PRIVATE_USER_ACCOUNTS[username]):
                authorized = True

        if not authorized:
            return unauthorized()

    # Check whether the URI is missing a file name.
    if uri.endswith("/"):
        uri += 'index.html'

    # Some clients may send in URL with literal '+' and other chars that need to be escaped
    # in order for the URL to resolve via an S3 HTTP request. decoding and then
    # re-encoding should ensure that clients that do or don't encode will always
    # head toward the S3 origin encoded.
    request['URI'] = quote(unquote_plus(uri))
    return request

