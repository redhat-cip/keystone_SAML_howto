Part 2: Setting up a Service Provider 
.....................................  

First, a few pre-requisites:
* For the sake of the article, we will suppose that our SP's FQDN is sp.cloudwatt.test. Change it with your own FQDN.  
* apache should be installed on your server, and port 443 (https) reachable from the outside world.

Install the needed Apache modules::    
    apt-get install libapache2-mod-shib2 shibboleth-sp2-schemas  

The configuration files will be in /etc/shibboleth/ and the ones we'll change are shibboleth2.xml and attribute-map.xml.  

Edit the following elements in /etc/shibboleth/shibboleth2.xml::    
    <ApplicationDefaults entityID="https://sp.cloudwatt.test/shibboleth"                        
                         REMOTE_USER="eppn persistent-id targeted-id">  

The entityID is a unique ID used to identify the SP. It usually derives from the FQDN. The REMOTE_USER field indicates which assertion to map to the REMOTE_USER environment variable in Apache; leave it as it is.  

Regenerate a certificate for the SP with shib-keygen::    
    shib-keygen -e https://sp.cloudwatt.test/shibboleth -h sp.cloudwatt.test -y 10  

This command will generate a certificate valid for 10 years, as /etc/shibboleth/sp-cert.pem and /etc/shibboleth/sp-key.pem. These keys should already be configured in /etc/shibboleth/shibboleth2.xml::    
    <CredentialResolver type="File" key="/etc/shibboleth/sp-key.pem" certificate="/etc/shibboleth/sp-cert.pem"/>

At this point, we can generate the SP Metadata file that needs to be given to the IdP. There is a CLI utility for this::
    shib-metagen -h sp.cloudwatt.test  > /etc/shibboleth/sp-test-metadata.xml

shib-metagen can take a few more options to set the organization, the administrative contacts, etc ... that can be required by an IdP prior to integrating the metadata. You can refer to shib-metagen's man page for more details.

If you have set an IdP by following Part 1, here is how to add your SP metadata in your IdP:

Copy your SP metadata file on the IdP, at /opt/shibboleth-idp/metadata/sp-metadata.xml .

Edit /opt/shibboleth-idp/conf/relying-party.xml and add a MetadataProvider::
            <metadata:MetadataProvider xsi:type="metadata:FilesystemMetadataProvider"
                                   id="SPTestMetadata"                                    
                                   metadataFile="/opt/shibboleth-idp/metadata/sp-metadata.xml" /> 
 

If you are using testshib.org, the people maintaining this are nice enough to give you ready-made config files. Just fetch them
and skip to the apache configuration steps below. If you are using your own IdP, the SP configuration needs to be tweaked some more.

Back on /etc/shibboleth/shibboleth2.xml on the SP, locate the SSO stanza (we're not going to use discovery services)::    
    <SSO entityID="https://idp.cloudwatt.test/idp/shibboleth">
                 SAML2 SAML1  
    </SSO>

Add the IdP metadata info near the MetadataProvider stanzas::
    <MetadataProvider type="XML" uri="https://idp.cloudwatt.test/idp/profile/Metadata/SAML"               
                      backingFilePath="/tmp/federation-metadata.xml" 
                      reloadInterval="7200">
    </MetadataProvider>


In /etc/shibboleth/attribute-map.xml, we map attributes we will use to more usable names. Uncomment the ones about the "cn" LDAP attribute::
    <Attribute name="urn:mace:dir:attribute-def:cn" id="cn"/>
    <Attribute name="urn:oid:2.5.4.3" id="cn"/>

And add the "uid" attribute::
    <Attribute name="urn:oid:0.9.2342.19200300.100.1.1" id="uid"/>

If you have followed Part 1 and are exposing group membership, add this attribute as well::
    <Attribute name="urn:oid:1.3.6.1.4.1.5923.1.5.1.1" id="memberOf"/>

We're done with the SP configuration, now let's move to apache ...

First, make sure the right modules are loaded::
    a2enmod ssl
    a2enmod shib2

Make sure Apache listens on port 443. Your /etc/apache2/ports.conf should look like this::
Listen 80
<IfModule ssl_module>         
Listen 443 
</IfModule>  
<IfModule mod_gnutls.c>
Listen 443
</IfModule> 

Edit your /etc/apache2/sites-available/default-ssl.conf file to look like this (this is very minimalist !)::
<IfModule mod_ssl.c>         
<VirtualHost _default_:443>                 
ServerAdmin webmaster@localhost                  
DocumentRoot /var/www/html                  
ErrorLog ${APACHE_LOG_DIR}/error.log                 
CustomLog ${APACHE_LOG_DIR}/access.log combined                  
SSLEngine on                  
SSLCertificateFile        /etc/ssl/certs/sp-test.pem                 
SSLCertificateKeyFile /etc/ssl/private/sp-test.key                   
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

<Location /Shibboleth.sso>                         
Satisfy Any                 
</Location>                  
<Location /somelocation>                           
AuthType shibboleth                           
ShibRequireSession On                           
ShibExportAssertion On                           
require shibboleth                 
</Location>            
</VirtualHost> 
</IfModule>

The most notable changes are the following:
    
    * SSLCertificateFile and SSLCertificateKeyFile: the default "snakeoil" certificate needs to be changed, as it is generated with a FQDN set to "localhost". It can be done with the following command: openssl req -x509 -newkey rsa:2048 -keyout sp-test.key -out sp-test.pem -days 3650
    * <Location /Shibboleth.sso> stanza: this makes SP specific URLs available to anyone (with respect to ACLs set in /etc/shibboleth/shibboleth2.xml). Notable URLs are https://sp.cloudwatt.test/Shibboleth.sso/Session (gives you some information about any session you opened on an IdP) and https://sp.cloudwatt.test/Shibboleth.sso/Status (a simple "ok" if the SP is correctly configured). If the latter is unreachable, it might be due to restrictive ACLs in shibboleth2.xml; look for the "Handler" stanza where "Location" is set to /Session and change it accordingly.
    * <Location /somelocation> stanza: this is a URI that will be protected by the SP. ShibRequireSession is set to "On" (and "require shibboleth") so that the user will be redirected to the IdP login page if no previous session exists. ShibExportAssertion set to On is recommended for greater compatibility with non-shibboleth IdPs.
    
At this point everything should be ready. Restart apache and shibboleth::
    sudo service apache2 restart
    sudo service shibd restart

Take your browser to https://sp.cloudwatt.test/somelocation and you should be redirected to your IdP login page. Log in, and you'll be redirected to the contents at somelocation (possibly nothing, but at least it is secure). Congratulations !

If you need more details about configuring your SP or troubleshooting problems, the following resources can be helpful:
    
    * https://www.edugate.ie/Support/Technical%20Resources/Installation%20Guides/Service%20Provider%20Guides/shibboleth-2-service-provi-0
    * the shibboleth wiki: https://wiki.shibboleth.net/confluence/display/SHIB2/NativeSPLinuxInstall
    * activate logging: https://wiki.shibboleth.net/confluence/display/SHIB/LogFiles
    * a list of commonly encountered issues and how to solve them: https://shibboleth.usc.edu/docs/idp/errors/

Reading the IdP logs can also be very eye-opening about what's going wrong.

If you'd like to try it without all the hassle, we have some test servers up on our Compute node. Just add the following to your /etc/hosts file::
    84.39.34.27 idp-test.cloudwatt.test
    84.39.34.25 sp-test.cloudwatt.test

And take your browser to https://sp-test.cloudwatt.test/somelocation !



