"model"
from trytond.osv import fields, OSV
from trytond.osv.orm import ExceptORM
from trytond.tools import Cache
import time


class Model(OSV):
    "Model"
    _name = 'ir.model'
    _description = __doc__
    _columns = {
        'name': fields.Char('Model name', size=64, translate=True),
        'model': fields.Char('Object name', size=64, required=True),
        'info': fields.Text('Information'),
        'fields': fields.One2Many('ir.model.field', 'model', 'Fields',
            required=True),
    }
    _defaults = {
        'name': lambda *a: 'No Name',
    }

Model()

class ModelField(OSV):
    "Model field"
    _name = 'ir.model.field'
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=64),
        'relation': fields.Char('Model Relation', size=64),
        'model': fields.Many2One('ir.model', 'Model', required=True,
            select=True, ondelete='cascade'),
        'field_description': fields.Char('Field Description', size=256,
            translate=True),
        'ttype': fields.Char('Field Type', size=64),
        'relate': fields.Boolean('Click and Relate'),

        'groups': fields.Many2Many('res.group', 'ir_model_field_group_rel',
            'field_id', 'group_id', 'Groups'),
        'group_name': fields.Char('Group Name', size=128),
        'view_load': fields.Boolean('View Auto-Load'),
        'help': fields.Text('Help', translate=True),
    }
    _defaults = {
        'relate': lambda *a: 0,
        'view_load': lambda *a: 0,
        'name': lambda *a: 'No Name',
        'field_description': lambda *a: 'No description available',
    }
    _order = "id"

ModelField()


class ModelAccess(OSV):
    "Model access"
    _name = 'ir.model.access'
    _description = __doc__
    _rec_name = 'model'
    _columns = {
        'model': fields.Many2One('ir.model', 'Model', required=True),
        'group': fields.Many2One('res.group', 'Group'),
        'perm_read': fields.Boolean('Read Access'),
        'perm_write': fields.Boolean('Write Access'),
        'perm_create': fields.Boolean('Create Access'),
        'perm_unlink': fields.Boolean('Delete Permission'),
        'description': fields.Text('Description'),
    }
    _sql_constraints = [
        ('model_group_uniq', 'UNIQUE("model", "group")',
            'Only on record by model and group is allowed!'),
    ]

    def check(self, cursor, user, model_name, mode='read',
            raise_exception=True):
        assert mode in ['read', 'write', 'create', 'unlink'], \
                'Invalid access mode for security'
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
        if row[0][0] == None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model = m.id) ' \
                    'WHERE a.group IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] == None:
                return True

        if not row[0][0]:
            if raise_exception:
                if mode == 'read':
                    raise ExceptORM('AccessError',
                            'You can not read this document! (%s)' \
                                    % model_name)
                elif mode == 'write':
                    raise ExceptORM('AccessError',
                            'You can not write in this document! (%s)' \
                                    % model_name)
                elif mode == 'create':
                    raise ExceptORM('AccessError',
                            'You can not create this kind of document! (%s)' \
                                    % model_name)
                elif mode == 'unlink':
                    raise ExceptORM('AccessError',
                            'You can not delete this document! (%s)' \
                                    % model_name)
                raise ExceptORM('AccessError',
                        'You do not have access to this document! (%s)' \
                                % model_name)
            else:
                return False
        return True

    check = Cache()(check)

    # Methods to clean the cache on the Check Method.
    def write(self, cursor, user, ids, vals, context=None):
        res = super(ModelAccess, self).write(cursor, user, ids, vals,
                context=context)
        self.check()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ModelAccess, self).create(cursor, user, vals,
                context=context)
        self.check()
        return res

    def unlink(self, cursor, user, ids, context=None):
        res = super(ModelAccess, self).unlink(cursor, user, ids,
                context=context)
        self.check()
        return res

ModelAccess()


class ModelData(OSV):
    "Model data"
    _name = 'ir.model.data'
    _description = __doc__
    _columns = {
        'fs_id': fields.Char('Identifier on File System', required=True,
            size=64, help="The id of the record as known on the file system."),
        'model': fields.Char('Model', required=True, size=64),
        'module': fields.Char('Module', required=True, size=64),
        'db_id': fields.Integer('Resource ID',
            help="The id of the record in the database."),
        'date_update': fields.DateTime('Update Date'),
        'date_init': fields.DateTime('Init Date'),
        'values': fields.Text('Values'),
    }
    _defaults = {
        'date_init': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    _sql_constraints = [
        ('fs_id_module_uniq', 'UNIQUE("fs_id", "module")',
            'The couple (fs_id, module) must be unique!'),
    ]

    def __init__(self, pool):
        super(ModelData, self).__init__(pool)
        if pool:
            self.fs2db = None
            self.fs2values = None


    def get_id(self, cursor, user, module, fs_id):
        """
        Return for an fs_id the corresponding db_id.
        """
        ids = self.search(cursor, user,
                          [('module','=',module),('fs_is','=',fs_id)])
        if not ids:
            raise Exception("Reference to %s not found"% \
                                ".".join([module,fs_id]))
        return self.read(cursor, user, ids[0],['db_id'])['db_id']



ModelData()
