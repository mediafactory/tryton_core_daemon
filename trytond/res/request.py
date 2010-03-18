#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Request"
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, In, If, Not, Equal
import time
import datetime

_STATES = [
    ('draft', 'Draft'),
    ('waiting', 'Waiting'),
    ('chatting', 'Chatting'),
    ('closed', 'Closed'),
]

_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Normal'),
    ('2', 'High'),
]

_READONLY = If(In(Eval('state'), ['waiting', 'closed']),
        True,
        If(Equal(Eval('state'), 'chatting'),
            Not(Equal(Eval('act_from'), Eval('_user'))),
            False))

class Request(ModelSQL, ModelView):
    "Request"
    _name = 'res.request'
    _description = __doc__
    name = fields.Char('Subject', states={
        'readonly': _READONLY,
       }, required=True)
    active = fields.Boolean('Active')
    priority = fields.Selection(_PRIORITIES, 'Priority', states={
           'readonly': _READONLY,
           }, required=True, order_field='priority')
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True)
    act_to = fields.Many2One('res.user', 'To', required=True,
            domain=[('active', '=', True)],
            states={
                'readonly': _READONLY,
                })
    body = fields.Text('Body', states={
       'readonly': _READONLY,
       })
    date_sent = fields.DateTime('Date', readonly=True)
    trigger_date = fields.DateTime('Trigger Date', states={
       'readonly': _READONLY,
       })
    references = fields.One2Many('res.request.reference', 'request',
            'References', states={
                'readonly': If(Equal(Eval('state'), 'closed'),
                    True,
                    Not(Equal(Eval('act_from', 0), Eval('_user', 0)))),
            })
    number_references = fields.Function(fields.Integer('Number of References',
        on_change_with=['references']), 'get_number_references')
    state = fields.Selection(_STATES, 'State', required=True, readonly=True)
    history = fields.One2Many('res.request.history', 'request',
           'History', readonly=True)

    def default_act_from(self, cursor, user, context=None):
        return int(user)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_active(self, cursor, user, context=None):
        return True

    def default_priority(self, cursor, user, context=None):
        return '1'

    def __init__(self):
        super(Request, self).__init__()
        self._rpc.update({
            'request_send': True,
            'request_reply': True,
            'request_close': True,
            'request_get': False,
        })
        self._order.insert(0, ('priority', 'DESC'))
        self._order.insert(1, ('trigger_date', 'DESC'))
        self._order.insert(2, ('create_date', 'DESC'))

    def on_change_with_number_references(self, cursor, user, vals,
            context=None):
        if vals.get('references'):
            return len(vals['references'])
        return 0

    def get_number_references(self, cursor, user, ids, name, context=None):
        res = {}
        for request in self.browse(cursor, user, ids, context=context):
            if request.references:
                res[request.id] = len(request.references)
            else:
                res[request.id] = 0
        return res

    def request_send(self, cursor, user, ids, context=None):
        request_history_obj = self.pool.get('res.request.history')
        for request in self.browse(cursor, user, ids, context=context):
            values = {
                'request': request.id,
                'act_from': request.act_from.id,
                'act_to': request.act_to.id,
                'body': request.body,
                'state': request.state,
                'subject': request.name,
                'number_references': request.number_references,
                'priority': request.priority,
            }
            if values['body'] and len(values['body']) > 128:
                values['name'] = values['body'][:125] + '...'
            else:
                values['name'] = values['body'] or '/'
            request_history_obj.create(cursor, user, values, context=context)
        self.write(cursor, user, ids, {
            'state': 'waiting',
            'date_send': datetime.datetime.now(),
            }, context=context)
        return True

    def request_reply(self, cursor, user, ids, context=None):
        for request in self.browse(cursor, user, ids, context=context):
            self.write(cursor, user, request.id, {
                'state': 'chatting',
                'act_from': user,
                'act_to': request.act_from.id,
                'trigger_date': False,
                'body': '',
                }, context=context)
        return True

    def request_close(self, cursor, user, ids, context=None):
        self.write(cursor, user, ids, {'state': 'closed', 'active': False})
        return True

    def request_get(self, cursor, user):
        ids = self.search(cursor, user, [
            ('act_to', '=', user),
            ['OR',
                ('trigger_date', '<=', datetime.datetime.now()),
                ('trigger_date', '=', False),
            ],
            ('active', '=', True),
            ])
        ids2 = self.search(cursor, user, [
            ('act_from', '=', user),
            ('act_to', '!=', user),
            ('state', '!=', 'draft'),
            ('active', '=', True),
            ])
        return (ids, ids2)

Request()


class RequestLink(ModelSQL, ModelView):
    "Request link"
    _name = 'res.request.link'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Selection('models_get', 'Model', required=True)
    priority = fields.Integer('Priority')

    def __init__(self):
        super(RequestLink, self).__init__()
        self._order.insert(0, ('priority', 'ASC'))

    def default_priority(self, cursor, user, context=None):
        return 5

    def models_get(self, cursor, user, context=None):
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search(cursor, user, [], context=context)
        res = []
        for model in model_obj.browse(cursor, user, model_ids, context=context):
            res.append((model.model, model.name))
        return res

RequestLink()


class RequestHistory(ModelSQL, ModelView):
    "Request history"
    _name = 'res.request.history'
    _description = __doc__
    name = fields.Char('Summary', required=True, readonly=True)
    request = fields.Many2One('res.request', 'Request', required=True,
       ondelete='CASCADE', select=1, readonly=True)
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True)
    act_to = fields.Many2One('res.user', 'To', required=True, readonly=True)
    body = fields.Text('Body', readonly=True)
    date_sent = fields.DateTime('Date sent', required=True, readonly=True)
    state = fields.Selection(_STATES, 'State', required=True, readonly=True)
    subject = fields.Char('Subject', required=True, readonly=True)
    number_references = fields.Integer('References', readonly=True)
    priority = fields.Selection(_PRIORITIES, 'Priority', required=True,
            readonly=True)

    def __init__(self):
        super(RequestHistory, self).__init__()
        self._order.insert(0, ('date_sent', 'DESC'))

    def default_name(self, cursor, user, context=None):
        return 'No Name'

    def default_act_from(self, cursor, user, context=None):
        return int(user)

    def default_act_to(self, cursor, user, context=None):
        return int(user)

    def default_date_sent(self, cursor, user, context=None):
        return datetime.datetime.now()

    def write(self, cursor, user, ids, vals, context=None):
        raise

RequestHistory()


class RequestReference(ModelSQL, ModelView):
    "Request Reference"
    _name = 'res.request.reference'
    _description = __doc__
    _rec_name = 'reference'

    request = fields.Many2One('res.request', 'Request', required=True,
            ondelete="CASCADE", select=1)
    reference = fields.Reference('Reference', selection='links_get',
            required=True)

    def links_get(self, cursor, user, context=None):
        request_link_obj = self.pool.get('res.request.link')
        ids = request_link_obj.search(cursor, user, [], context=context)
        request_links = request_link_obj.browse(cursor, user, ids,
                context=context)
        return [(x.model, x.name) for x in request_links]

RequestReference()
