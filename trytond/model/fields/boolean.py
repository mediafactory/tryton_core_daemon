#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Boolean(Field):
    '''
    Define a boolean field (``True`` or ``False``).
    '''
    _type = 'boolean'

    def __init__(self, string='', help='', readonly=False, domain=None,
            states=None, priority=0, change_default=False, select=0,
            on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None):
        super(Boolean, self).__init__(string=string, help=help, required=False,
                readonly=readonly, domain=domain, states=states,
                priority=priority, change_default=change_default,
                select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)

    __init__.__doc__ = Field.__init__.__doc__
