'''
Tomcat Management Functions
'''
import os
import shutil
import grp
import pwd
import yaml
import requests
import errno
import getpass
from time import sleep
import OpenSSL
from lxml import etree
import esg_functions
import esg_bash2py
import esg_logging_manager
import esg_cert_manager
from clint.textui import progress


logger = esg_logging_manager.create_rotating_log(__name__)

with open(os.path.join(os.path.dirname(__file__), 'esg_config.yaml'), 'r') as config_file:
    config = yaml.load(config_file)

TOMCAT_VERSION = "8.5.20"
CATALINA_HOME = "/usr/local/tomcat"

def check_tomcat_version():
    esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/version.sh")

def download_tomcat():
    if os.path.isdir("/usr/local/tomcat"):
        print "Tomcat directory found."
        check_tomcat_version()
        continue_tomcat = raw_input("Do you want to contine the Tomcat installation [y/N]: ") or "no"
        if continue_tomcat.lower() in ["no", "n"]:
            return False

    tomcat_download_url = "http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.20/bin/apache-tomcat-8.5.20.tar.gz"
    print "downloading Tomcat"
    r = requests.get(tomcat_download_url)
    tomcat_download_path =  "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(TOMCAT_VERSION=TOMCAT_VERSION)
    with open(tomcat_download_path, 'wb') as f:
        total_length = int(r.headers.get('content-length'))
        for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1):
            if chunk:
                f.write(chunk)
                f.flush()

    return True

def extract_tomcat_tarball(dest_dir="/usr/local"):
    with esg_bash2py.pushd(dest_dir):
        esg_functions.extract_tarball(
            "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(TOMCAT_VERSION=TOMCAT_VERSION))

        # Create symlink
        create_symlink(TOMCAT_VERSION)
        try:
            os.remove(
                "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(TOMCAT_VERSION=TOMCAT_VERSION))
        except OSError, error:
            print "error:", error
            pass


def create_symlink(TOMCAT_VERSION):
    esg_bash2py.symlink_force(
        "/usr/local/apache-tomcat-{TOMCAT_VERSION}".format(TOMCAT_VERSION=TOMCAT_VERSION), "/usr/local/tomcat")


def remove_example_webapps():
    '''remove Tomcat example applications'''
    with esg_bash2py.pushd("/usr/local/tomcat/webapps"):
        try:
            shutil.rmtree("docs")
            shutil.rmtree("examples")
            shutil.rmtree("host-manager")
            # shutil.rmtree("manager")
        except OSError, error:
            if error.errno == errno.ENOENT:
                pass
            else:
                logger.exception()

def copy_config_files():
    '''copy custom configuration'''
    '''server.xml: includes references to keystore, truststore in /esg/config/tomcat'''
    '''context.xml: increases the Tomcat cache to avoid flood of warning messages'''

    print "\n*******************************"
    print "Copying custom Tomcat config files"
    print "******************************* \n"
    try:
        shutil.copyfile("tomcat_conf/server.xml", "/usr/local/tomcat/conf/server.xml")
        shutil.copyfile("tomcat_conf/context.xml", "/usr/local/tomcat/conf/context.xml")
    #     shutil.copyfile("certs/esg-truststore.ts", "/esg/config/tomcat/esg-truststore.ts")
    #     shutil.copyfile("certs/esg-truststore.ts-orig", "/esg/config/tomcat/esg-truststore.ts-orig")
    #     shutil.copyfile("certs/keystore-tomcat", "/esg/config/tomcat/keystore-tomcat")
        esg_bash2py.mkdir_p("/esg/config/tomcat")
        shutil.copyfile("certs/tomcat-users.xml", "/esg/config/tomcat/tomcat-users.xml")
    #
        shutil.copy("tomcat_conf/setenv.sh", os.path.join(CATALINA_HOME, "bin"))
    except OSError, error:
        # if error.errno == errno.EEXIST:
        #     pass
        # else:
        logger.exception()

    esg_cert_manager.main()

def create_tomcat_user():
    '''Create the Tomcat system user and user group'''
    print "\n*******************************"
    print "Creating Tomcat User"
    print "******************************* \n"

    esg_functions.call_subprocess("groupadd tomcat")
    esg_functions.call_subprocess("useradd -s /sbin/nologin -g tomcat -d /usr/local/tomcat tomcat")
    tomcat_directory = "/usr/local/apache-tomcat-{TOMCAT_VERSION}".format(TOMCAT_VERSION=TOMCAT_VERSION)
    tomcat_user_id = pwd.getpwnam("tomcat").pw_uid
    tomcat_group_id = grp.getgrnam("tomcat").gr_gid
    esg_functions.change_permissions_recursive(tomcat_directory, tomcat_user_id, tomcat_group_id)

    os.chmod("/usr/local/tomcat/webapps", 0775)

def start_tomcat():
    print "\n*******************************"
    print "Attempting to start Tomcat"
    print "******************************* \n"
    return esg_functions.call_subprocess("/usr/local/tomcat/bin/catalina.sh start")

def stop_tomcat():
    esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/catalina.sh stop")

def restart_tomcat():
    stop_tomcat()
    print "Sleeping for 7 seconds to allow shutdown"
    sleep(7)
    start_tomcat()

def check_tomcat_status():
    return esg_functions.call_subprocess("ps -aux | grep tomcat | grep -v grep")

def run_tomcat_config_test():
    esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/catalina.sh configtest")

def copy_credential_files(tomcat_install_config_dir):
    '''Copy Tomcat config files'''
    logger.debug("Moving credential files into node's tomcat configuration dir: %s", config["tomcat_conf_dir"])
    tomcat_credential_files = [config["truststore_file"], config["keystore_file"], config["tomcat_users_file"],
        os.path.join(tomcat_install_config_dir, "hostkey.pem")]

    for file_path in tomcat_credential_files:
        credential_file_name = esg_bash2py.trim_string_from_head(file_path)
        if os.path.exists(os.path.join(tomcat_install_config_dir,credential_file_name)) and not os.path.exists(file_path):
            try:
                shutil.move(os.path.join(tomcat_install_config_dir,credential_file_name), file_path)
            except OSError:
                logger.exception("Could not move file %s", credential_file_name)

    esgf_host = esg_functions.get_esgf_host()
    if os.path.exists(os.path.join(tomcat_install_config_dir, esgf_host +"-esg-node.csr")) and not os.path.exists(os.path.join(config["tomcat_conf_dir"], esgf_host +"-esg-node.csr")):
        shutil.move(os.path.join(tomcat_install_config_dir, esgf_host +"-esg-node.csr"), os.path.join(config["tomcat_conf_dir"], esgf_host +"-esg-node.csr"))

    if os.path.exists(os.path.join(tomcat_install_config_dir, esgf_host +"-esg-node.pem")) and not os.path.exists(os.path.join(config["tomcat_conf_dir"], esgf_host +"-esg-node.pem")):
        shutil.move(os.path.join(tomcat_install_config_dir, esgf_host +"-esg-node.pem"), os.path.join(config["tomcat_conf_dir"], esgf_host +"-esg-node.pem"))


def check_server_xml():
    '''Check the Tomcat server.xml file for the explicit Realm specification needed.'''
    #Be sure that the server.xml file contains the explicit Realm specification needed.
    server_xml_path = os.path.join(config["tomcat_install_dir"],"conf", "server.xml")
    tree = etree.parse(server_xml_path)
    root = tree.getroot()
    realm_element = root.find(".//Realm")
    if realm_element:
        return True

def migrate_tomcat_credentials_to_esgf(esg_dist_url, tomcat_config_dir):
    '''
    Move selected config files into esgf tomcat's config dir (certificate et al)
    Ex: /esg/config/tomcat
    -rw-r--r-- 1 tomcat tomcat 181779 Apr 22 19:44 esg-truststore.ts
    -r-------- 1 tomcat tomcat    887 Apr 22 19:32 hostkey.pem
    -rw-r--r-- 1 tomcat tomcat   1276 Apr 22 19:32 keystore-tomcat
    -rw-r--r-- 1 tomcat tomcat    590 Apr 22 19:32 pcmdi11.llnl.gov-esg-node.csr
    -rw-r--r-- 1 tomcat tomcat    733 Apr 22 19:32 pcmdi11.llnl.gov-esg-node.pem
    -rw-r--r-- 1 tomcat tomcat    295 Apr 22 19:42 tomcat-users.xml
    Only called when migration conditions are present.
    '''
    tomcat_install_config_dir = os.path.join(config["tomcat_install_dir"], "conf")

    if tomcat_install_config_dir != config["tomcat_conf_dir"]:
        if not os.path.exists(config["tomcat_conf_dir"]):
            esg_bash2py.mkdir_p(config["tomcat_conf_dir"])

        esg_functions.backup(tomcat_install_config_dir)

        copy_credential_files(tomcat_install_config_dir)

        os.chown(config["tomcat_conf_dir"], esg_functions.get_user_id("tomcat"), esg_functions.get_group_id("tomcat"))

        if not check_server_xml():
            download_server_config_file(esg_dist_url)

        #SET the server.xml variables to contain proper values
        logger.debug("Editing %s/conf/server.xml accordingly...", config["tomcat_install_dir"])
        edit_tomcat_server_xml(config["keystore_password"])

def edit_tomcat_server_xml(keystore_password):
    server_xml_path = os.path.join(config["tomcat_install_dir"],"conf", "server.xml")
    tree = etree.parse(server_xml_path)
    root = tree.getroot()

    pathname = root.find(".//Resource[@pathname]")
    pathname.set('pathname', config["tomcat_users_file"])
    connector_element = root.find(".//Connector[@truststoreFile]")
    connector_element.set('truststoreFile', config["truststore_file"])
    connector_element.set('truststorePass', config["truststore_password"])
    connector_element.set('keystoreFile', config["keystore_file"])
    connector_element.set('keystorePass', keystore_password)
    connector_element.set('keyAlias', config["keystore_alias"])
    tree.write(open(server_xml_path, "wb"), pretty_print = True)
    tree.write(os.path.join(config["tomcat_install_dir"],"conf", "test_output.xml"), pretty_print = True)


def setup_temp_certs():
    '''Setup temporary certs for testing a standalone node installation'''
    temp_ca_name = "{hostname}-CA".format(hostname=esg_functions.get_esgf_host())
    new_ca_output = esg_functions.call_subprocess("perl CA.pl -newca")


def main():
    print "\n*******************************"
    print "Setting up Tomcat {TOMCAT_VERSION}".format(TOMCAT_VERSION=TOMCAT_VERSION)
    print "******************************* \n"
    if download_tomcat():
        extract_tomcat_tarball()
        remove_example_webapps()
        create_tomcat_user()
        copy_config_files()
        start_tomcat()

if __name__ == '__main__':
    main()
