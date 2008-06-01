import ConfigParser, optparse, os, sys
import logging
from version import VERSION
from netsvc import LOG_CRITICAL, LOG_ERROR, LOG_WARNING
from netsvc import LOG_INFO, LOG_DEBUG


class ConfigManager(object):
    def __init__(self, fname=None):
        self.options = {
            'interface': '',
            'netrpc': True,
            'netport': '8070',
            'xmlrpc': False,
            'xmlport': '8069',
            'webdav': False,
            'webdavport': '8080',
            'db_host': False,
            'db_port': False,
            'db_name': False,
            'db_user': False,
            'db_password': False,
            'db_maxconn': 64,
            'pg_path': None,
            'admin_passwd': 'admin',
            'verbose': False,
            'debug_mode': False,
            'pidfile': None,
            'logfile': None,
            'secure': False,
            'privatekey': '/etc/ssl/trytond/server.key',
            'certificate': '/etc/ssl/trytond/server.pem',
            'smtp_server': 'localhost',
            'smtp_user': False,
            'smtp_password': False,
            'stop_after_init': False,
            'data_path': '/var/lib/trytond',
            'max_thread': 40,
        }

        parser = optparse.OptionParser(version=VERSION)

        parser.add_option("-c", "--config", dest="config",
                help="specify alternate config file")
        parser.add_option('--debug', dest='debug_mode', action='store_true',
                help='enable debug mode')
        parser.add_option("-v", "--verbose", action="store_true",
                dest="verbose", help="enable debugging")

        parser.add_option("--stop-after-init", action="store_true",
                dest="stop_after_init",
                help="stop the server after it initializes")

        parser.add_option("-d", "--database", dest="db_name",
                help="specify the database name")
        parser.add_option("-i", "--init", dest="init",
                help="init a module (use \"all\" for all modules)")
        parser.add_option("-u", "--update", dest="update",
                help="update a module (use \"all\" for all modules)")

        (opt, args) = parser.parse_args()

        if opt.config:
            self.configfile = opt.config
        else:
            configdir = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(__file__), '..')))
            prefixdir = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(sys.prefix), '..')))
            self.configfile = os.path.join(configdir, 'etc', 'trytond.conf')
            if not os.path.isfile(self.configfile):
                self.configfile = os.path.join(prefixdir, 'etc', 'trytond.conf')
        self.load()

        # Verify that we want to log or not, if not the output will go to stdout
        if self.options['logfile'] in ('None', 'False'):
            self.options['logfile'] = False
        # the same for the pidfile
        if self.options['pidfile'] in ('None', 'False'):
            self.options['pidfile'] = False
        if self.options['data_path'] in ('None', 'False'):
            self.options['data_path'] = False

        for arg in (
                'db_name',
                'verbose',
                'debug_mode',
                'stop_after_init',
                ):
            if getattr(opt, arg) != None:
                self.options[arg] = getattr(opt, arg)

        init = {}
        if opt.init:
            for i in opt.init.split(','):
                init[i] = 1
        self.options['init'] = init

        update = {}
        if opt.update:
            for i in opt.update.split(','):
                update[i] = 1
        self.options['update'] = update

    def load(self):
        parser = ConfigParser.ConfigParser()
        try:
            parser.read([self.configfile])
            for (name, value) in parser.items('options'):
                if value == 'True' or value == 'true':
                    value = True
                if value == 'False' or value == 'false':
                    value = False
                self.options[name] = value
        except IOError:
            pass
        except ConfigParser.NoSectionError:
            pass

    def get(self, key, default=None):
        return self.options.get(key, default)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options[key]

CONFIG = ConfigManager()
