#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Test for Tree"
from trytond.model import ModelView, ModelSQL, fields


class MPTT(ModelSQL, ModelView):
    'Modified Preorder Tree Traversal'
    _name = 'test.mptt'
    _description = __doc__
    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', required=True)
    parent = fields.Many2One('test.mptt', "Parent", select=True,
            left="left", right="right")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    childs = fields.One2Many('test.mptt', 'parent', 'Children')
    active = fields.Boolean('Active')

    def __init__(self):
        super(MPTT, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._constraints += [
            ('check_recursion', 'recursive_mptt'),
        ]
        self._error_messages.update({
            'recursive_mptt': 'You can not create recursive Tree!',
        })

    def default_active(self):
        return True

    def default_left(self):
        return 0

    def default_right(self):
        return 0

MPTT()
