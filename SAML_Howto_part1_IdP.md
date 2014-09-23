# Introduction to federated authentication with Shibboleth

One of the most exciting features coming up for [Openstack's Identity service - Keystone]( http://keystone.openstack.org) is federated authentication. This work begun during the Icehouse release cycle, which brought an early implementation of federated authentication on the server side, and there is an ongoing effort to meet the Juno release with improved features and support of federated authentication on the client side.

## How does it work ?

First, let's specify some terms:
* A **Service Provider (SP)** is a service (for example a web server, or in our case Keystone) that offers restricted access to its resources, according to who the user is and what she is allowed to do. However, it doesn't necessarily needs to know who the user is, it only needs a proof of her identity.
* An **Identity Provider (IdP)** is a service capable of identifying users and listing properties about them, usually groups they belong to or roles they have.
* **SAML**, [Security Assertion Markup Language](http://en.wikipedia.org/wiki/Security_Assertion_Markup_Language), is used by Service Providers and Identity Providers to communicate among each other, namely to exchange assertions (or attributes) about a user from the IdP to the SP.

Identity Providers and Service Providers usually interact according to the following scenario:

1. Alice, who works for Acme Corp., wants to access a resource protected with federated authentication through her web browser. She is not specifically registered with the resource.
2. The resource, or more precisely Service Provider, gives Alice a list of Identity
providers it is aware of. Acme Corp's IdP is among the list, so Alice chooses this one.
3. Alice's web browser is forwarded to Acme Corp's IdP, where she authenticates herself. It is important to note that this happens completely independently from the original Service Provider, and it is never aware of Alice's credentials.
4. If she authenticates successfully, the IdP forwards Alice's web browser back to the Service Provider, along SAML assertions, and an authenticated session with the IdP. The Service Provider knows the incoming user was authenticated and authorized by the IdP, and gives her access to its resources according to the contents of the SAML assertions.

## How is it implemented in Keystone ?

This describes the current implementation in Icehouse. This is subject to changes in Juno and beyond!

The Keystone Federation API has been added to the Identity v3 API. It defines two things:

* A mapping is a set of rules that map a given set of SAML assertions to specific keystone users or groups (on which a set of roles are granted). For example, a mapping could specify that if the "eppn" (it stands for eduPersonPrincipalName, an LDAP-type attribute) assertion equals admin@acme.com, then the incoming user will be mapped to the keystone user admin; or if the "eduPersonEntitlement" assertion contains "R&D Lab", the user will be mapped to the group "OpenstackDevelopper" and receive a temporary keystone user named after its "eppn" assertion. [*]
* A protocol is the association of an identity provider declared in Keystone, and one or several mapping rules to use when receiving assertions from an identity provider. This makes it possible to create reusable mapping rules that can be common to many identity providers. Once a protocol is defined, the following endpoint is available for federated authentication: `https://keystone:5000/v3/OS-FEDERATION/identity_providers/$identity_provider/protocols/$protocol/auth` where `$identity_provider` and `$protocol` are the IdP and protocol that were defined, respectively.

[*] a temporary user isn't created in keystone's user backend, it appears for auditing and compatibility purposes.

There is also one important requirement to have federation with keystone: keystone must be served through Apache, since the SP heavy lifting is done by an apache module called `apache_shib2`. This is the default deployment option since Icehouse so it won't be a problem with a fresh install; otherwise the keystone documentation explains how to configure Apache to do so.

The previous scenario now looks like this for keystone:

1. Alice from Acme Corp. needs a keystone token to use Acme's private cloud's Compute resources. She hits the endpoint` https://keystone:5000/v3/OS-FEDERATION/identity_providers/ACMECORP/protocols/ACMEPROTOCOL/auth` with her web browser.<br /> ![step1](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_01.png)

2. The `apache_shib2` module ("Shibboleth") protects this URL and is configured to forward Alice's browser to Acme Corp's IdP (this is all done in Apache, at this point, no keystone code has been executed so far). Alice authenticates against the IdP.<br /> ![step2](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_02.png)<br /> ![step3](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_03.png)
3. Upon success, she is sent back to the keystone endpoint, along with SAML assertions about her. Keystone checks these assertions against ACMEPROTOCOL, and if it is a match, Alice receives an unscoped token from keystone, containing the user (real or temporary) she is mapped on, and the keystone groups she belongs to.<br /> ![step4](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_04.png)<br /> ![step5](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_05.png)<br /> ![step6](https://github.com/enovance/keystone_SAML_howto/blob/master/images/SAML_step_06.png)
4. She then authenticates normally with her unscoped token, requesting a token scoped to a given domain and project; if it is alright with the groups and/or the keystone user she was mapped to, she then gets a scoped token that she can use with the Compute API.

## What are the advantages of federation ?

Federation has really big advantages, for the end-users and for the administrators alike:
* User management in one place: there is no need anymore to manage users at the service level. No more provisioning and syncing users among backends !
* Separation of services and AAA (Authentication/Authorization/Accounting): these are usually two separate matters, so it is better to have these isolated.
* Fine-grained information sharing between the IdP and the SP: at configuration time, a "contract" is established between the IdP and the SP to know which assertions have to be sent back to the SP. Sensitive, irrelevant information about a user can therefore be kept secret.
* Single Sign-On: if the user is already authenticated once on the IdP, it will extend to any SP working with this IdP.

SSO is very cool for the end-user, but I think that the first advantage listed is really the "killer feature" when applied to Openstack. Provisioning thousands of users, and afterwards syncing users deletions and authorization changes between both backends is a big problem for large organizations looking to deploy a private cloud or to register on a public cloud offer like Cloudwatt. Federation solves the problem elegantly ... if not easily, but this series of articles will help you with setting up a federation test bed.


## Deploying a federation test bed

**BEFORE YOU START**: each server MUST HAVE a FQDN ! The IdP and the SP rely on this heavily. It is possible to use bogus FQDNs like sp.cloudwatt.test as long as you declare them in your `/etc/hosts and /etc/hostname` files, so that each server knows where to find the other. In this series we will use sp.cloudwatt.test and idp.cloudwatt.test as the FQDNs of the SP and the IdP respectively.

You will also need OpenSSL on each server to generate certificates.

The test bed will be deployed on Ubuntu 14.04 servers.

### Part 1: Setting up an Identity Provider

It is possible to skip this part: you can set up a Service Provider and use it with the test IdP at [TestShib.org](http://www.testshib.org) if you only want to test the federation workflow on keystone. It greatly simplifies things as it helps you configure your SP, but it won't work with a bogus FQDN though.

We will follow closely the instructions found here: https://www.switch.ch/aai/docs/shibboleth/SWITCH/latest/idp/deployment/

First, a few pre-requisites:
* For the sake of the article, we will suppose that our IdP's FQDN is idp.cloudwatt.test. Change it with your own FQDN.
* apache should be installed on your server, and port 443 (https) reachable from the outside world. Additionnally, the modules mod_ssl and mod_proxy_ajp (both present in the default ubuntu package for apache) need to be enabled.
* java should be installed on your server : apt-get install default-jre-headless
* openssl should be installed on your server.
* ntp should be installed on your server.
* unzip should be installed on your server.

The IdP will use a LDAP backend, such as OpenLDAP, to store users. Creating such a backend is out of the scope of this series, but lots of resources can be found online; the directory we will use here looks a lot like [the one described in this tutorial](https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-a-basic-ldap-server-on-an-ubuntu-12-04-vps).<br /> ![The test directory. Come on down to South Park ...](https://github.com/enovance/keystone_SAML_howto/blob/master/images/LDAP.png)

The Shibboleth IdP service is served through tomcat, so let's install it:
```Bash
  apt-get install tomcat7
```

Set the JAVA_OPTS variables in `/etc/default/tomcat7`:
```Bash
  JAVA_OPTS="-Djava.awt.headless=true -Xmx512M -XX:MaxPermSize=128M -Dcom.sun.security.enableCRLDP=true"
```

Disable autodeploying when looking for updates in `/etc/tomcat7/server.xml`:
```Apache
<Host name="localhost" appBase="webapps"
        unpackWARs="true" autoDeploy="false"
        xmlValidation="false" xmlNamespaceAware="false">
```

In the same file, uncomment the Connector stanza for port 8009 and adapt it:
```Apache
<Connector port="8009" protocol="AJP/1.3" redirectPort="8443"
           address="127.0.0.1" enableLookups="false" tomcatAuthentication="false" />
```

Get the latest Shibboleth version from the Shibboleth website. We'll use 2.4.0:
```Bash
  cd /usr/local/src
  curl -O http://shibboleth.net/downloads/identity-provider/2.4.0/shibboleth-identityprovider-2.4.0-bin.zip
  unzip shibboleth-identityprovider-2.4.0-bin.zip
  cd shibboleth-identityprovider-2.4.0
  chmod u+x install.sh
```

Endorse XML/Xerces libraries from the Shibboleth IdP package in `$CATALINA_HOME/endorsed `:
```Bash
  cd /usr/local/src/shibboleth-identityprovider-2.4.0
  mkdir /usr/share/tomcat7/endorsed/
  cp ./endorsed/*.jar /usr/share/tomcat7/endorsed/
```

Run Shibboleth's ant installer (keep the default target location setting, ie `/opt/shibboleth-idp/`):
```Bash
  cd /usr/local/src/shibboleth-identityprovider-2.4.0/
  env IdPCertLifetime=3 JAVA_HOME=/usr/lib/jvm/default-java ./install.sh
```

Create certificates with the right FQDN by following the instructions on [Shibboleth's wiki for Regenerating Key/Certificate Pairs](https://wiki.shibboleth.net/confluence/display/SHIB2/IdPCertRenew).

When you do so, you need to manually edit the IdP's metadata at `/opt/shibboleth-idp/metadata/idp-metadata.xml` to reflect the change in the certificate. Update the contents of `idp.cert` where appropriate in the metadata file.

Create the tomcat context descriptor file as `/etc/tomcat7/Catalina/localhost/idp.xml`:
```XML
    <Context docBase="/opt/shibboleth-idp/war/idp.war"
    privileged="true"
    antiResourceLocking="false"
    antiJARLocking="false"
    unpackWAR="false"
    swallowOutput="true"
    cookies="false" />
```

We will now tell the IdP how to check usernames and passwords at login. On `/opt/shibboleth-idp/login.conf`, uncomment the LDAP part like so, with adjustments to your own specific LDAP schema:
```
   edu.vt.middleware.ldap.jaas.LdapLoginModule required
   ldapUrl="ldap://LDAPSERVER"
   baseDn="ou=users,dc=cloudwatt,dc=test"
   ssl="false"
   bindDn="cn=bind,dc=cloudwatt,dc=test"
   bindCredential="bind"
   userFilter="uid={0}";
```

It is time to configure Apache now.

Generate some certificates for SSL. If you can work with self-signed ones (it is just a test after all), you can generate them this way:
```Bash
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout idp.key -out idp.crt
```

Put them in `/etc/ssl/private/` and `/etc/ssl/certs/` respectively.

Create an idp.conf file in /etc/apache2/sites-available/ that will look like this:
```Apache
    ServerName idp-test.cloudwatt.test
    <IfModule mod_ssl.c>
    <VirtualHost _default_:443>
        ServerName idp-test.cloudwatt.test
        ServerAdmin webmaster@localhost
        DocumentRoot /var/www
        ErrorLog ${APACHE_LOG_DIR}/error.log
        CustomLog ${APACHE_LOG_DIR}/access.log combined
        SSLEngine on
        SSLCertificateFile        /etc/ssl/certs/idp.crt
        SSLCertificateKeyFile /etc/ssl/private/idp.key
        <FilesMatch "\.(cgi|shtml|phtml|php)$">
            SSLOptions +StdEnvVars
        </FilesMatch>
        <Directory /usr/lib/cgi-bin>
            SSLOptions +StdEnvVars
        </Directory>
        BrowserMatch "MSIE [2-6]" \
            nokeepalive ssl-unclean-shutdown \
            downgrade-1.0 force-response-1.0
        # MSIE 7 and newer should be able to use keepalive
        BrowserMatch "MSIE [17-9]" ssl-unclean-shutdown

        <Proxy ajp://localhost:8009>
            Allow from all
        </Proxy>
        ProxyPass /idp ajp://localhost:8009/idp retry=5
    </VirtualHost>
    <VirtualHost _default_:8443>
        ServerName idp-test.cloudwatt.test:8443
        ServerAdmin admin@localhost
        DocumentRoot /var/www
        SSLEngine On
        SSLCipherSuite HIGH:MEDIUM:!aNULL:!MD5
        SSLProtocol all -SSLv2
        SSLCertificateFile /opt/shibboleth-idp/credentials/idp.crt
        SSLCertificateKeyFile /opt/shibboleth-idp/credentials/idp.key
        <Proxy ajp://localhost:8009>
            Allow from all
        </Proxy>
        ProxyPass /idp ajp://localhost:8009/idp retry=5
        BrowserMatch "MSIE [2-6]" \
           nokeepalive ssl-unclean-shutdown \
        downgrade-1.0 force-response-1.0
        # MSIE 7 and newer should be able to use keepalive
        BrowserMatch "MSIE [17-9]" ssl-unclean-shutdown
    </VirtualHost>
</IfModule>
```

Enable the virtualhost and the modules:
```Bash
  a2ensite idp
  a2enmod ssl
  a2enmod proxy_ajp
```

Make sure apache can listen on the adequate ports in `/etc/apache2/ports.conf`:
```Apache
    Listen 443
    Listen 8443
```

Restart apache:
```Bash
  service apache2 restart
```

Back to the IdP configuration ...

The IdP credentials must be set to the right permissions:
```Bash
  cd /opt/shibboleth-idp/credentials
  chown root idp.key
  chgrp tomcat7 idp.{key,crt}
  chmod 440 idp.key
  chmod 644 idp.crt
```

Edit `/opt/shibboleth-idp/conf/relying-party.xml`, locate and update the following stanzas:
```XML
        <rp:AnonymousRelyingParty provider="https://idp-test.cloudwatt.test/idp/shibboleth" defaultSigningCredentialRef="IdPCredential"/>
        <rp:DefaultRelyingParty provider="https://idp-test.cloudwatt.test/idp/shibboleth" defaultSigningCredentialRef="IdPCredential" defaultAuthenticationMethod="urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport">
```
Edit `/opt/shibboleth-idp/conf/attribute-resolver.xml`, uncomment any attribute you'd like to use, such as `sourceAttributeID="cn"`, and uncomment the LDAP data connector:
```XML
    <resolver:DataConnector id="myLDAP" xsi:type="dc:LDAPDirectory"
                            ldapURL="ldap://LDAP_SERVER"
                            baseDN="ou=users,dc=cloudwatt,dc=test"
                            principal="cn=bind,dc=cloudwatt,dc=test"
                            principalCredential="bind">
        <dc:FilterTemplate>
<![CDATA[
  (uid=$requestContext.principalName)
]]>
        </dc:FilterTemplate>
    </resolver:DataConnector>
```

Add the following filtering policy to `/opt/shibboleth-idp/conf/attribute-filter.xml` to define the uid attribute:
```XML
<afp:AttributeFilterPolicy id="releaseUIDToAnyone">
    <afp:PolicyRequirementRule xsi:type="basic:ANY"/>
    <afp:AttributeRule attributeID="uid">
        <afp:PermitValueRule xsi:type="basic:ANY"/>
    </afp:AttributeRule>
</afp:AttributeFilterPolicy>
```

I am using a schema in OpenLDAP where the groups information is stored in a branch separate from users. Namely, my users are under the DN `ou=users,dc=cloudwatt,dc=test`, while my groups are posixGroups under the branch `ou=groups,dc=cloudwatt,dc=test` and group members' uids are stored in the attribute memberUid. To have memberships sent to SPs, I'll add a data connector and an attribute definition in `/opt/shibboleth-idp/attribute-resolver.xml`:
```XML
    <resolver:AttributeDefinition id="isMemberOf" xsi:type="Simple" xmlns="urn:mace:shibboleth:2.0:resolver:ad" sourceAttributeID="cn">
        <resolver:Dependency ref="myLDAPGroups" />
        <resolver:AttributeEncoder xsi:type="enc:SAML1String"
                                   name="urn:mace:dir:attribute-def:isMemberOf" />
        <resolver:AttributeEncoder xsi:type="SAML2String" xmlns="urn:mace:shibboleth:2.0:attribute:encoder" name="urn:oid:1.3.6.1.4.1.5923.1.5.1.1" friendlyName="isMemberOf" />
    </resolver:AttributeDefinition>
```

Add this in the Data Connector section of the file. This is very close to the existing LDAP connector, except for the base DN (the groups DN) and the LDAP filter that takes groups only if the requested uid is in its "memberUid" attribute:
```XML
        <resolver:DataConnector id="myLDAPGroups" xsi:type="dc:LDAPDirectory"
                                ldapURL="ldap://localhost"
                                baseDN="ou=groups,dc=cloudwatt,dc=test"
                                principal="cn=bind,dc=cloudwatt,dc=test"
                                principalCredential="bind"
                                maxResultSize="500"
                                mergeResults="true">
            <dc:FilterTemplate>
            <![CDATA[
 (&(objectclass=posixGroup)(memberUid=$requestContext.principalName))
               ]]>
            </dc:FilterTemplate>
            <dc:ReturnAttributes>
            cn
            </dc:ReturnAttributes>
        </resolver:DataConnector>
```

To have this new attribute released to SPs, add the following attribute policy in `/opt/shibboleth-sp/conf/attribute-filter.xml`:
```XML
<afp:AttributeFilterPolicy id="releaseIsMemberOfToAnyone">
    <afp:PolicyRequirementRule xsi:type="basic:ANY"/>
    <afp:AttributeRule attributeID="isMemberOf">
        <afp:PermitValueRule xsi:type="basic:ANY"/>
    </afp:AttributeRule>
</afp:AttributeFilterPolicy>
```

Enable the UserPassword authentication (this will use LDAP as specified earlier) in `/opt/shibboleth-idp/conf/handler.xml` by uncommenting and updating this stanza if necessary:
```XML
<ph:LoginHandler xsi:type="ph:UsernamePassword"
                 jaasConfigurationLocation="file:///opt/shibboleth-idp/conf/login.config">
    <ph:AuthenticationMethod>
        urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport
    </ph:AuthenticationMethod>
</ph:LoginHandler>
```

Finally (!!) configure the /Status page to be available for you, this is done in `/usr/local/src/shibboleth-identityprovider-2.4.0/src/main/webapp/WEB-INF/web.xml`:
```XML
    <servlet>
    <servlet-name>Status</servlet-name>
    <servlet-class>edu.internet2.middleware.shibboleth.idp.StatusServlet</servlet-class>

    <!-- Space separated list of CIDR blocks allowed to access the status page -->
    <init-param>
        <param-name>AllowedIPs</param-name>
        <param-value>127.0.0.1/32 ::1/128 130.59.0.0/16 2001:620::/48 #your IP range#</param-value>
     </init-param>

     <load-on-startup>2</load-on-startup>
</servlet>
```

Redeploy the web application (keep the values from the first time you ran this) and restart the services:
```Bash
  cd /usr/local/src/shibboleth-identityprovider-2.4.0/
  env JAVA_HOME=/usr/lib/jvm/default-java ./install.sh

  service apache2 restart
  service tomcat7 restart
```

Be aware that tomcat7 takes a LOT of time to start up. Check the Tomcat log in `/var/log/tomcat7/catalina.out` for errors and to make sure the service has finally started.

That's it ! (Theoretically) Congratulations !

#### Troubleshooting
The following resources can be useful for troubleshooting and more information about Shibboleth IdPs:

* ["Shibboleth Test Bed - Part 2: Installing the IdP" on CCSI](https://www.acceleratecarboncapture.org/drupal/blog/patton/public/shibboleth-test-bed-part-2-installing-idp)
* ["LogFiles - Shibboleth 1.x" on Shibboleth.net](https://wiki.shibboleth.net/confluence/display/SHIB/LogFiles) - activate logging
* ["IdPConfiguration - Shibboleth 2.x" on Shibboleth.net](https://wiki.shibboleth.net/confluence/display/SHIB2/IdPConfiguration)

I strongly advise to set logging as verbose as possible in order to troubleshoot problems. This is how I found out I was using incorrect certificates, and that my LDAP credentials were incorrect.
