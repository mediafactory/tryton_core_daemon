#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE, cursor
from psycopg2 import IntegrityError
import psycopg2
import re
import os
from mx import DateTime as mdt
import zipfile
import version
from config import CONFIG
from netsvc import Logger, LOG_ERROR, LOG_WARNING

RE_FROM = re.compile('.* from "?([a-zA-Z_0-9]+)"?.*$')
RE_INTO = re.compile('.* into "?([a-zA-Z_0-9]+)"?.*$')

class tryton_cursor(cursor):

    def __build_dict(self, row):
        res = {}
        for i in range(len(self.description)):
            res[self.description[i][0]] = row[i]
        return res

    def dictfetchone(self):
        row = self.fetchone()
        if row:
            return self.__build_dict(row)
        else:
            return row

    def dictfetchmany(self, size):
        res = []
        rows = self.fetchmany(size)
        for row in rows:
            res.append(self.__build_dict(row))
        return res

    def dictfetchall(self):
        res = []
        rows = self.fetchall()
        for row in rows:
            res.append(self.__build_dict(row))
        return res


class FakeCursor(object):
    nbr = 0
    _tables = {}
    sql_from_log = {}
    sql_into_log = {}
    sql_log = False
    count = 0
    IN_MAX = 1000

    def __init__(self, connpool, conn, dbname, cursor_factory):
        self._connpool = connpool
        self.conn = conn
        self.cursor_factory = cursor_factory
        self.cursor = conn.cursor(cursor_factory=self.cursor_factory)
        self.dbname = dbname

    def execute(self, sql, params=None):
        if not params:
            params = ()

        if self.sql_log:
            now = mdt.now()
        if params:
            res = self.cursor.execute(sql, params)
        else:
            res = self.cursor.execute(sql)
        if self.sql_log:
            self.count += 1
            res_from = RE_FROM.match(sql.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)][0] += 1
                self.sql_from_log[res_from.group(1)][1] += mdt.now() - now
            res_into = RE_INTO.match(sql.lower())
            if res_into:
                self.sql_into_log.setdefault(res_into.group(1), [0, 0])
                self.sql_into_log[res_into.group(1)][0] += 1
                self.sql_into_log[res_into.group(1)][1] += mdt.now() - now
        return res

    def print_log(self, sql_type='from'):
        print "SQL LOG %s:" % (sql_type,)
        if sql_type == 'from':
            logs = self.sql_from_log.items()
        else:
            logs = self.sql_into_log.items()
        logs.sort(lambda x, y: cmp(x[1][1], y[1][1]))
        amount = 0
        for log in logs:
            print "table:", log[0], ":", str(log[1][1]), "/", log[1][0]
            amount += log[1][1]
        print "SUM:%s/%d"% (amount, self.count)

    def close(self):
        if self.sql_log:
            self.print_log('from')
            self.print_log('into')
        self.cursor.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self.cursor
        self._connpool.putconn(self.conn)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class FakeDB:

    def __init__(self, connpool, dbname):
        self._connpool = connpool
        self.dbname = dbname

    def cursor(self, cursor_factory=tryton_cursor):
        conn = self._connpool.getconn()
        conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        return FakeCursor(self._connpool, conn, self.dbname,
                cursor_factory=cursor_factory)

    def close(self):
        self._connpool.closeall()

def db_connect(db_name):
    host = CONFIG['db_host'] and "host=%s" % CONFIG['db_host'] or ''
    port = CONFIG['db_port'] and "port=%s" % CONFIG['db_port'] or ''
    name = "dbname=%s" % db_name
    user = CONFIG['db_user'] and "user=%s" % CONFIG['db_user'] or ''
    password = CONFIG['db_password'] \
            and "password=%s" % CONFIG['db_password'] or ''
    maxconn = int(CONFIG['db_maxconn']) or 64
    dsn = '%s %s %s %s %s' % (host, port, name, user, password)
    connpool = ThreadedConnectionPool(0, maxconn, dsn)
    return FakeDB(connpool, db_name)

def init_db(cursor):
    sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
    for line in file(sql_file).read().split(';'):
        if (len(line)>0) and (not line.isspace()):
            cursor.execute(line)

    opj = os.path.join
    modules_path = os.path.join(os.path.dirname(__file__), 'modules')
    modules = []
    if os.path.exists(modules_path) and os.path.isdir(modules_path):
        modules = os.listdir(modules_path)

    for i in (modules + ['ir', 'workflow', 'res', 'webdav']):
        tryton_file = opj(modules_path, i, '__tryton__.py')
        mod_path = opj(modules_path, i)
        if i in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.dirname(__file__)
            tryton_file = opj(root_path, i, '__tryton__.py')
            mod_path = opj(root_path, i)
        info = {}
        if os.path.isfile(tryton_file) \
                and not os.path.isfile(opj(modules_path, i + '.zip')):
            info = eval(file(tryton_file).read())
        elif zipfile.is_zipfile(mod_path):
            zfile = zipfile.ZipFile(mod_path)
            i = os.path.splitext(i)[0]
            info = eval(zfile.read(opj(i, '__tryton__.py')))
        if info:
            categs = info.get('category', 'Uncategorized').split('/')
            p_id = None
            while categs:
                if p_id is not None:
                    cursor.execute('SELECT id ' \
                            'FROM ir_module_category ' \
                            'WHERE name = %s AND parent = %s',
                            (categs[0], p_id))
                else:
                    cursor.execute('SELECT id ' \
                            'FROM ir_module_category ' \
                            'WHERE name = %s AND parent is NULL',
                            (categs[0],))
                c_id = cursor.fetchone()
                if not c_id:
                    cursor.execute(
                            'SELECT NEXTVAL(\'ir_module_category_id_seq\')')
                    c_id = cursor.fetchone()[0]
                    cursor.execute('INSERT INTO ir_module_category ' \
                            '(id, name, parent) ' \
                            'VALUES (%s, %s, %s)', (c_id, categs[0], p_id))
                else:
                    c_id = c_id[0]
                p_id = c_id
                categs = categs[1:]

            active = info.get('active', False)
            installable = info.get('installable', True)
            if installable:
                if active:
                    state = 'to install'
                else:
                    state = 'uninstalled'
            else:
                state = 'uninstallable'
            cursor.execute('SELECT NEXTVAL(\'ir_module_module_id_seq\')')
            module_id = cursor.fetchone()[0]
            cursor.execute('INSERT INTO ir_module_module ' \
                    '(id, author, website, name, shortdesc, ' \
                    'description, category, state) ' \
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (module_id, info.get('author', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), p_id, state))
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(module, name) VALUES (%s, %s)',
                        (module_id, dependency))

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)



def table_exist(cursor, table_name):
    cursor.execute("SELECT relname FROM pg_class " \
                       "WHERE relkind = 'r' AND relname = %s",
                   (table_name,))
    return bool(cursor.rowcount)


class table_handler:

    def __init__(self, cursor, table_name, object_name=None, module_name=None):
        self.table_name = table_name
        self.table = {}
        self.constraint = []
        self.fk_deltype = {}
        self.index = {}
        self.field2module = {}
        self.module_name = module_name
        self.cursor = cursor
        self.object_name = object_name

        # Create new table if necessary
        if not table_exist(self.cursor, self.table_name):
            self.cursor.execute('CREATE TABLE "%s" ' \
                             "(id SERIAL NOT NULL, " \
                             "PRIMARY KEY(id))"% self.table_name)
        self.update_definitions()

    def update_definitions(self):
        # Fetch columns definitions from the table
        self.cursor.execute("SELECT at.attname, at.attlen, "\
                         "at.atttypmod, at.attnotnull, at.atthasdef, "\
                         "ty.typname, "\
                         "CASE WHEN at.attlen = -1 "\
                           "THEN at.atttypmod-4 "\
                           "ELSE at.attlen END as size "\
                       "FROM pg_class cl "\
                         "JOIN pg_attribute at on (cl.oid = at.attrelid) "\
                         "JOIN pg_type ty on (at.atttypid = ty.oid) "\
                       "WHERE cl.relname = %s AND at.attnum > 0",
                       (self.table_name,))
        self.table = {}
        for line in self.cursor.fetchall():
            column, length, typmod, notnull, hasdef, typname, size = line
            self.table[column] = {
                "length": length,
                "typmod": typmod,
                "notnull": notnull ,
                "hasdef": hasdef,
                "size": size,
                "typname": typname}

        # fetch constrains for the table
        self.cursor.execute("SELECT co.contype, co.confdeltype, at.attname, "\
                         "cl2.relname, co.conname "\
                       "FROM pg_constraint co "\
                         "LEFT JOIN pg_class cl on (co.conrelid = cl.oid) "\
                         "LEFT JOIN pg_class cl2 on (co.confrelid = cl2.oid) "\
                         "LEFT JOIN pg_attribute at on (co.conkey[1] = at.attnum) "\
                       "WHERE cl.relname = %s",
                       (self.table_name,))
        self.constraint = []
        self.fk_deltype = {}
        for line in self.cursor.fetchall():
            contype, confdeltype, column, ref, conname = line
            if contype == 'f':
                self.fk_deltype[column] = confdeltype
            else:
                if conname not in self.constraint:
                    self.constraint.append(conname)

        # Fetch indexes defined for the table
        self.cursor.execute("SELECT cl2.relname "\
                       "FROM pg_index ind "\
                         "JOIN pg_class cl on (cl.oid = ind.indrelid) "\
                         "JOIN pg_class cl2 on (cl2.oid = ind.indexrelid) "\
                       "WHERE cl.relname = %s",
                       (self.table_name,))
        self.index = [l[0] for l in self.cursor.fetchall()]

        # Keep track of which module created each field
        self.field2module = {}
        if self.object_name is not None:
            self.cursor.execute('SELECT f.name, f.module '\
                           'FROM ir_model_field f '\
                             'JOIN ir_model m on (f.model=m.id) '\
                           'WHERE m.model = %s',
                           (self.object_name,)
                           )
            for line in self.cursor.fetchall():
                self.field2module[line[0]] = line[1]

    def migrate_column(self, column_name, column_type):

        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "RENAME COLUMN \"%s\" " \
                       "TO temp_change_size" % \
                       (self.table_name, column_name))
        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "ADD COLUMN \"%s\" %s" % \
                       (self.table_name, column_name, column_type))
        self.cursor.execute("UPDATE \"%s\" " \
                       "SET \"%s\" = temp_change_size::%s" % \
                       (self.table_name, column_name, column_type))
        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "DROP COLUMN temp_change_size" % \
                       (self.table_name,))
        self.update_definitions()

    def db_default(self, column_name, value):
        self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                'ALTER COLUMN "' + column_name + '" SET DEFAULT %s',
                (value,))

    def add_raw_column(self, column_name, column_type, default_fun=None,
                       field_size=None, migrate = True):
        if column_name in self.table:

            if not migrate:
                return
            base_type = column_type[0].lower()
            if not base_type == self.table[column_name]['typname']:
                logger = Logger()
                logger.notify_channel(
                    'init', LOG_WARNING,
                    'Unable to migrate column % s on table %s from %s to %s.' % \
                    (column_name, self.table_name,
                        self.table[column_name]['typname'], base_type))
            if not base_type == 'varchar':
                return
            if field_size == None:
                if self.table[column_name]['size'] > 0:
                    self.migrate_column(column_name, base_type)
                return
            elif self.table[column_name]['size'] == field_size:
                return
            elif self.table[column_name]['size'] > 0 and \
                    self.table[column_name]['size'] < field_size:
                self.migrate_column(column_name, base_type)
            else:
                logger = Logger()
                logger.notify_channel(
                    'init', LOG_WARNING,
                    'Unable to migrate column %s on table %s ' \
                            'from varchar(%s) to varchar(%s).' % \
                    (column_name, self.table_name,
                     self.table[column_name]['size'] > 0 and \
                         self.table[column_name]['size'] or "",
                     field_size))
            return

        column_type = column_type[1]
        self.cursor.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' %
                       (self.table_name, column_name, column_type))
        # Populate column with default values:
        if default_fun is not None:
            default = default_fun(self.cursor, 0, {})
            if (default is not False)  and (default is not False):
                self.cursor.execute('UPDATE "' + self.table_name + '" '\
                                    'SET "' + column_name + '" = %s',
                                    (default,))
            else:
                self.cursor.execute('UPDATE "' + self.table_name + '" '\
                                    'SET "' + column_name + '" = NULL')
        elif column_type == 'bool':
            self.cursor.execute('UPDATE "' + self.table_name + '" '\
                                'SET "' + column_name + '" = false')
        elif column_type in ('int4', 'float8'):
            self.cursor.execute('UPDATE "' + self.table_name + '" '\
                                'SET "' + column_name + '" = 0')

        self.update_definitions()

    def add_m2m(self, column_name, other_table, relation_table, rtable_from, rtable_to):
        if not table_exist(self.cursor, other_table):
            raise Exception("table %s not found"%other_table)
        rtable = table_handler(
            self.cursor, relation_table, object_name=None,
            module_name= self.module_name)
        rtable.add_raw_column(rtable_from, ('int4', 'int4'))
        rtable.add_raw_column(rtable_to, ('int4', 'int4'))
        rtable.add_fk(rtable_from, self.table_name)
        rtable.add_fk(rtable_to, other_table)
        rtable.index_action(rtable_from, 'add')
        rtable.index_action(rtable_to, 'add')

    def add_fk(self, column_name, reference, on_delete=None):
        on_delete_code = {
            'RESTRICT': 'r',
            'NO ACTION': 'a',
            'CASCADE': 'c',
            'SET NULL': 'n',
            'SET DEFAULT': 'd',
            }
        if on_delete is not None :
            on_delete = on_delete.upper()
            if on_delete not in on_delete_code:
                raise Exception('On delete action not supported !')
        else:
            on_delete = 'SET NULL'
        code = on_delete_code[on_delete]

        if self.fk_deltype.get(column_name) == code:
            # The fk exist and the delete action is ok
            return
        self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                'ADD FOREIGN KEY ("' + column_name + '") ' \
                    'REFERENCES "' + reference + '" ' \
                    'ON DELETE ' + on_delete)
        self.update_definitions()

    def index_action(self, column_name, action='add'):
        index_name = "%s_%s_index" % (self.table_name, column_name)

        if action == 'add':
            if index_name in self.index:
                return
            self.cursor.execute('CREATE INDEX "' + index_name + '" ' \
                               'ON "' + self.table_name + '" ("' + column_name + '")')
            self.update_definitions()
        elif action == 'remove':
            if self.field2module.get(column_name) != self.module_name:
                return

            self.cursor.execute("SELECT * FROM pg_indexes " \
                                "WHERE indexname = '%s'" %
                           (index_name,))
            if self.cursor.rowcount:
                self.cursor.execute('DROP INDEX "%s" ' % (index_name,))
                self.update_definitions()

    def not_null_action(self, column_name, action='add'):
        if column_name not in self.table:
            return

        if action == 'add':
            if self.table[column_name]['notnull']:
                return
            self.cursor.execute('SELECT id FROM "%s" ' \
                               'WHERE "%s" IS NULL' % \
                               (self.table_name, column_name))
            if not self.cursor.rowcount:
                self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                                   'ALTER COLUMN "' + column_name + '" ' \
                                   "SET NOT NULL")
                self.update_definitions()
            else:
                logger = Logger()
                logger.notify_channel(
                    'init',
                    LOG_WARNING,
                    'Unable to set column %s ' \
                        'of table %s not null !\n'\
                        'Try to re-run: ' \
                        'trytond.py --update=module\n' \
                        'If it doesn\'t work, update records and execute manually:\n' \
                        'ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % \
                        (column_name, self.table_name, self.table_name, column_name))
        elif action == 'remove':
            if not self.table[column_name]['notnull']:
                return
            if self.field2module.get(column_name) != self.module_name:
                return
            self.cursor.execute('ALTER TABLE "%s" ' \
                               'ALTER COLUMN "%s" DROP NOT NULL' %
                           (self.table_name, column_name))
            self.update_definitions()

    def add_constraint(self, ident, constraint):
        ident = self.table_name + "_" + ident
        if ident in self.constraint:
            # This constrain already exist
            return
        try:
            self.cursor.execute('ALTER TABLE "%s" ' \
                           'ADD CONSTRAINT "%s" %s' % \
                           (self.table_name, ident, constraint,))
        except:
            raise
            logger = Logger()
            logger.notify_channel(
                'init', LOG_WARNING,
                'unable to add \'%s\' constraint on table %s !\n' \
                'If you want to have it, you should update the records ' \
                'and execute manually:\n'\
                'ALTER table "%s" ADD CONSTRAINT "%s" %s' % \
                (constraint, self.table_name, self.table_name,
                 ident, constraint,))
        self.update_definitions()
