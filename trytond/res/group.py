#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Group"
from itertools import chain
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction


class MenuMany2Many(fields.Many2Many):

    def get(self, ids, model, name, values=None):
        menu_obj = self.get_target(model.pool)
        res = super(MenuMany2Many, self).get(ids, model, name,
                values=values)
        menu_ids = list(set(chain(*res.values())))
        test_ids = []
        for i in range(0, len(menu_ids), Transaction().cursor.IN_MAX):
            sub_ids = menu_ids[i:i + Transaction().cursor.IN_MAX]
            test_ids.append(menu_obj.search([
                ('id', 'in', sub_ids),
                ]))
        menu_ids = set(chain(*test_ids))
        for ids in res.itervalues():
            for id_ in ids[:]:
                if id_ not in menu_ids:
                    ids.remove(id_)
        return res

class Group(ModelSQL, ModelView):
    "Group"
    _name = "res.group"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    model_access = fields.One2Many('ir.model.access', 'group',
       'Access Model')
    rule_groups = fields.Many2Many('ir.rule.group-res.group',
       'group_id', 'rule_group_id', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    menu_access = MenuMany2Many('ir.ui.menu-res.group',
       'gid', 'menu_id', 'Access Menu')

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'unique (name)', 'The name of the group must be unique!')
        ]

    def create(self, vals):
        res = super(Group, self).create(vals)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

    def write(self, ids, vals):
        res = super(Group, self).write(ids, vals)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

    def delete(self, ids):
        res = super(Group, self).delete(ids)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

Group()
