#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import pooler
from config import CONFIG
import sha
import time
import random

SESSION_TIMEOUT = 600 #seconds

_USER_CACHE = {}

def login(dbname, loginname, password, cache=True):
    loginname = loginname.encode('utf-8')
    password = password.encode('utf-8')
    cursor = pooler.get_db(dbname).cursor()
    password_sha = sha.new(password).hexdigest()
    cursor.execute('SELECT id FROM res_user '
        'WHERE login = %s and password = %s and active',
        (loginname, password_sha))
    res = cursor.fetchone()
    cursor.close()
    if res:
        user_id = res[0]
        if cache:
            _USER_CACHE.setdefault(dbname, {})
            timestamp = time.time()
            session = str(random.random())
            _USER_CACHE[dbname][user_id] = (timestamp, session)
            return (user_id, session)
        else:
            return user_id
    else:
        return False

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, session, reset_timeout=True):
    session = session.encode('utf-8')
    if _USER_CACHE.get(dbname, {}).has_key(user):
        timestamp, real_session = _USER_CACHE[dbname][user]
        if real_session == session \
                and abs(timestamp - time.time()) < SESSION_TIMEOUT:
            if reset_timeout:
                _USER_CACHE[dbname][user] = (time.time(), real_session)
            return True
    raise Exception('NotLogged')
