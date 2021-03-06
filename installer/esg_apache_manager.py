import os
import subprocess
import shutil
import datetime
import socket
import shlex
import filecmp
import git
import esg_bash2py
import esg_version_manager
import esg_functions
import esg_logging_manager
import esg_cert_manager
import esg_init
import yaml
import pip
from distutils.spawn import find_executable

logger = esg_logging_manager.create_rotating_log(__name__)

with open(os.path.join(os.path.dirname(__file__), 'esg_config.yaml'), 'r') as config_file:
    config = yaml.load(config_file)

def check_for_apache_installation():
    if find_executable("httpd"):
        return True
    else:
        return False

def start_apache():
    return esg_functions.call_subprocess("service esgf-httpd start")

def stop_apache():
    esg_functions.stream_subprocess_output("service esgf-httpd stop")

def restart_apache():
    esg_functions.stream_subprocess_output("service esgf-httpd restart")

def check_apache_status():
    return esg_functions.call_subprocess("service esgf-httpd status")

def run_apache_config_test():
    esg_functions.stream_subprocess_output("service esgf-httpd configtest")


def install_python27():
    '''Install python with shared library '''
    with esg_bash2py.pushd("/tmp"):
        python_download_url = "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"

def install_apache_httpd():
    esg_functions.stream_subprocess_output("yum -y update")
    esg_functions.stream_subprocess_output("yum install -y httpd httpd-devel mod_ssl")
    esg_functions.stream_subprocess_output("yum clean all")

    #Custom ESGF Apache files that setup proxying
    shutil.copyfile("apache_conf/esgf-httpd", "/etc/init.d/esgf-httpd")
    os.chmod("/etc/init.d/esgf-httpd", 0755)
    shutil.copyfile("apache_conf/esgf-httpd.conf", "/etc/httpd/conf/esgf-httpd.conf")
    shutil.copyfile("apache_conf/esgf-httpd-local.conf", "/etc/httpd/conf/esgf-httpd-local.conf")
    shutil.copyfile("apache_conf/esgf-httpd-locals.conf", "/etc/httpd/conf/esgf-httpd-locals.conf")


def install_mod_wsgi():
    '''Have to ensure python is install properly with the shared library for mod_wsgi installation to work'''
    print "\n*******************************"
    print "Setting mod_wsgi"
    print "******************************* \n"

    pip.main(['install', "mod_wsgi==4.5.3"])
    with esg_bash2py.pushd("/etc/httpd/modules"):
        #If installer running in a conda env
        if "conda" in find_executable("python"):
            esg_bash2py.symlink_force("/usr/local/conda/envs/esgf-pub/lib/python2.7/site-packages/mod_wsgi/server/mod_wsgi-py27.so", "/etc/httpd/modules/mod_wsgi-py27.so")
        else:
            esg_bash2py.symlink_force("/usr/local/lib/python2.7/site-packages/mod_wsgi/server/mod_wsgi-py27.so", "/etc/httpd/modules/mod_wsgi-py27.so")

def make_python_eggs_dir():
    esg_bash2py.mkdir_p("/var/www/.python-eggs")
    apache_user_id = esg_functions.get_user_id("apache")
    apache_group_id = esg_functions.get_group_id("apache")
    os.chown("/var/www/.python-eggs", apache_user_id, apache_group_id)

def copy_apache_conf_files():
    ''' Copy custom apache conf files '''
    esg_bash2py.mkdir_p("/etc/certs")
    #TODO: Generate certs from esg_cert_manager and copy here
    # esg_cert_manager.create_self_signed_cert("/etc/certs")
    # esg_cert_manager.create_certificate_chain("/etc/certs/hostcert.pem")
    # shutil.copyfile("apache_certs/hostcert.pem", "/etc/certs/hostcert.pem")
    # shutil.copyfile("apache_certs/hostkey.pem", "/etc/certs/hostkey.pem")
    shutil.copyfile("apache_certs/esgf-ca-bundle.crt", "/etc/certs/esgf-ca-bundle.crt")
    # shutil.copyfile("apache_certs/temp_cachain.pem", "/etc/certs/cachain.pem")
    shutil.copyfile("apache_html/index.html", "/var/www/html/index.html")
    # shutil.copyfile("apache_conf/httpd.conf", "/etc/httpd/conf.d/httpd.conf")
    shutil.copyfile("apache_conf/ssl.conf", "/etc/httpd/conf.d/ssl.conf")

def main():
    print "\n*******************************"
    print "Setting up Apache (httpd) Web Server"
    print "******************************* \n"

    if check_for_apache_installation():
        print "Found existing Apache installation."
        esg_functions.call_subprocess("httpd -version")
        continue_install = raw_input("Would you like to continue the Apache installation anyway? [y/N]: ") or "N"
        if continue_install.lower() in ["no", "n"]:
            return
    install_apache_httpd()
    install_mod_wsgi()
    make_python_eggs_dir()
    copy_apache_conf_files()
    start_apache()

if __name__ == '__main__':
    main()
