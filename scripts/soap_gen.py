from datetime import datetime
import os
import random
import string


soap = """
<SOAP-ENV:Envelope 
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" 
    xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ecp="urn:oasis:names:tc:SAML:2.0:profiles:SSO:ecp">
    <SOAP-ENV:Header>
     </SOAP-ENV:Header>
     <SOAP-ENV:Body> 
        <samlp:AuthnRequest
		ID="%(RANDOM_STRING)s" 
		ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:PAOS"
		AssertionConsumerServiceURL="%(ASSERTION_CONSUMER_SERVICE_URL)s"
		IssueInstant="%(TIMESTAMP)s"
		Version="2.0"
	>
	<saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
		%(REMOTE_ENTITY_ID)s
	</saml:Issuer>
	<samlp:NameIDPolicy AllowCreate="1"/>
	</samlp:AuthnRequest>       
     </SOAP-ENV:Body> 
</SOAP-ENV:Envelope>"""

if __name__ == "__main__":

    import os

    acs = os.environ.get('ASSERTION_CONSUMER_SERVICE_URL',
                         'https://sp-test.cloudwatt.test:5000/Shibboleth.sso/SAML2/ECP')
    entity_id = os.environ.get('REMOTE_ENTITY_ID',
                               'https://sp-test.cloudwatt.test/shibboleth')

    with open('soap.xml', 'w') as output:
        string_id = ''.join(random.sample(string.ascii_letters, 20))
        issue_instant = datetime.utcnow().isoformat()
        output.write(soap % {'RANDOM_STRING': string_id,
                             'ASSERTION_CONSUMER_SERVICE_URL': acs,
                             'TIMESTAMP': issue_instant,
                             'REMOTE_ENTITY_ID': entity_id })

