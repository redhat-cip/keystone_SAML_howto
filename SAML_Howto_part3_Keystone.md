### Part 3: Making it work with Keystone

Now that our federation bricks are in place, let's try it with Keystone. The simplest way to deploy Keystone is through [devstack](http://www.devstack.org), just clone the devstack repository on your SP server, and adapt the `local.conf` file to your needs. Mine looks like this:
```
    [[local|localrc]]
    RECLONE=yes
    ADMIN_PASSWORD=XXX
    MYSQL_PASSWORD=XXX
    RABBIT_PASSWORD=XXX
    SERVICE_PASSWORD=XXX
    ENABLED_SERVICES=key,mysql
    SERVICE_TOKEN=XXXX
    HOST_IP=1.2.3.4
```

From now on we'll assume you have a similar deployment with `admin` and `demo` users and projects, and `admin` and `_member_` roles.

The [official documentation](http://docs.openstack.org/developer/keystone/configure_federation.html) gives all the steps, in a very clear fashion, in order to plug federation into keystone.

If you've followed part 2, there are only two steps you need to adapt:
* Configure your keystone `vhost` (located at `/etc/apache2/sites-enabled/keystone.conf` if you installed keystone with devstack) [as it is explained on the Keystone docs](http://docs.openstack.org/developer/keystone/configure_federation.html#configure-apache-httpd-for-mod-shibboleth). I choose to keep the auth parameters from part 2 in the `<LocationMatch /v3/OS-FEDERATION/identity_providers/.*?/protocols/saml2/auth>` stanza, so that I am prompted for authentication in the browser if no SSO session exists. Make sure to remove the `ShibRequireAll` rule if you're using Apache 2.4+. Since we've been working with SSL so far, we'll have to keep doing so and you have to enable SSL in the `vhost`.
```
 **TODO** Add copy of vhost here
```
* Enable the federation extension in keystone, [as explained on the official docs](http://docs.openstack.org/developer/keystone/extensions/federation.html). At the time of this writing, the external auth method must be disabled for saml2 to work properly, but [a patch is on its way](https://review.openstack.org/#/c/111953/).

Finally, if you've followed part 2, we need to update the SP metadata on the IdP to reflect the new service port (keystone's port 5000). Add the following lines to `/opt/idp-shibboleth/metadata/sp-metadata.xml` on your IdP server:
```XML
        <md:ArtifactResolutionService Binding="urn:oasis:names:tc:SAML:2.0:bindings:SOAP" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/Artifact/SOAP" index="11"/>
    <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:SOAP" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SLO/SOAP"/>     <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SLO/Redirect"/>     <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SLO/POST"/>     <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Artifact" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SLO/Artifact"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML2/POST" index="11"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST-SimpleSign" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML2/POST-SimpleSign" index="12"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Artifact" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML2/Artifact" index="13"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:PAOS" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML2/ECP" index="14"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:1.0:profiles:browser-post" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML/POST" index="15"/>     <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:1.0:profiles:artifact-01" Location="https://sp.cloudwatt.test:5000/Shibboleth.sso/SAML/Artifact" index="16"/>
```

Now let's create some groups, federation mappings and a protocol in keystone. This is all done with the V3, which is well covered by the `keystoneclient` library and the trunk version of the `OpenstackClient` CLI, but not yet available in packaged versions as of this writing. We'll do it the cool way, with cURL calls.

When applicable, replace `XXXX` by the service token you defined in your local.conf file, or the one set in `/etc/keystone/keystone.conf`.

Create a group for the `_member_` role:
```bash
  curl -i -d '{     "group": {         "description": "member group",         "domain_id": "default",         "name": "membergroup"     } }' -X POST http://sp.cloudwatt.test:5000/v3/groups -H "Content-Type: application/json" -H "X-Auth-Token: XXXX"
```

Get the group id from keystone's response, in my case it was `f610b34a922449a590734fc3955518b9`.

Get the `_member_` role id, this time you can simply use `keystone role-list` to get it. In my case: `9fe2ff9ee4384b1894a90878d3e92bab`. Get the `demo` project's id as well with `keystone tenant-list`, I got `6616831a20124ab88a31d9c763b54e17`.

We can now assign the `_member_` role on the `demo` project to our group, following this syntax:
```bash
  curl -i -X PUT http://sp.cloudwatt.test/v3/projects/$projectID/groups/$groupID/roles/$roleID -H "X-Auth-Token: XXXX"::
  curl -i -X PUT http://sp.cloudwatt.test:5000/v3/projects/6616831a20124ab88a31d9c763b54e17/groups/f610b34a922449a590734fc3955518b9/roles/9fe2ff9ee4384b1894a90878d3e92bab -H "X-Auth-Token: XXXX"
```

Let's declare our identity provider in keystone, we will name it `testIdP` (which is also its id, so it has to be unique):
```bash
    curl -si -H"X-Auth-Token:XXXX" -H "Content-type: application/json" -d '{ "identity_provider": { "description": "cloudwatt test IdP", "enabled": true } }' -X PUT http://sp.cloudwatt.test:5000/v3/OS-FEDERATION/identity_providers/testIdP
```

Now we will create a mapping. I want that people belonging to the `user` group in my LDAP directory get access to the `demo` project as themselves, and that people belonging to the `admin` group get to act as the keystone `admin` account. You can find explanations on the mapping rules syntax and examples on the following links:
* [OpenStack's Identity API readme - Federation Mappings](https://github.com/openstack/identity-api/blob/master/v3/src/markdown/identity-api-v3-os-federation-ext.md#mappings-os-federationmappings)
* [OpenStack's Identity API readme - Example Mapping Rules](https://github.com/openstack/identity-api/blob/master/v3/src/markdown/identity-api-v3-os-federation-ext.md#example-mapping-rules)

Basically, each rule contains two parts:
* The `local` part, dealing with the keystone properties like the username or the group id to assign to the authenticating user
* The `remote` part, that sets conditions on the SAML assertions ("type"). If all the conditions are fulfilled, the authenticating user is mapped according to the `local` directives.

The `remote` conditions can be:
* `any_one_of` - true if the assertion equals or matches any of the values listed
* `not_any_of` - false if the assertion equals or matches any of the values listed

Setting `regex` to true will make the mapping engine consider the values as regular expressions.

In the `local` definitions, you can set variable substitutions, like `{0}, {1}, ... {n}`, this means these will be replaced by the corresponding assertions in the `remote` part, with respect to their listing order.

Here is the command to create our mapping:
```bash
  curl -si -H"X-Auth-Token:XXXX" -H "Content-type: application/json" \
      -d '{ "mapping": {         "rules": [             {                 "local":[                     {                         "user": {                             "name": "admin"                         }                     }                 ],                 "remote": [                     {                         "type": "isMemberOf",                         "regex": true,                         "any_one_of":                         ["admin"]                     }                 ]             },                         {                 "local":[                     {                         "user": {                             "name": "{0}"                         }                     },                     {                         "group": {                             "id": "f610b34a922449a590734fc3955518b9"                         }                     }                 ],                 "remote": [                     {                         "type": "uid"                        },                     {                         "type": "isMemberOf",                         "regex": true,                         "any_one_of":                         ["^user",                          ";user"]                     }                 ]             }         ]     } }' \
      -X PUT http://sp.cloudwatt.test:5000/v3/OS-FEDERATION/mappings/testmapping
```

We can finally create our saml2 protocol:
```bash
  curl -si -H"X-Auth-Token:XXXX" -H "Content-type: application/json" -d '{ "protocol": { "mapping_id": "testmapping" } }' -X PUT http://sp.cloudwatt.test:5000/v3/OS-FEDERATION/identity_providers/testIdP/protocols/saml2
```

It has to be called `saml2` if you followed the instructions from the keystone documentation above about `LocationMatch`, otherwise just name it any way you want.

You are now ready to fetch an unscoped token from keystone using SAML, open a browser with developer tools, or at least the capability to display the response headers, and head to `https://sp.cloudwatt.test:5000/v3/OS-FEDERATION/identity_providers/testIdP/protocols/saml2/auth`. You'll be redirected to the IdP login page, and once you authenticate, you'll receive a JSON payload summarizing the saml2 auth. The unscoped token is stored in the `X-Subject-Token` header.

The next logical step is to check what projects and domains you're allowed in; you can do this with the following `cURL` commands:
```bash
  curl -k -X GET -H "X-Auth-Token: your_unscoped_token" https://sp.cloudwatt.test:5000/v3/OS-FEDERATION/projects
  curl -k -X GET -H "X-Auth-Token: your_unscoped_token" https://sp.cloudwatt.test:5000/v3/OS-FEDERATION/domains
```

Knowing these, you can finally request a scoped token and do stuff:
```bash
  curl -k -X POST -H "Content-Type: application/json" -d '{"auth":{"identity":{"methods":["saml2"],"saml2":{"id":"your_unscoped_token"}},"scope":{"project":{"domain": {"name": "Default"},"name":"demo"}}}}' -D - https://sp.cloudwatt.test:5000/v3/auth/tokens
```

And fetch your scoped token, again, from the response header called `X-Subject-Token`.

#### Enabling non-browser authentication with ECP

One of the main problems with SAML is that it's a protocol relies heavily on the use of a browser, making it impossible to use in a command-line client for example. This is were ECP ([Enhanced Client or Proxy"](https://wiki.shibboleth.net/confluence/display/SHIB2/ECP)) comes in handy. Basically, the client "impersonates" the Service Provider and requests directly the Identity Provider. A session is established, that can be validated with the Service Provider.

After all we've done, activating ECP is rather easy. On the Identity Provider:

1. Make sure the ECP profile is enabled in your `DefaultRelyingParty` configuration, in `/opt/shibboleth-idp/conf/relying-party.xml`:

  ```XML
    <rp:ProfileConfiguration xsi:type="saml:SAML2ECPProfile"
                              signAssertions="always"
                              includeAttributeStatement="true"/>
  ```

2. Make sure the ECP handler is enabled, check that `/opt/shibboleth-idp/conf/handler.xml` contains the following:

  ```XML
    <ph:ProfileHandler xsi:type="ph:SAML2ECP"
        inboundBinding="urn:oasis:names:tc:SAML:2.0:bindings:SOAP"
        outboundBindingEnumeration="urn:oasis:names:tc:SAML:2.0:bindings:SOAP">
      <ph:RequestPath>/SAML2/SOAP/ECP</ph:RequestPath>
    </ph:ProfileHandler>
  ```

3. Add the following in `/etc/apache2/sites-enabled/idp.conf` to enable Basic Auth on the ECP URL:

  ```XML
                <Location /idp/profile/SAML2/SOAP/ECP>
                AuthType Basic
AuthName "Test IdP Basic Auth for ECP"
require valid-user
AuthBasicProvider ldap
AuthLDAPURL ldap://localhost/ou=users,dc=cloudwatt,dc=test?uid
AuthLDAPBindDN "cn=binduser,dc=cloudwatt,dc=test"
AuthLDAPBindPassword "bindpassword"
</Location>
  ```

This has, of course, to be adapted to your own setup. My test IdP, as discussed in part 1, uses a LDAP backend for authentication, so I must rely on Apache's LDAP module (which is usually loaded by default, otherwise it can be loaded with the command `a2enmod ldap`).

Restart apache and the IdP is ready to go, [I wrote a script to help you test it](https://gist.github.com/mhuin/e3fcd3be028547453467). This script will generate the SOAP message needed to query the ECP endpoint. Modify it to suit your needs or use the environment variables as demonstrated in the script, you might need to change `utcnow()` for `now()` if your IdP server is not on UTC time. Then, if you run:
```bash
  python soap_gen.py && curl -k -d @soap.xml -H "Content-Type: application/vnd.paos+xml" --basic -u username:password https://idp.cloudwatt.test/idp/profile/SAML2/SOAP/ECP | xmllint --pretty 1 -
```

You should receive a big XML encoded message if all goes well.

On the Service Provider, we need to also activate ECP so that it accepts incoming connections. It is simply a matter of setting `ECP="true"` in SSO stanza in `/etc/shibboleth/shibboleth2.xml`:
```XML
    <SSO entityID="https://idp.cloudwatt.test/idp/shibboleth" isDefault="true" ECP="true">
```

Restart `shibd` on the SP. To be on the safe side, re-download the metadata from your SP (located at `https://sp.cloudwatt.test:5000/Shibboleth.sso/Metadata` - the port is important!) and update your ISP at `/opt/shibboleth-idp/metadata/`.

Restart tomcat7 on the IdP once the metadata has been updated.

You can now authenticate with the latest `keystoneclient` library, [you can see how with this code snippet](https://gist.github.com/mhuin/3a4f6d8feeb85c0d3448).

### What's next ?

Keystone offers already a functional approach to federation. To make it fully usable for the end-user, efforts should be made on integration with Horizon and the command-line utilities.

[Horizon's integration is discussed on this patch](https://review.openstack.org/#/c/96867/) and the CLI modifications are currently [being developed on this other patch](https://review.openstack.org/#/c/108325/).
