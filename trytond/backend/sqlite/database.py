#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import CONFIG
from trytond.session import Session
import logging
import os
import re
import mx.DateTime
from decimal import Decimal

_FIX_ROWCOUNT = False
try:
    from pysqlite2 import dbapi2 as sqlite
    from pysqlite2.dbapi2 import IntegrityError as DatabaseIntegrityError
    from pysqlite2.dbapi2 import OperationalError as DatabaseOperationalError
    #pysqlite2 < 2.5 doesn't return correct rowcount
    _FIX_ROWCOUNT = sqlite.version_info < (2 , 5, 0)
except ImportError:
    import sqlite3 as sqlite
    from sqlite3 import IntegrityError as DatabaseIntegrityError
    from sqlite3 import OperationalError as DatabaseOperationalError

def date_trunc(_type, date):
    if _type == 'second':
        return date
    try:
        date = mx.DateTime.strptime(date, '%Y-%m-%d %H:%M:%S')
    except:
        return None
    if _type == 'year':
        return "%i-01-01 00:00:00" % dt.year
    elif _type == 'month':
        return "%i-%02i-01 00:00:00" % (dt.year, dt.month)
    elif _type == 'day':
        return "%i-%02i-%02i 00:00:00" % (dt.year, dt.month, dt.day)

def now():
    return mx.DateTime.now().strftime('%Y-%m-%d %H:%M:%S')


class Database(DatabaseInterface):

    _memory_database = None
    _memory_created = False
    _conn = None

    def __new__(cls, database_name=':memory:'):
        if database_name in (':memory:', 'memory') \
                and cls._memory_database:
            return cls._memory_database
        return DatabaseInterface.__new__(cls, database_name=database_name)

    def __init__(self, database_name=':memory:'):
        super(Database, self).__init__(database_name=database_name)
        if database_name in (':memory:', 'memory'):
            Database._memory_database = self

    def connect(self):
        if self._conn is not None:
            return self
        if self.database_name in (':memory:', 'memory'):
            path = ':memory:'
            if self.database_name == 'memory' \
                    and not self._memory_created:
                raise Exception('Database doesn\'t exist!')
        else:
            path = os.path.join(CONFIG['data_path'],
                    self.database_name + '.sqlite')
            if not os.path.isfile(path):
                raise Exception('Database doesn\'t exist!')
        self._conn = sqlite.connect(path, detect_types=sqlite.PARSE_DECLTYPES)
        self._conn.create_function('date_trunc', 2, date_trunc)
        self._conn.create_function('now', 0, now)
        return self

    def cursor(self, autocommit=False):
        if self._conn is None:
            self.connect()
        if autocommit:
            self._conn.isolation_level = None
        else:
            self._conn.isolation_level = 'IMMEDIATE'
        return Cursor(self._conn, self.database_name)

    def close(self):
        if self.database_name in (':memory:', 'memory'):
            return
        if self._conn is None:
            return
        self._conn = None

    def create(self, cursor, database_name):
        if database_name in (':memory:', 'memory'):
            path = ':memory:'
            if database_name == 'memory':
                self._memory_created = True
        else:
            if os.sep in database_name:
                return
            path = os.path.join(CONFIG['data_path'],
                    database_name + '.sqlite')
        conn = sqlite.connect(path)
        cursor = conn.cursor()
        cursor.close()
        conn.close()

    def drop(self, cursor, database_name):
        if database_name in (':memory', 'memory'):
            self._conn = None
            return
        if os.sep in database_name:
            return
        os.remove(os.path.join(CONFIG['data_path'],
            database_name + '.sqlite'))

    @staticmethod
    def dump(database_name):
        if database_name in (':memory:', 'memory'):
            raise Exception('Unable to dump memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(CONFIG['data_path'],
                database_name + '.sqlite')
        file_p = file(path)
        data = file_p.read()
        file_p.close()
        return data

    @staticmethod
    def restore(database_name, data):
        if database_name in (':memory:', 'memory'):
            raise Exception('Unable to restore memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(CONFIG['data_path'],
                database_name + '.sqlite')
        if os.path.isfile(path):
            raise Exception('Database already exists!')
        file_p = file(path, 'wb')
        file_p.write(data)
        file_p.close()

    @staticmethod
    def list(cursor):
        res = []
        for file in os.listdir(CONFIG['data_path']) + ['memory']:
            if file.endswith('.sqlite') or file == 'memory':
                if file == 'memory':
                    db_name = ':memory:'
                else:
                    db_name = file[:-7]
                try:
                    database = Database(db_name)
                except:
                    continue
                cursor2 = database.cursor()
                if cursor2.test():
                    res.append(db_name)
                cursor2.close()
        return res

    @staticmethod
    def init(cursor):
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        for line in file(sql_file).read().split(';'):
            if (len(line)>0) and (not line.isspace()):
                cursor.execute(line)

        for i in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.join(os.path.dirname(__file__), '..', '..')
            tryton_file = os.path.join(root_path, i, '__tryton__.py')
            mod_path = os.path.join(root_path, i)
            info = eval(file(tryton_file).read())
            active = info.get('active', False)
            if active:
                state = 'to install'
            else:
                state = 'uninstalled'
            cursor.execute('INSERT INTO ir_module_module ' \
                    '(create_uid, create_date, author, website, name, ' \
                    'shortdesc, description, state) ' \
                    'VALUES (%s, now(), %s, %s, %s, %s, %s, %s)',
                    (0, info.get('author', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), state))
            cursor.execute('SELECT last_insert_rowid()')
            module_id = cursor.fetchone()[0]
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(create_uid, create_date, module, name) ' \
                        'VALUES (%s, now(), %s, %s) ',
                        (0, module_id, dependency))


class _Cursor(sqlite.Cursor):

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


class Cursor(CursorInterface):
    IN_MAX = 500

    def __init__(self, conn, database_name):
        self._conn = conn
        self.database_name = database_name
        self.dbname = self.database_name #XXX to remove
        self.cursor = conn.cursor(_Cursor)

    def __getattr__(self, name):
        if _FIX_ROWCOUNT and name == 'rowcount':
            return -1
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        sql = sql.replace('?', '??')
        quote_separation = re.compile(r"(.*?)('.*?')", re.DOTALL)
        notQuoted_quoted = quote_separation.findall(sql+"''")
        replaced = [nq\
                .replace('%s', '?')\
                .replace('ilike', 'like') \
                + q for (nq, q) in notQuoted_quoted]
        sql = "".join(replaced)[:-2]
        try:
            if params:
                res = self.cursor.execute(sql, params)
            else:
                res = self.cursor.execute(sql)
        except:
            raise
        return res

    def close(self, close=False):
        self.cursor.close()
        self.rollback()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def test(self):
        self.cursor.execute("SELECT name " \
                "FROM sqlite_master " \
                "WHERE type = 'table' AND name in (" \
                "'ir_model', "
                "'ir_model_field', "
                "'ir_ui_view', "
                "'ir_ui_menu', "
                "'res_user', "
                "'res_group', "
                "'wkf', "
                "'wkf_activity', "
                "'wkf_transition', "
                "'wkf_instance', "
                "'wkf_workitem', "
                "'wkf_witm_trans', "
                "'ir_module_module', "
                "'ir_module_module_dependency, '"
                "'ir_translation, '"
                "'ir_lang'"
                ")")
        return len(self.cursor.fetchall()) != 0

    def lastid(self):
        self.cursor.execute('SELECT last_insert_rowid()')
        return self.cursor.fetchone()[0]

    def has_lock(self):
        return False

sqlite.register_converter('NUMERIC', lambda val: Decimal(str(val)))
sqlite.register_adapter(Decimal, lambda val: float(val))
sqlite.register_adapter(Session, lambda val: int(val))
