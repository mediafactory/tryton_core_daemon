#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"model"
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import Cache
from trytond.report import Report
from trytond.wizard import Wizard
import time
import base64


class Model(ModelSQL, ModelView):
    "Model"
    _name = 'ir.model'
    _description = __doc__
    name = fields.Char('Model Description', translate=True)
    model = fields.Char('Model Name', required=True)
    info = fields.Text('Information')
    module = fields.Char('Module',
       help="Module in which this model is defined")
    fields = fields.One2Many('ir.model.field', 'model', 'Fields',
       required=True)

    def __init__(self):
        super(Model, self).__init__()
        self._sql_constraints += [
            ('model_uniq', 'UNIQUE(model)',
                'The model must be unique!'),
        ]
        self._order.insert(0, ('model', 'ASC'))

Model()

class ModelField(ModelSQL, ModelView):
    "Model field"
    _name = 'ir.model.field'
    _description = __doc__
    name = fields.Char('Name', required=True)
    relation = fields.Char('Model Relation')
    model = fields.Many2One('ir.model', 'Model', required=True,
       select=1, ondelete='cascade')
    field_description = fields.Char('Field Description', translate=True)
    ttype = fields.Char('Field Type')
    groups = fields.Many2Many('res.group', 'ir_model_field_group_rel',
       'field_id', 'group_id', 'Groups')
    help = fields.Text('Help', translate=True)
    module = fields.Char('Module',
       help="Module in which this field is defined")

    def __init__(self):
        super(ModelField, self).__init__()
        self._sql_constraints += [
            ('name_model_uniq', 'UNIQUE(name, model)',
                'The field name in model must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def default_name(self, cursor, user, context=None):
        return 'No Name'

    def default_field_description(self, cursor, user, context=None):
        return 'No description available'

    def read(self, cursor, user, ids, fields_names=None, context=None):
        translation_obj = self.pool.get('ir.translation')

        if context is None:
            context = {}
        to_delete = []
        if context.get('language'):
            if fields_names is None:
                fields_names = self._columns.keys()

            if 'field_description' in fields_names \
                    or 'help' in fields_names:
                if 'model' not in fields_names:
                    fields_names.append('model')
                    to_delete.append('model')
                if 'name' not in fields_names:
                    fields_names.append('name')
                    to_delete.append('name')

        res = super(ModelField, self).read(cursor, user, ids,
                fields_names=fields_names, context=context)

        if context.get('language') \
                and ('field_description' in fields_names \
                or 'help' in fields_names):
            model_ids = set()
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_ids.add(rec['model'][0])
                else:
                    model_ids.add(rec['model'])
            model_ids = list(model_ids)
            cursor.execute('SELECT id, model FROM ir_model WHERE id IN ' \
                    '(' + ','.join(['%s' for x in model_ids]) + ')', model_ids)
            id2model = dict(cursor.fetchall())

            trans_args = []
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_id = rec['model'][0]
                else:
                    model_id = rec['model']
                if 'field_description' in fields_names:
                    trans_args.append(
                            (id2model[model_id] + ',' + rec['name'],
                                'field', context['language'], None))
                if 'help' in fields_names:
                    trans_args.append((id2model[model_id] + ',' + rec['name'],
                            'help', context['language'], None))
            translation_obj._get_sources(cursor, trans_args)
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_id = rec['model'][0]
                else:
                    model_id = rec['model']
                if 'field_description' in fields_names:
                    res_trans = translation_obj._get_source(cursor,
                            id2model[model_id] + ',' + rec['name'],
                                'field', context['language'])
                    if res_trans:
                        rec['field_description'] = res_trans
                if 'help' in fields_names:
                    res_trans = translation_obj._get_source(cursor,
                            id2model[model_id] + ',' + rec['name'],
                            'help', context['language'])
                    if res_trans:
                        rec['help'] = res_trans

        if to_delete:
            for rec in res:
                for field in to_delete:
                    del rec[field]
        return res

ModelField()


class ModelAccess(ModelSQL, ModelView):
    "Model access"
    _name = 'ir.model.access'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Many2One('ir.model', 'Model', required=True,
            ondelete="CASCADE")
    group = fields.Many2One('res.group', 'Group',
            ondelete="CASCADE")
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Permission')
    description = fields.Text('Description')

    def __init__(self):
        super(ModelAccess, self).__init__()
        self._sql_constraints += [
            ('model_group_uniq', 'UNIQUE("model", "group")',
                'Only on record by model and group is allowed!'),
        ]
        self._error_messages.update({
            'read': 'You can not read this document! (%s)',
            'write': 'You can not write in this document! (%s)',
            'create': 'You can not create this kind of document! (%s)',
            'delete': 'You can not delete this document! (%s)',
            })

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def default_perm_read(self, cursor, user, context=None):
        return False

    def default_perm_write(self, cursor, user, context=None):
        return False

    def default_perm_create(self, cursor, user, context=None):
        return False

    def default_perm_delete(self, cursor, user, context=None):
        return False

    def check(self, cursor, user, model_name, mode='read',
            raise_exception=True, context=None):
        assert mode in ['read', 'write', 'create', 'delete'], \
                'Invalid access mode for security'
        model_obj = self.pool.get(model_name)
        if hasattr(model_obj, 'table_query') \
                and model_obj.table_query(context):
            return False
        if user == 0:
            return True
        cursor.execute('SELECT MAX(CASE WHEN perm_'+mode+' THEN 1 else 0 END) '
            'FROM ir_model_access a '
                'JOIN ir_model m '
                    'ON (a.model = m.id) '
                'JOIN res_group_user_rel gu '
                    'ON (gu.gid = a.group) '
            'WHERE m.model = %s AND gu.uid = %s', (model_name, user,))
        row = cursor.fetchall()
        if row[0][0] is None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model = m.id) ' \
                    'WHERE a.group IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] is None:
                return True

        if not row[0][0]:
            if raise_exception:
                self.raise_user_error(cursor, mode, model_name,
                        context=context)
            else:
                return False
        return True

    check = Cache('ir_model_access.check')(check)

    # Methods to clean the cache on the Check Method.
    def write(self, cursor, user, ids, vals, context=None):
        res = super(ModelAccess, self).write(cursor, user, ids, vals,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ModelAccess, self).create(cursor, user, vals,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def delete(self, cursor, user, ids, context=None):
        res = super(ModelAccess, self).delete(cursor, user, ids,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

ModelAccess()


class ModelData(ModelSQL, ModelView):
    "Model data"
    _name = 'ir.model.data'
    _description = __doc__
    fs_id = fields.Char('Identifier on File System', required=True,
            help="The id of the record as known on the file system.",
            select=1)
    model = fields.Char('Model', required=True, select=1)
    module = fields.Char('Module', required=True, select=1)
    db_id = fields.Integer('Resource ID',
       help="The id of the record in the database.", select=1)
    date_update = fields.DateTime('Update Date')
    date_init = fields.DateTime('Init Date')
    values = fields.Text('Values')
    inherit = fields.Boolean('Inherit')

    def __init__(self):
        super(ModelData, self).__init__()
        self._sql_constraints = [
            ('fs_id_module_model_uniq', 'UNIQUE("fs_id", "module", "model")',
                'The triple (fs_id, module, model) must be unique!'),
        ]

    def default_date_init(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def default_inherit(self, cursor, user, context=None):
        return False

    def get_id(self, cursor, user, module, fs_id):
        """
        Return for an fs_id the corresponding db_id.

        :param cursor: the database cursor
        :param user: the user id
        :param module: the module name
        :param fs_id: the id in the xml file

        :return: the database id
        """
        ids = self.search(cursor, user, [
            ('module', '=', module),
            ('fs_is', '=', fs_id),
            ('inherit', '=', False),
            ])
        if not ids:
            raise Exception("Reference to %s not found" % \
                                ".".join([module,fs_id]))
        return self.read(cursor, user, ids[0], ['db_id'])['db_id']

ModelData()


class PrintModelGraphInit(ModelView):
    'Print Model Graph Init'
    _name = 'ir.model.print_model_graph.init'
    _description = __doc__
    level = fields.Integer('Level')

    def default_level(self, cursor, user, context=None):
        return 1

PrintModelGraphInit()


class PrintModelGraph(Wizard):
    _name = 'ir.model.print_model_graph'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ir.model.print_model_graph.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-ok', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'ir.model.graph',
                'state': 'end',
            },
        },
    }

PrintModelGraph()


class ModelGraph(Report):
    _name = 'ir.model.graph'

    def execute(self, cursor, user, ids, datas, context=None):
        import pydot
        model_obj = self.pool.get('ir.model')

        if context is None:
            context = {}

        models = model_obj.browse(cursor, user, ids, context=context)

        graph = pydot.Dot(fontsize="8")
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        self.fill_graph(cursor, user, models, graph,
                level=datas['form']['level'], context=context)
        data = graph.create(prog='dot', format='png')
        return ('png', base64.encodestring(data), False)

    def fill_graph(self, cursor, user, models, graph, level=1, context=None):
        import pydot
        model_obj = self.pool.get('ir.model')

        sub_models = set()
        if level > 0:
            for model in models:
                for field in model.fields:
                    if field.name in ('create_uid', 'write_uid'):
                        continue
                    if field.relation and not graph.get_node(field.relation):
                        sub_models.add(field.relation)
            if sub_models:
                model_ids = model_obj.search(cursor, user, [
                    ('model', 'in', list(sub_models)),
                    ], context=context)
                sub_models = model_obj.browse(cursor, user, model_ids,
                        context=context)
                if set(sub_models) != set(models):
                    self.fill_graph(cursor, user, sub_models, graph,
                            level=level - 1, context=context)

        for model in models:
            label = '{' + model.model + '\\n'
            if model.fields:
                label += '|'
            for field in model.fields:
                if field.name in ('create_uid', 'write_uid',
                        'create_date', 'write_date', 'id'):
                    continue
                label += '+ ' + field.name + ': ' + field.ttype
                if field.relation:
                    label += ' ' + field.relation
                label += '\l'
            label += '}'
            if pydot.__version__ == '1.0.2':
                # version 1.0.2 doesn't quote correctly label on Node object
                label = '"' + label + '"'
            node = pydot.Node(str(model.model), shape='record', label=label)
            graph.add_node(node)

            for field in model.fields:
                if field.name in ('create_uid', 'write_uid'):
                    continue
                if field.relation:
                    node_name = field.relation
                    if pydot.__version__ == '1.0.2':
                        # version 1.0.2 doesn't quote correctly node name
                        node_name = '"' + node_name + '"'
                    if not graph.get_node(node_name):
                        continue
                    args = {}
                    tail = model.model
                    head = field.relation
                    edge_model_name = model.model
                    edge_relation_name = field.relation
                    if pydot.__version__ == '1.0.2':
                        # version 1.0.2 doesn't quote correctly edge name
                        edge_model_name = '"' + edge_model_name + '"'
                        edge_relation_name = '"' + edge_relation_name + '"'
                    if field.ttype == 'many2one':
                        edge = graph.get_edge(edge_model_name,
                                edge_relation_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                    elif field.ttype == 'one2many':
                        edge = graph.get_edge(edge_relation_name,
                                edge_model_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                        tail = field.relation
                        head = model.model
                    elif field.ttype == 'many2many':
                        if graph.get_edge(edge_model_name, edge_relation_name):
                            continue
                        if graph.get_edge(edge_relation_name, edge_model_name):
                            continue
                        args['arrowtail'] = "inv"
                        args['arrowhead'] = "inv"

                    edge = pydot.Edge(str(tail), str(head), **args)
                    graph.add_edge(edge)

ModelGraph()
