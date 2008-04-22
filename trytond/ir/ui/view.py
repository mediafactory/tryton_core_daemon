"View"
from trytond.osv import fields, OSV
from xml import dom
from difflib import SequenceMatcher
import os
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING


class View(OSV):
    "View"
    _name = 'ir.ui.view'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Char('Model', size=None, required=True)
    priority = fields.Integer('Priority', required=True)
    type = fields.Selection([
       ('tree','Tree'),
       ('form','Form'),
       ('graph', 'Graph'),
       ('calendar', 'Calendar'),
       ('board', 'Board'),
       ], 'View Type', required=True)
    arch = fields.Text('View Architecture', required=True)
    inherit = fields.Many2One('ir.ui.view', 'Inherited View')
    field_childs = fields.Char('Childs Field',size=64)
    module = fields.Char('Module', size=128, readonly=True)
    _order = "priority"

    def __init__(self):
        super(View, self).__init__()
        self._constraints += [
            ('check_xml', 'Invalid XML for View Architecture!', ['arch'])
        ]

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
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('model', '=', self._name),
            ('db_id', 'in', ids),
            ])
        for view in views:
            logger = Logger()
            try:
                from Ft.Xml.Domlette import ValidatingReader
                xml = '<?xml version="1.0"?>\n<!DOCTYPE %s SYSTEM "file://%s/%s.dtd">\n'\
                        % (view.inherit and 'data' or view.type,
                                os.path.dirname(__file__),
                                view.inherit and view.inherit.type or view.type)
                xml += view.arch.strip()
                try:
                    ValidatingReader.parseString(xml)
                except Exception, exception:
                    logger.notify_channel('ir', LOG_ERROR,
                            'Invalid xml view: %s' % (str(exception)))
                    return False
            except:
                logger.notify_channel('ir', LOG_WARNING,
                'Could not import Ft.Xml.Domlette, please install 4Suite ' \
                        'to have xml validation')
            try:
                document = dom.minidom.parseString(view.arch)
            except:
                return False
            strings = self._translate_view(document.documentElement)
            view_ids = self.search(cursor, 0, [
                ('model', '=', view.model),
                ('id', '!=', view.id),
                ])
            for view2 in self.browse(cursor, 0, view_ids):
                document = dom.minidom.parseString(view2.arch)
                strings += self._translate_view(document.documentElement)
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
            cursor.execute('DELETE FROM ir_translation ' \
                    'WHERE name = %s ' \
                        'AND type = %s ' \
                        'AND src NOT IN ' \
                            '(' + ','.join(['%s' for x in strings]) + ')',
                    (view.model, 'view') + tuple(strings))
        return True

    def unlink(self, cursor, user, ids, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids, context=context)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        res = super(View, self).unlink(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(View, self).create(cursor, user, vals, context=context)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get()
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
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        res = super(View, self).write(cursor, user, ids, vals, context=context)
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        return res

    def _translate_view(self, document):
        strings = []
        if document.hasAttribute('string'):
            string = document.getAttribute('string')
            if string:
                strings.append(string.encode('utf-8'))
        if document.hasAttribute('sum'):
            string = document.getAttribute('sum')
            if string:
                strings.append(string.encode('utf-8'))
        for child in [x for x in document.childNodes \
                if (x.nodeType == x.ELEMENT_NODE)]:
            strings.extend(self._translate_view(child))
        return strings

View()


class ViewShortcut(OSV):
    "View shortcut"
    _name = 'ir.ui.view_sc'
    _description = __doc__
    name = fields.Char('Shortcut Name', size=64, required=True)
    res_id = fields.Integer('Resource Ref.', required=True)
    sequence = fields.Integer('Sequence')
    user_id = fields.Many2One('res.user', 'User Ref.', required=True,
       ondelete='cascade')
    resource = fields.Char('Resource Name', size=64, required=True)
    _order = 'sequence'

    def __init__(self):
        super(ViewShortcut, self).__init__()
        self._rpc_allowed.append('get_sc')

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
