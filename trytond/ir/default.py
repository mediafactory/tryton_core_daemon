#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Default"
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal
import mx.DateTime
import datetime


class Default(ModelSQL, ModelView):
    "Default"
    _name = 'ir.default'
    _description = __doc__
    _rec_name = 'value'
    model = fields.Many2One('ir.model', 'Model', required=True,
       ondelete='cascade')
    field = fields.Many2One('ir.model.field', 'Field', required=True,
       ondelete='cascade')
    value = fields.Text('Value')
    clause = fields.Text('Clause')
    user = fields.Many2One('res.user', 'User', ondelete='cascade')

    def __init__(self):
        super(Default, self).__init__()
        self._rpc.update({
            'get_default': False,
            'set_default': True,
        })

    def get_default(self, cursor, user, model, clause, context=None):
        res = {}
        test_user = user
        test_clause = clause
        default_ids = []
        while True:
            default_ids += self.search(cursor, user, [
                ('model.model', '=', model),
                ('clause', '=', test_clause),
                ('user', '=', test_user),
                ], context=context)
            if test_user:
                test_user = False
                continue
            if test_clause:
                test_clause = False
                continue
            break
        ctx = {}
        ctx['Decimal'] = Decimal
        for default in self.browse(cursor, user, default_ids, context=context):
            if default.field.name not in res:
                if default.field.ttype in ('reference', 'char', 'sha', 'text',
                        'time', 'selection'):
                    res[default.field.name] = default.value
                elif default.field.ttype in ('integer', 'biginteger'):
                    res[default.field.name] = int(default.value)
                elif default.field.ttype == 'float':
                    res[default.field.name] = float(default.value)
                elif default.field.ttype == 'numeric':
                    res[default.field.name] = Decimal(default.value)
                elif default.field.ttype == 'date':
                    date = mx.DateTime.strptime(default.value, '%Y-%m-%d')
                    res[default.field.name] = datetime.date(date.year,
                            date.month, date.day)
                elif default.field.ttype == 'datetime':
                    date = mx.DateTime.strptime(default.value,
                            '%Y-%m-%d %H:%M:%S')
                    res[default.field.name] = datetime.datetime(date.year,
                            date.month, date.day, date.hour, date.minute,
                            int(date.second))
                else:
                    res[default.field.name] = eval(default.value)
        return res

    def set_default(self, cursor, user, model, field, clause, value,
            user_default, context=None):
        model_obj = self.pool.get('ir.model')
        field_obj = self.pool.get('ir.model.field')
        model_id = model_obj.search(cursor, user, [
            ('model', '=', model),
            ], context=context)[0]
        field_id = field_obj.search(cursor, user, [
            ('name', '=', field),
            ], context=context)[0]
        default_ids = self.search(cursor, user, [
            ('model', '=', model_id),
            ('field', '=', field_id),
            ('clause', '=', clause),
            ('user', '=', user_default),
            ], context=context)
        if default_ids:
            self.delete(cursor, user, default_ids, context=context)
        self.create(cursor, user, {
            'model': model_id,
            'field': field_id,
            'value': str(value),
            'clause': clause,
            'user': user_default,
            }, context=context)

Default()
