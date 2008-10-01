#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"""
SPEC: Execute "model.function(*eval(args))" periodically
   date        : date to execute the job or NULL if directly
   delete_after: delete the ir.cron entry after execution
   interval_*  : period
   max_repeat  : number of execution or NULL if endlessly
"""

from mx import DateTime
from trytond import pooler
from trytond.osv import fields, OSV
import datetime
import traceback
import sys

_INTERVALTYPES = {
    'work_days': lambda interval: DateTime.RelativeDateTime(days=interval),
    'days': lambda interval: DateTime.RelativeDateTime(days=interval),
    'hours': lambda interval: DateTime.RelativeDateTime(hours=interval),
    'weeks': lambda interval: DateTime.RelativeDateTime(days=7*interval),
    'months': lambda interval: DateTime.RelativeDateTime(months=interval),
    'minutes': lambda interval: DateTime.RelativeDateTime(minutes=interval),
}

class Cron(OSV):
    "Cron"
    _name = "ir.cron"
    _description = __doc__
    name = fields.Char('Name', required=True)
    user = fields.Many2One('res.user', 'Execution User', required=True,
                           help="The user used to execute this action")
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
    active = fields.Boolean('Active', select=1)
    interval_number = fields.Integer('Interval Number')
    interval_type = fields.Selection( [
       ('minutes', 'Minutes'),
       ('hours', 'Hours'),
       ('work_days', 'Work Days'),
       ('days', 'Days'),
       ('weeks', 'Weeks'),
       ('months', 'Months'),
       ], 'Interval Unit')
    numbercall = fields.Integer('Number of calls', select=1,
       help='Number of time the function is called,\n' \
               'a negative number indicates that the function ' \
               'will always be called')
    doall = fields.Boolean('Repeat missed')
    nextcall = fields.DateTime('Next call date', required=True,
            select=1)
    model = fields.Char('Model')
    function = fields.Char('Function')
    args = fields.Text('Arguments')
    priority = fields.Integer('Priority',
       help='0=Very Urgent\n10=Not urgent')
    running = fields.Boolean('Running', readonly=True, select=1)

    def __init__(self):
        super(Cron, self).__init__()
        self._error_messages.update({
            'request_title': 'Scheduled action failed',
            'request_body': "The following action failed to execute "
                            "properly: \"%s\" \n See the first attachment for "
                            "details.\n Traceback: \n\n%s\n"
            })

    def default_nextcall(self, cursor, user, context=None):
        return datetime.datetime.now()

    def default_priority(self, cursor, user, context=None):
        return 5

    def default_user(self, cursor, user, context=None):
        return user

    def default_interval_number(self, cursor, user, context=None):
        return 1

    def default_interval_type(self, cursor, user, context=None):
        return 'months'

    def default_numbercall(self, cursor, user, context=None):
        return 1

    def default_active(self, cursor, user, context=None):
        return True

    def default_doall(self, cursor, user, context=None):
        return True

    def default_running(self, cursor, user, context=None):
        return False

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def _callback(self, cursor, user, job_id, model, func, args):
        args = (args or []) and eval(args)
        obj = self.pool.get(model)
        if obj and hasattr(obj, func):
            fct = getattr(obj, func)
            fct(cursor, user, *args)

    def pool_jobs(self, db_name):
        now = DateTime.now()
        cursor = pooler.get_db(db_name).cursor()
        cursor.execute('SELECT * FROM ir_cron ' \
                'WHERE numbercall <> 0 ' \
                    'AND active ' \
                    'AND nextcall <= now() ' \
                    'AND NOT running ' \
                    'ORDER BY priority')
        crons = cursor.dictfetchall()

        for cron in crons:
            try:
                cursor.execute('UPDATE ir_cron SET running = True ' \
                        'WHERE id = %s' % cron['id'])
                nextcall = DateTime.strptime(str(cron['nextcall']),
                        '%Y-%m-%d %H:%M:%S')
                numbercall = cron['numbercall']
                done = False
                while nextcall < now and numbercall:
                    if numbercall > 0:
                        numbercall -= 1
                    if not done or cron['doall']:
                            self._callback(cursor, cron['user'], cron['id'], cron['model'],
                                           cron['function'], cron['args'])
                    if numbercall:
                        nextcall += _INTERVALTYPES[cron['interval_type']](
                                cron['interval_number'])
                    done = True
                addsql = ''
                if not numbercall:
                    addsql = ', active=False'
                cursor.execute("UPDATE ir_cron SET nextcall = %s, " \
                            "running = False, numbercall = %s" + addsql + " " \
                            "WHERE id = %s",
                            (nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                                numbercall, cron['id']))
                cursor.commit()

            except Exception, error:
                cursor.rollback()

                tb_s = ''
                for line in traceback.format_exception(*sys.exc_info()):
                    try:
                        line = line.encode('utf-8', 'ignore')
                    except:
                        continue
                    tb_s += line

                request_obj = self.pool.get('res.request')
                try:
                    request_obj.create(
                        cursor, cron['user'],
                        {'name': self.raise_user_error(
                                cursor, 'request_title', raise_exception=False),
                         'priority': '2',
                         'act_from': cron['user'],
                         'act_to': cron['request_user'],
                         'body': self.raise_user_error(
                                cursor, 'request_body', (cron['name'], tb_s),
                                raise_exception=False),
                         'date_sent': now,
                         'references': [
                                ('create',{'reference': "ir.cron,%s"%cron['id']})],
                         'state': 'waiting',
                         'trigger_date': now,
                         })
                    cursor.commit()
                except:
                    cursor.rollback()
        cursor.close()
Cron()
