import json
import requests

from keystoneclient import session as kc_session
from keystoneclient.contrib.auth.v3 import saml2


def initialize():
    auth_url = 'https://sp-test.cloudwatt.test:5000/v3'
    identity_provider = 'testIdP'
    identity_provider_url = 'https://idp-test.cloudwatt.test/idp/profile/SAML2/SOAP/ECP'
    username = 'kenny'
    password = 'kenny'

    my_session = kc_session.Session(session=requests.session(), verify=False)
    print(my_session)
    unscoped_plugin = saml2.Saml2UnscopedToken(auth_url, identity_provider,
                                               identity_provider_url,
                                               username, password)
    print(unscoped_plugin)

    unscoped_token = unscoped_plugin.get_auth_ref(my_session)
    print(json.dumps(unscoped_token, indent=4, separators=(',', ': ')))


if __name__ == '__main__':
    initialize()
