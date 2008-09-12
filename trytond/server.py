#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"""
%prog [options]
"""
import logging
format='[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
datefmt='%a %b %d %H:%M:%S %Y'
logging.basicConfig(level=logging.DEBUG, format=format, datefmt=datefmt)
import sys, os, signal
import netsvc
import time
import psycopg2
import pooler
import sql_db
import config
from config import CONFIG
import web_service
import wkf_service
from module import register_classes
import mx.DateTime
from getpass import getpass
import sha
import logging
import logging.handlers
import threading


class TrytonServer(object):

    def __init__(self):

        if CONFIG['logfile']:
            logf = CONFIG['logfile']
            # test if the directories exist, else create them
            try:
                handler = logging.handlers.TimedRotatingFileHandler(
                    logf, 'D', 1, 30)
            except Exception, exception:
                sys.stderr.write("ERROR: couldn't create the logfile directory:" \
                        + str(exception))
            else:
                formatter = logging.Formatter(format, datefmt)
                # tell the handler to use this format
                handler.setFormatter(formatter)

                # add the handler to the root logger
                logging.getLogger().addHandler(handler)
                logging.getLogger().setLevel(logging.INFO)
        elif os.name != 'nt':
            reverse = '\x1b[7m'
            reset = '\x1b[0m'
            # reverse color for error and critical messages
            for level in logging.ERROR, logging.CRITICAL:
                msg = reverse + logging.getLevelName(level) + reset
                logging.addLevelName(level, msg)

        self.logger = logging.getLogger("init")

        if not hasattr(mx.DateTime, 'strptime'):
            mx.DateTime.strptime = lambda x, y: mx.DateTime.mktime(
                    time.strptime(x, y))

        self.logger.info('using %s as configuration file' % CONFIG.configfile)
        self.logger.info('initialising distributed objects services')

        self.dispatcher = netsvc.Dispatcher()
        self.dispatcher.monitor(signal.SIGINT)


        web_service.DB()
        web_service.Common()
        web_service.Object()
        web_service.Wizard()
        web_service.Report()

        wkf_service.WorkflowService()

    def run(self):
        "Run the server and never return"

        update_module = False
        init = {}
        for db_name in CONFIG["db_name"]:
            cursor = None
            try:
                if db_name:
                    cursor = pooler.get_db_only(db_name).cursor()
            except psycopg2.OperationalError:
                self.logger.info("could not connect to database '%s'!" % db_name,)

            init[db_name] = False
            if cursor and CONFIG['init']:
                cursor.execute("SELECT relname " \
                        "FROM pg_class " \
                        "WHERE relkind = 'r' AND relname in (" \
                        "'inherit', "
                        "'ir_model', "
                        "'ir_model_field', "
                        "'ir_ui_view', "
                        "'ir_ui_menu', "
                        "'res_user', "
                        "'res_group', "
                        "'res_group_user_rel', "
                        "'wkf', "
                        "'wkf_activity', "
                        "'wkf_transition', "
                        "'wkf_instance', "
                        "'wkf_workitem', "
                        "'wkf_witm_trans', "
                        "'ir_module_category', "
                        "'ir_module_module', "
                        "'ir_module_module_dependency, '"
                        "'ir_translation, '"
                        "'ir_lang'"
                        ")")
                if len(cursor.fetchall()) == 0:
                    self.logger.info("init db")
                    sql_db.init_db(cursor)
                    init[db_name] = True
                cursor.commit()

            register_classes()

            if db_name:
                lang = None
                if cursor:
                    cursor.execute('SELECT code FROM ir_lang ' \
                            'WHERE translatable = True')
                    lang = [x[0] for x in cursor.fetchall()]
                    cursor.close()
                update_module = bool(CONFIG['init'] or CONFIG['update'])
                pooler.get_db_and_pool(db_name, update_module=update_module,
                        lang=lang)
        else:
            register_classes()

        for kind in ('init', 'update'):
            CONFIG[kind] = {}

        for db_name in CONFIG['db_name']:
            if init[db_name]:
                while True:
                    password = getpass('Admin Password for %s:' % db_name)
                    password2 = getpass('Admin Password Confirmation:')
                    if password != password2:
                        sys.stderr.write('Admin Password Confirmation doesn\'t match ' \
                                'Admin Password!\n')
                        continue
                    if not password:
                        sys.stderr.write('Admin Password is required!\n')
                        continue
                    break

                cursor = pooler.get_db_only(db_name).cursor()
                cursor.execute('UPDATE res_user ' \
                        'SET password = %s ' \
                        'WHERE login = \'admin\'',
                        (sha.new(password).hexdigest(),))
                cursor.commit()
                cursor.close()

        if update_module:
            self.logger.info('Update/Init succeed!')
            sys.exit(0)

        # Launch Server
        secure = CONFIG["secure"]
        if CONFIG['xmlrpc']:
            interface = CONFIG["interface"]
            try:
                port = int(CONFIG["xmlport"])
            except:
                self.logger.error("invalid port '%s'!" % (CONFIG["xmlport"],))
                sys.exit(1)

            httpd = netsvc.HttpDaemon(interface, port, secure)

            xml_gw = netsvc.XmlRpc.RpcGateway('web-service')
            httpd.attach("/xmlrpc", xml_gw )
            logging.getLogger("web-service").info(
                "starting XML-RPC" + (CONFIG['secure'] and ' Secure' or '') + \
                    " services, port " + str(port))

        if CONFIG['netrpc']:
            interface = CONFIG["interface"]
            try:
                port = int(CONFIG["netport"])
            except:
                self.logger.error("invalid port '%s'!" % (CONFIG["netport"],))
                sys.exit(1)

            tinysocket = netsvc.TinySocketServerThread(interface, port,
                    secure)
            logging.getLogger("web-service").info(
                "starting netrpc service, port " + str(port))

        if CONFIG['webdav']:
            interface = CONFIG['interface']
            try:
                port = int(CONFIG['webdavport'])
            except:
                self.logger.error("invalid port '%s'!" % (CONFIG['webdavport'],))
                sys.exit(1)

            webdavd = netsvc.WebDAVServerThread(interface, port, secure)
            logging.getLogger("web-service").info(
                    'starting webdav service, port ' + str(port))

        def handler(signum, frame):
            if CONFIG['netrpc']:
                tinysocket.stop()
            if CONFIG['xmlrpc']:
                httpd.stop()
            if CONFIG['webdav']:
                webdavd.stop()
            if CONFIG['pidfile']:
                os.unlink(CONFIG['pidfile'])
            sys.exit(0)

        if CONFIG['pidfile']:
            fd_pid = open(CONFIG['pidfile'], 'w')
            pidtext = "%d" % (os.getpid())
            fd_pid.write(pidtext)
            fd_pid.close()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        self.logger.info('the server is running, waiting for connections...')
        if CONFIG['netrpc']:
            tinysocket.start()
        if CONFIG['xmlrpc']:
            httpd.start()
        if CONFIG['webdav']:
            webdavd.start()
        #DISPATCHER.run()

        try:
            import psyco
            psyco.full()
        except ImportError:
            pass

        now = time.time()
        while True:
            time.sleep(1)
            if time.time() - now >= 60:
                for dbname in pooler.get_db_list():
                    pool = pooler.get_pool(dbname)
                    cron_obj = pool.get('ir.cron')
                    thread = threading.Thread(
                            target=cron_obj.pool_jobs,
                            args=(dbname,), kwargs={})
                    thread.start()
                now = time.time()

if __name__ == "__main__":
    SERVER = TrytonServer()
    SERVER.run()
