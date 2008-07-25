#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"View"
from trytond.osv import fields, OSV
from difflib import SequenceMatcher
import os
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING
from lxml import etree


class View(OSV):
    "View"
    _name = 'ir.ui.view'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Char('Model', required=True, select=1)
    priority = fields.Integer('Priority', required=True, select=1)
    type = fields.Selection([
       ('tree','Tree'),
       ('form','Form'),
       ('graph', 'Graph'),
       ('calendar', 'Calendar'),
       ('board', 'Board'),
       ], 'View Type', required=True, select=1)
    arch = fields.Text('View Architecture', required=True)
    inherit = fields.Many2One('ir.ui.view', 'Inherited View', select=1)
    field_childs = fields.Char('Childs Field')
    module = fields.Char('Module', readonly=True)

    def __init__(self):
        super(View, self).__init__()
        self._constraints += [
            ('check_xml', 'Invalid XML for View Architecture!', ['arch'])
        ]
        self._order.insert(0, ('priority', 'ASC'))

    def default_arch(self, cursor, user, context=None):
        return '<?xml version="1.0"?>'

    def default_priority(self, cursor, user, context=None):
        return 16

    def default_module(self, cursor, user, context=None):
        return context and context.get('module', '') or ''

    def check_xml(self, cursor, user, ids):
        "Check XML"
        views = self.browse(cursor, user, ids)
        cursor.execute('SELECT id, name, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name IN ' \
                        '(' + ','.join(['%s' for x in views]) + ')',
                        ('en_US', 'view') + tuple([x.model for x in views]))
        trans_views = {}
        for trans in cursor.dictfetchall():
            trans_views.setdefault(trans['name'], {})
            trans_views[trans['name']][trans['src']] = trans
        for view in views:
            xml = view.arch.strip()
            tree = etree.fromstring(xml)

            # validate the tree using RelaxNG
            rng_name = os.path.join(os.path.dirname(__file__),
                    (view.inherit and view.inherit.type or view.type) + '.rng')
            if hasattr(etree, 'RelaxNG'):
                validator = etree.RelaxNG(file=rng_name)
                if not validator.validate(tree):
                    logger = Logger()
                    error_log = reduce(lambda x, y: str(x) + '\n' + str(y),
                            validator.error_log.filter_from_errors())
                    logger.notify_channel('ir', LOG_ERROR,
                            'Invalid xml view:\n%s' %  (str(error_log) + '\n' + xml))
                    return False
            root_element = tree.getroottree().getroot()
            strings = self._translate_view(root_element)
            view_ids = self.search(cursor, 0, [
                ('model', '=', view.model),
                ('id', '!=', view.id),
                ])
            for view2 in self.browse(cursor, 0, view_ids):
                tree2 = etree.fromstring(view2.arch)
                root2_element = tree2.getroottree().getroot()
                strings += self._translate_view(root2_element)
            if not strings:
                continue
            for string in {}.fromkeys(strings).keys():
                done = False
                if string in trans_views.get(view.model, {}):
                    del trans_views[view.model][string]
                    continue
                for string_trans in trans_views.get(view.model, {}):
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_views[view.model][string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute('UPDATE ir_translation ' \
                            'SET src = %s, ' \
                                'fuzzy = True ' \
                            'WHERE name = %s ' \
                                'AND type = %s ' \
                                'AND src = %s',
                            (string, view.model, 'view', string_trans))
                        del trans_views[view.model][string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module)' \
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (view.model, 'en_US', 'view', string, '',
                            view.module))
            if strings:
                cursor.execute('DELETE FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND type = %s ' \
                            'AND src NOT IN ' \
                                '(' + ','.join(['%s' for x in strings]) + ')',
                        (view.model, 'view') + tuple(strings))
        return True

    def delete(self, cursor, user, ids, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids, context=context)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(View, self).delete(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(View, self).create(cursor, user, vals, context=context)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def write(self, cursor, user, ids, vals, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(View, self).write(cursor, user, ids, vals, context=context)
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def _translate_view(self, element):
        strings = []
        if element.get('string'):
            string = element.get('string')
            if string:
                strings.append(string)
        if element.get('sum'):
            string = element.get('sum')
            if string:
                strings.append(string)
        for child in element:
            strings.extend(self._translate_view(child))
        return strings

View()


class ViewShortcut(OSV):
    "View shortcut"
    _name = 'ir.ui.view_sc'
    _description = __doc__
    name = fields.Char('Shortcut Name', required=True)
    res_id = fields.Integer('Resource Ref.', required=True)
    sequence = fields.Integer('Sequence')
    user_id = fields.Many2One('res.user', 'User Ref.', required=True,
       ondelete='cascade')
    resource = fields.Char('Resource Name', required=True)

    def __init__(self):
        super(ViewShortcut, self).__init__()
        self._rpc_allowed.append('get_sc')
        self._order.insert(0, ('sequence', 'ASC'))

    def get_sc(self, cursor, user, user_id, model='ir.ui.menu', context=None):
        "Provide user's shortcuts"
        ids = self.search(cursor, user, [
            ('user_id','=',user_id),
            ('resource','=',model),
            ], context=context)
        return self.read(cursor, user, ids, ['res_id', 'name'], context=context)

    def default_resource(self, cursor, user, context=None):
        return 'ir.ui.menu'

ViewShortcut()


class ViewTreeWidth(OSV):
    "View Tree Width"
    _name = 'ir.ui.view_tree_width'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Char('Model', required=True, select=1)
    field = fields.Char('Field', required=True, select=1)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE', select=1)
    width = fields.Integer('Width')

    def __init__(self):
        super(ViewTreeWidth, self).__init__()
        self._rpc_allowed += [
            'set_width',
        ]

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids, context=context)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(ViewTreeWidth, self).delete(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ViewTreeWidth, self).create(cursor, user, vals, context=context)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(ViewTreeWidth, self).write(cursor, user, ids, vals, context=context)
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def set_width(self, cursor, user, model, fields, context=None):
        '''
        Set width for the current user on the model.
        fields is a dictionary with key: field name and value: width.
        '''
        ids = self.search(cursor, user, [
            ('user', '=', user),
            ('model', '=', model),
            ('field', 'in', fields.keys()),
            ], context=context)
        self.delete(cursor, user, ids, context=context)

        for field in fields.keys():
            self.create(cursor, user, {
                'model': model,
                'field': field,
                'user': user,
                'width': fields[field],
                }, context=context)

ViewTreeWidth()
