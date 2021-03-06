import os
import re
import socket
import tld
import urlparse
import getpass
from esg_exceptions import UnverifiedScriptError
from distutils.spawn import find_executable
import esg_functions
import esg_property_manager
import esg_version_manager
import esg_logging_manager
import esg_bash2py
import esg_init
import yaml
import semver
import readline

logger = esg_logging_manager.create_rotating_log(__name__)

with open(os.path.join(os.path.dirname(__file__), 'esg_config.yaml'), 'r') as config_file:
    config = yaml.load(config_file)

def _choose_admin_password(password_file=config["esgf_secret_file"]):
    '''Sets the ESGF password that is stored in /esg/config/.esgf_pass'''
    while True:
        password_input = getpass.getpass(
            "What is the admin password to use for this installation? (alpha-numeric only): ")
        if not _is_valid_password(password_input):
            continue

        password_input_confirmation = getpass.getpass(
            "Please re-enter password to confirm: ")

        if esg_functions.confirm_password(password_input, password_input_confirmation):
            esg_functions.set_security_admin_password(password_input)
            break


def _choose_organization_name(force_install=False):
    esg_root_id = esg_property_manager.get_property("esg_root_id")
    if esg_root_id:
        logger.info("esg_root_id = [%s]", esg_root_id)
        return
    elif force_install:
        try:
            default_org_name = tld.get_tld(
                "http://" + socket.gethostname(), as_object=True).domain
        except tld.exceptions.TldDomainNotFound, error:
            logger.exception("Could not find top level domain for %s.", socket.gethostname())
            default_org_name = "llnl"
        while True:
            org_name_input = raw_input("What is the name of your organization? [{default_org_name}]: ".format(default_org_name=default_org_name)) or default_org_name
            org_name_input.replace("", "_")
            esg_property_manager.write_as_property("esg_root_id", org_name_input)
            break

def _choose_node_short_name(force_install=False):
    node_short_name = esg_property_manager.get_property("node_short_name")
    if not node_short_name or force_install:
        while True:
            node_short_name_input = raw_input("Please give this node a \"short\" name [{node_short_name}]: ".format(node_short_name=node_short_name)) or node_short_name
            node_short_name_input.replace("", "_")
            esg_property_manager.write_as_property(
                "node_short_name", node_short_name_input)
            break
    else:
        logger.info("node_short_name = [%s]", node_short_name)


def _choose_node_long_name(force_install=False):
    node_long_name = esg_property_manager.get_property("node_long_name")
    if not node_long_name or force_install:
        while True:
            node_long_name_input = raw_input("Please give this node a more descriptive \"long\" name [{node_long_name}]: ".format(
                node_long_name=node_long_name)) or node_long_name
            esg_property_manager.write_as_property(
                "node_long_name", node_long_name_input)
            break
    else:
        logger.info("node_long_name = [%s]", node_long_name)


def _choose_node_namespace(force_install=False):
    node_namespace = esg_property_manager.get_property("node_namespace")
    if not node_namespace or force_install:
        try:
            top_level_domain = tld.get_tld(
                "http://" + socket.gethostname(), as_object=True)
            domain = top_level_domain.domain
            suffix = top_level_domain.suffix
            default_node_namespace = suffix + "." + domain
        except tld.exceptions.TldDomainNotFound, error:
            top_level_domain = None
            default_node_namespace = None
        while True:
            node_namespace_input = raw_input("What is the namespace to use for this node? (set to your reverse fqdn - Ex: \"gov.llnl\") [{default_node_namespace}]: ".format(
                default_node_namespace=default_node_namespace)) or default_node_namespace
            namespace_pattern_requirement = re.compile("(\w+.{1}\w+)$")
            if not namespace_pattern_requirement.match(node_namespace_input):
                print "Namespace entered is not in a valid format.  Valid format is [suffix].[domain].  Example: gov.llnl"
                continue
            else:
                esg_property_manager.write_as_property(
                    "node_namespace", node_namespace_input)
                break
    else:
        logger.info("node_namespace = [%s]", node_namespace)


def _choose_node_peer_group(force_install=False):
    node_peer_group = esg_property_manager.get_property("node_peer_group")
    if node_peer_group:
        logger.info("node_peer_group = [%s]", node_peer_group)
        return
    if not node_peer_group or force_install:
        try:
            node_peer_group
        except NameError:
            node_peer_group = "esgf-dev"
        while True:
            print "Only choose esgf-test for test federation install or esgf-prod for production installation.  Otherwise choose esgf-dev."
            node_peer_group_input = raw_input(
                "What peer group(s) will this node participate in? (esgf-test|esgf-prod|esgf-dev) [{node_peer_group}]: ".format(node_peer_group=node_peer_group)) or node_peer_group
            if node_peer_group_input.strip() not in ["esgf-test", "esgf-prod", "esgf-dev"]:
                print "Invalid Selection: {node_peer_group_input}".format(node_peer_group_input=node_peer_group_input)
                print "Please choose either esgf-test, esgf-dev, or esgf-prod"
                continue
            else:
                esg_property_manager.write_as_property(
                    "node_peer_group", node_peer_group_input)
                break

def _choose_esgf_index_peer(force_install=False):
    esgf_index_peer = esg_property_manager.get_property("esgf_index_peer")
    esgf_default_peer = esg_property_manager.get_property("esgf_default_peer")
    esgf_host = esg_property_manager.get_property("esgf_host")
    if not esgf_index_peer or force_install:
        default_esgf_index_peer = esgf_default_peer or esgf_host or socket.getfqdn()
        esgf_index_peer_input = raw_input("What is the hostname of the node do you plan to publish to? [{default_esgf_index_peer}]: ".format(
            default_esgf_index_peer=default_esgf_index_peer)) or default_esgf_index_peer
        esg_property_manager.write_as_property(
            "esgf_index_peer", esgf_index_peer_input)
    else:
        logger.info("esgf_index_peer = [%s]", esgf_index_peer)


def _choose_mail_admin_address(force_install=False):
    mail_admin_address = esg_property_manager.get_property("mail_admin_address")
    if not mail_admin_address or force_install:
        mail_admin_address_input = raw_input(
            "What email address should notifications be sent as? [{mail_admin_address}]: ".format(mail_admin_address=mail_admin_address))
        if mail_admin_address_input:
            esg_property_manager.write_as_property(
                "mail_admin_address", mail_admin_address_input)
        else:
            print " (The notification system will not be enabled without an email address)"
    else:
        logger.info("mail_admin_address = [%s]", mail_admin_address)


def _choose_publisher_db_user(force_install=False):
    default_publisher_db_user = None
    publisher_db_user = esg_property_manager.get_property("publisher_db_user")
    if publisher_db_user:
        print "Found existing value for property publisher_db_user: {publisher_db_user}".format(publisher_db_user=publisher_db_user)
        logger.info("publisher_db_user: %s", publisher_db_user)
        return
    if not publisher_db_user or force_install:
        default_publisher_db_user = publisher_db_user or "esgcet"
        publisher_db_user_input = raw_input(
            "What is the (low privilege) db account for publisher? [{default_publisher_db_user}]: ".format(default_publisher_db_user=default_publisher_db_user)) or default_publisher_db_user
        esg_property_manager.write_as_property(
            "publisher_db_user", publisher_db_user_input)

def _choose_publisher_db_user_passwd(force_install=False):
    if config["publisher_db_user_passwd"] or esg_functions.get_publisher_password():
        print "Using previously configured publisher DB password"
        return

    if force_install:
        publisher_db_user = esg_property_manager.get_property("publisher_db_user") or "esgcet"
        publisher_db_user_passwd_input = getpass.getpass(
            "What is the db password for publisher user ({publisher_db_user})?: ".format(publisher_db_user=publisher_db_user))

        password_input_confirmation = getpass.getpass(
            "Please re-enter password to confirm: ")

        if esg_functions.confirm_password(publisher_db_user_passwd_input, password_input_confirmation):
            esg_functions.set_publisher_password(publisher_db_user_passwd_input)

def initial_setup_questionnaire(force_install=False):
    print "-------------------------------------------------------"
    print 'Welcome to the ESGF Node installation program! :-)'
    print "-------------------------------------------------------"

    esg_bash2py.mkdir_p(config['esg_config_dir'])

    starting_directory = os.getcwd()

    os.chdir(config['esg_config_dir'])

    esgf_host = esg_property_manager.get_property("esgf_host")
    _choose_fqdn(esgf_host)

    if not esg_functions.get_security_admin_password() or force_install:
        _choose_admin_password()
    else:
        logger.info("Previously set password found.")

    _choose_organization_name()
    _choose_node_short_name()
    _choose_node_long_name()
    _choose_node_namespace()
    _choose_node_peer_group()
    _choose_esgf_index_peer()
    _choose_mail_admin_address()

    #TODO:Extract constructring DB string into separate function
    db_properties = get_db_properties()

    if not all(db_properties) or force_install:
        _is_managed_db(db_properties)
        _get_db_conn_str_questionnaire(db_properties)
    else:
        if db_properties["db_host"] == esgf_host or db_properties["db_host"] == "localhost":
            print "db_connection_string = {db_user}@localhost".format(db_user=db_properties["db_user"])
        else:
            connstring_ = "{db_user}@{db_host}:{db_port}/{db_database} [external = ${db_managed}]".format(db_user=db_properties["db_user"],
                                                                                                          db_host=db_properties[
                                                                                                              "db_host"],
                                                                                                          db_port=db_properties[
                                                                                                              "db_port"],
                                                                                                          db_database=db_properties[
                                                                                                              "db_database"],
                                                                                                          db_managed=db_properties["db_managed"])

    _choose_publisher_db_user()
    _choose_publisher_db_user_passwd()

    os.chmod(config['pub_secret_file'], 0640)
    if "tomcat" not in esg_functions.get_group_list():
        esg_functions.add_unix_group(config["tomcat_group"])
    os.chown(config['esgf_secret_file'], config[
             "installer_uid"], esg_functions.get_tomcat_group_id())

    if db_properties["db_host"] == esgf_host or db_properties["db_host"] == "localhost":
        logger.info("db publisher connection string %s@localhost",
                    db_properties["db_user"])
    else:
        logger.info("db publisher connection string %s@%s:%s/%s",
                    db_properties["db_user"], db_properties["db_host"], db_properties["db_port"], db_properties["db_database"])

    os.chdir(starting_directory)

    return True


def get_db_properties():
    db_properties_dict = {"db_user": None, "db_host": None,
                          "db_port": None, "db_database": None, "db_managed": None}
    for key, _ in db_properties_dict.items():
        db_properties_dict[key] = esg_property_manager.get_property(key)

    return db_properties_dict




def _get_db_conn_str_questionnaire(db_properties, force_install=False):
    # postgresql://esgcet@localhost:5432/esgcet
    user_ = None
    host_ = None
    port_ = None
    dbname_ = None
    connstring_ = None
    valid_connection_string = None

    # Note the values referenced here should have been set by prior get_property *** calls
    # that sets these values in the script scope. (see the call in
    # questionnaire function - above)
    esgf_host = esg_property_manager.get_property("esgf_host")
    if not db_properties["db_user"] or not db_properties["db_host"] or not db_properties["db_port"] or not db_properties["db_database"]:
        if not db_properties["db_host"]:
            if db_properties["db_host"] == esgf_host or db_properties["db_host"] == "localhost":
                connstring_ = "{db_user}@localhost"
            else:
                connstring_ = "{db_user}@{db_host}:{db_port}/{db_database}"
    while True:
        print "Please enter the database connection string..."
        print " (form: postgresql://[username]@[host]:[port]/esgcet)"
        db_managed = esg_property_manager.get_property("db_managed")
        #(if it is a not a force install and we are using a LOCAL (NOT MANAGED) database then db_managed == "no")
        if not connstring_ and db_managed != "yes" and not force_install:
            connstring_ = "dbsuper@localhost:5432/esgcet"
        db_connection_input = raw_input(
            "What is the database connection string? [postgresql://${connstring_}]: postgresql://".format(connstring_=connstring_)) or connstring_
        parsed_db_conn_string = urlparse.urlparse(db_connection_input)
        # result.path[1:] is database name
        if not parsed_db_conn_string.username or not parsed_db_conn_string.hostname or parsed_db_conn_string.port or parsed_db_conn_string.result.path[1:]:
            logger.error("ERROR: Incorrect connection string syntax or values")
            valid_connection_string = False
        else:
            valid_connection_string = True
            break
    logger.debug("user = %s", user_)
    logger.debug("host = %s", host_)
    logger.debug("port = %s", port_)
    logger.debug("database = %s", dbname_)

    # write vars to property file
    esg_property_manager.write_as_property("db_user", user_)
    esg_property_manager.write_as_property("db_host", host_)
    esg_property_manager.write_as_property("db_port", port_)
    esg_property_manager.write_as_property("db_database", dbname_)

    logger.debug("valid_connection_string: %s",  valid_connection_string)
    return valid_connection_string


def _is_managed_db(db_properties, force_install=False):
    '''
        responds true (returns 0) if this IS intended to be a managed database
        is expecting the vars:
        ---- "db_host"
        ---- "esgf_host"
        to be set
        Define: managed - (true|0) this means NOT manipulated by this script but done by external means
        (hint prepend "externally" before managed to get the meaning - yes I find it confusing but Stephen likes this term :-))
        db_managed=no means that it is a LOCAL database. (I have to change this damn verbiage... what I get for following pasco-speak ;-).
    '''
    db_managed_default = None
    default_selection_output = None
    db_managed = esg_property_manager.get_property("db_managed")
    if not force_install:
        if db_managed == "yes":
            return True
        else:
            return False

    if not db_managed:
        esgf_host = esg_property_manager.get_property("esgf_host")
        logger.debug("esgf_host = %s", esgf_host)
        logger.debug("db_host = %s", db_properties["db_host"])

        # Try to come up with some "sensible" default value for the user...
        if db_properties["db_host"] == esgf_host or db_properties["db_host"] == "localhost" or not db_properties["db_host"]:
            db_managed_default = "no"
            default_selection_output = "[y/N]:"
        else:
            db_managed_default = "yes"
            default_selection_output = "[Y/n]:"

        external_db_input = raw_input(
            "Is the database external to this node? " + default_selection_output)
        if not external_db_input:
            db_managed = db_managed_default
            esg_property_manager.write_as_property("db_managed", db_managed)
        else:
            if external_db_input.lower() == "y" or external_db_input.lower() == "yes":
                db_managed == "yes"
            else:
                db_managed == "no"
            esg_property_manager.write_as_property("db_managed", db_managed)
    else:
        logger.info("db_managed = [%s]", db_managed)

    if db_managed == "yes":
        print "Set to use externally \"managed\" database on host: {db_host}".format(db_host=db_properties["db_host"])
        return True
    else:
        logger.debug("(hmm... setting db_host to localhost)")
        # Note: if not managed and on the local machine... always use
        # "localhost"
        db_properties["db_host"] = "localhost"
        return False

def _choose_fqdn(esgf_host, force_install=False):
    if not esgf_host or force_install:
        default_host_name = esgf_host or socket.getfqdn()
        defaultdomain_regex = r"^\w+-*\w*\W*(.+)"
        defaultdomain = re.search(
            defaultdomain_regex, default_host_name).group(1)
        if not default_host_name:
            default_host_name = "localhost.localdomain"
        elif not defaultdomain:
            default_host_name = default_host_name + ".localdomain"

        default_host_name = raw_input("What is the fully qualified domain name of this node? [{default_host_name}]: ".format(
            default_host_name=default_host_name)) or default_host_name
        esgf_host = default_host_name
        logger.info("esgf_host = [%s]", esgf_host)
        esg_property_manager.write_as_property("esgf_host", esgf_host)
    else:
        logger.info("esgf_host = [%s]", esgf_host)
        esg_property_manager.write_as_property("esgf_host", esgf_host)


def _is_valid_password(password_input):
    if not password_input or not str.isalnum(password_input):
        print "Invalid password... "
        return False
    if not password_input or len(password_input) < 6:
        print "Sorry password must be at least six characters :-( "
        return False
    else:
        return True

def _update_postgres_password():
    '''Updates the Postgres system account password; gets saved to /esg/config/.esg_pg_pass'''
    if not esg_functions.get_tomcat_group_id():
        esg_functions.add_unix_group(config["tomcat_group"])
    tomcat_group_id = esg_functions.get_tomcat_group_id()

    try:
        with open(config['pg_secret_file'], "w") as secret_file:
            secret_file.write(config["pg_sys_acct_passwd"])
    except IOError:
        logger.exception("Could not open %s", config['pg_secret_file'])

    os.chmod(config['pg_secret_file'], 0640)
    try:
        os.chown(config['pg_secret_file'], config[
                 "installer_uid"], tomcat_group_id)
    except OSError:
        logger.exception("Unable to change ownership of %s", config["pg_secret_file"])
