#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model
from trytond.tools import Cache, safe_eval
from trytond.modules import create_graph, get_module_list
from trytond.pyson import PYSONEncoder, CONTEXT
from lxml import etree
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import copy

def _find(tree, element):
    if element.tag == 'xpath':
        res = tree.xpath(element.get('expr'))
        if res:
            return res[0]
    return None


def _inherit_apply(src, inherit):
    tree_src = etree.fromstring(src)
    tree_inherit = etree.fromstring(inherit)
    root_inherit = tree_inherit.getroottree().getroot()
    for element2 in root_inherit:
        element = _find(tree_src, element2)
        if element is not None:
            pos = element2.get('position', 'inside')
            if pos == 'replace':
                parent = element.getparent()
                enext = element.getnext()
                if enext is not None:
                    for child in element2:
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(element2.getchildren())
                parent.remove(element)
            elif pos == 'replace_attributes':
                child = element2.getchildren()[0]
                for attr in child.attrib:
                    element.set(attr, child.get(attr))
            elif pos == 'inside':
                element.extend(element2.getchildren())
            elif pos == 'after':
                parent = element.getparent()
                enext = element.getnext()
                if enext is not None:
                    for child in element2:
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(element2.getchildren())
            elif pos == 'before':
                parent = element.getparent()
                for child in element2:
                    index = parent.index(element)
                    parent.insert(index, child)
            else:
                raise AttributeError('Unknown position ' \
                        'in inherited view %s!' % pos)
        else:
            raise AttributeError(
                    'Couldn\'t find tag (%s: %s) in parent view!' % \
                            (element2.tag, element2.get('expr')))
    return etree.tostring(tree_src, encoding='utf-8')


class ModelView(Model):
    """
    Define a model with views in Tryton.
    """
    __modules_list = None # Cache for the modules list sorted by dependency

    @staticmethod
    def _reset_modules_list():
        ModelView.__modules_list = None

    def _get_modules_list(self):
        if ModelView.__modules_list:
            return ModelView.__modules_list
        graph = create_graph(get_module_list())[0]
        ModelView.__modules_list = [x.name for x in graph] + [None]
        return ModelView.__modules_list

    _modules_list = property(fget=_get_modules_list)

    def __init__(self):
        super(ModelView, self).__init__()
        self._rpc['fields_view_get'] = False

    @Cache('modelview.fields_view_get')
    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):
        '''
        Return a view definition.

        :param cursor: the database cursor
        :param user: the user id
        :param view_id: the id of the view, if None the first one will be used
        :param view_type: the type of the view if view_id is None
        :param context: the context
        :param toolbar: if True the result will contain a toolbar key with
            keyword action definitions for the view
        :param hexmd5: if filled, the function will return True if the result
            has the same md5
        :return: a dictionary with keys:
           - model: the model name
           - arch: the xml description of the view
           - fields: a dictionary with the definition of each field in the view
           - toolbar: a dictionary with the keyword action definitions
           - md5: the check sum of the dictionary without this checksum
        '''

        if context is None:
            context = {}

        result = {'model': self._name}

        test = True
        model = True
        sql_res = False
        inherit_view_id = False
        while test:
            if view_id:
                where = (model and (" and model='%s'" % (self._name,))) or ''
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                            'inherit, model ' \
                        'FROM ir_ui_view WHERE id = %s ' + where, (view_id,))
            else:
                cursor.execute('SELECT arch, field_childs, id, type, ' \
                        'inherit, model ' \
                        'FROM ir_ui_view ' \
                        'WHERE model = %s AND type = %s' \
                        'ORDER BY inherit DESC, priority ASC, id ASC',
                        (self._name, view_type))
            sql_res = cursor.fetchone()
            if not sql_res:
                break
            test = sql_res[4]
            if test:
                inherit_view_id = sql_res[2]
            view_id = test or sql_res[2]
            model = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[3]
            result['view_id'] = view_id
            result['arch'] = sql_res[0]
            result['field_childs'] = sql_res[1] or False

            # Check if view is not from an inherited model
            if sql_res[5] != self._name:
                inherit_obj = self.pool.get(sql_res[5])
                result['arch'] = inherit_obj.fields_view_get(cursor, user,
                        result['view_id'], context=context)['arch']
                view_id = inherit_view_id

            # get all views which inherit from (ie modify) this view
            cursor.execute('SELECT arch, domain, module FROM ir_ui_view ' \
                    'WHERE (inherit = %s AND model = %s) OR ' \
                        ' (id = %s AND inherit IS NOT NULL) '
                    'ORDER BY priority ASC, id ASC',
                    (view_id, self._name, view_id))
            sql_inherit = cursor.fetchall()
            raise_p = False
            while True:
                try:
                    sql_inherit.sort(lambda x, y: \
                            cmp(self._modules_list.index(x[2] or None),
                                self._modules_list.index(y[2] or None)))
                    break
                except ValueError:
                    if raise_p:
                        raise
                    # There is perhaps a new module in the directory
                    ModelView._reset_modules_list()
                    raise_p = True
            for arch, domain, _ in sql_inherit:
                if domain:
                    if not safe_eval(domain, {'context': context}):
                        continue
                if not arch or not arch.strip():
                    continue
                result['arch'] = _inherit_apply(result['arch'], arch)

        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = self.fields_get(cursor, user, context=context)
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<form string="%s">''' % (self._description,)
                for i in res:
                    if i in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id', 'rec_name'):
                        continue
                    if res[i]['type'] not in ('one2many', 'many2many'):
                        xml += '<label name="%s"/>' % (i,)
                        xml += '<field name="%s"/>' % (i,)
                        if res[i]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"
            elif view_type == 'tree':
                field = 'id'
                if self._rec_name in self._columns:
                    field = self._rec_name
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<tree string="%s"><field name="%s"/></tree>''' \
                % (self._description, field)
            else:
                xml = ''
            result['type'] = view_type
            result['arch'] = xml
            result['field_childs'] = False
            result['view_id'] = 0

        # Update arch and compute fields from arch
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(result['arch'], parser)
        xarch, xfields = self._view_look_dom_arch(cursor, user, tree,
                result['type'], context=context)
        result['arch'] = xarch
        result['fields'] = xfields

        # Add toolbar
        if toolbar:
            action_obj = self.pool.get('ir.action.keyword')
            prints = action_obj.get_keyword(cursor, user, 'form_print',
                    (self._name, 0), context=context)
            actions = action_obj.get_keyword(cursor, user, 'form_action',
                    (self._name, 0), context=context)
            relates = action_obj.get_keyword(cursor, user, 'form_relate',
                    (self._name, 0), context=context)
            result['toolbar'] = {
                'print': prints,
                'action': actions,
                'relate': relates,
            }

        # Compute md5
        if hashlib:
            result['md5'] = hashlib.md5(str(result)).hexdigest()
        else:
            result['md5'] = md5.new(str(result)).hexdigest()
        if hexmd5 == result['md5']:
            return True
        return result

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        """
        Overload this method if you need a window title.
        which depends on the context

        :param cursor: the database cursor
        :param user: the user id
        :param value: the default header string
        :param view_type: the type of the view
        :param context: the context
        :return: the header string of the view
        """
        return value

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        fields_width = {}
        tree_root = tree.getroottree().getroot()

        if type == 'tree':
            viewtreewidth_obj = self.pool.get('ir.ui.view_tree_width')
            viewtreewidth_ids = viewtreewidth_obj.search(cursor, user, [
                ('model', '=', self._name),
                ('user', '=', user),
                ], context=context)
            for viewtreewidth in viewtreewidth_obj.browse(cursor, user,
                    viewtreewidth_ids, context=context):
                if viewtreewidth.width > 0:
                    fields_width[viewtreewidth.field] = viewtreewidth.width

        fields_def = self.__view_look_dom(cursor, user, tree_root, type,
                fields_width=fields_width, context=context)

        for field_name in fields_def.keys():
            if field_name in self._columns:
                field = self._columns[field_name]
            elif field_name in self._inherit_fields:
                field = self._inherit_fields[field_name][2]
            else:
                continue
            for depend in field.depends:
                fields_def.setdefault(depend, {'name': depend})

        if ('active' in self._columns) or ('active' in self._inherit_fields):
            fields_def.setdefault('active', {'name': 'active', 'select': "2"})

        arch = etree.tostring(tree, encoding='utf-8', pretty_print=False)
        fields2 = self.fields_get(cursor, user, fields_def.keys(), context)
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    def __view_look_dom(self, cursor, user, element, type, fields_width=None,
            context=None):
        translation_obj = self.pool.get('ir.translation')

        if fields_width is None:
            fields_width = {}
        if context is None:
            context = {}
        result = False
        fields_attrs = {}
        childs = True

        if element.tag in ('field', 'label', 'separator', 'group'):
            for attr in ('name', 'icon'):
                if element.get(attr):
                    attrs = {}
                    try:
                        if element.get(attr) in self._columns:
                            field = self._columns[element.get(attr)]
                        else:
                            field = self._inherit_fields[element.get(
                                attr)][2]
                        if hasattr(field, 'model_name'):
                            relation = field.model_name
                        else:
                            relation = field.get_target(self.pool)._name
                    except:
                        relation = False
                    if relation and element.tag == 'field':
                        childs = False
                        views = {}
                        for field in element:
                            if field.tag in ('form', 'tree', 'graph'):
                                field2 = copy.copy(field)

                                def _translate_field(field):
                                    if field.get('string'):
                                        trans = translation_obj._get_source(
                                                cursor, self._name, 'view',
                                                context['language'],
                                                field.get('string'))
                                        if trans:
                                            field.set('string', trans)
                                    if field.get('sum'):
                                        trans = translation_obj._get_source(
                                                cursor, self._name, 'view',
                                                context['language'],
                                                field.get('sum'))
                                        if trans:
                                            field.set('sum', trans)
                                    for field_child in field:
                                        _translate_field(field_child)
                                if 'language' in context:
                                    _translate_field(field2)

                                relation_obj = self.pool.get(relation)
                                if hasattr(relation_obj, '_view_look_dom_arch'):
                                    xarch, xfields = \
                                            relation_obj._view_look_dom_arch(
                                                    cursor, user,
                                                    field2, field.tag,
                                                    context=context)
                                    views[field.tag] = {
                                        'arch': xarch,
                                        'fields': xfields
                                    }
                                element.remove(field)
                        attrs = {'views': views}
                    fields_attrs[element.get(attr)] = attrs
            if element.get('name') in fields_width:
                element.set('width', str(fields_width[element.get('name')]))

        # convert attributes into pyson
        encoder = PYSONEncoder()
        for attr in ('states', 'domain', 'context', 'digits', 'add_remove',
                'spell', 'colors'):
            if element.get(attr):
                element.set(attr, encoder.encode(safe_eval(element.get(attr),
                    CONTEXT)))

        # translate view
        if ('language' in context) and not result:
            for attr in ('string', 'sum', 'confirm', 'help'):
                if element.get(attr):
                    trans = translation_obj._get_source(cursor,
                            self._name, 'view', context['language'],
                            element.get(attr))
                    if trans:
                        element.set(attr, trans)

        # Set header string
        if element.tag in ('form', 'tree', 'graph'):
            element.set('string', self.view_header_get(cursor, user,
                element.get('string') or '', view_type=element.tag,
                context=context))

        if element.tag == 'tree' and element.get('sequence'):
            fields_attrs.setdefault(element.get('sequence'), {})

        if childs:
            for field in element:
                fields_attrs.update(self.__view_look_dom(cursor, user, field,
                    type, fields_width=fields_width, context=context))
        return fields_attrs
