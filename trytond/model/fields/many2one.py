#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Many2One(Field):
    _type = 'many2one'

    def __init__(self, model_name, string='', left=None, right=None,
            ondelete='SET NULL', datetime_field=None, **args):
        if datetime_field:
            if ('depends' in args) and args['depends']:
                args['depends'].append(datetime_field)
            else:
                args['depends'] = [datetime_field]
        super(Many2One, self).__init__(string=string, **args)
        self.model_name = model_name
        self.left = left
        self.right = right
        self.ondelete = ondelete
        self.datetime_field = datetime_field
