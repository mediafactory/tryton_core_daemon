#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model
from trytond.osv import fields
from trytond.model.browse import BrowseRecordList, BrowseRecord, BrowseRecordNull
from trytond.model.browse import EvalEnvironment
import datetime
import time
from decimal import Decimal

OPERATORS = (
    'child_of',
    'not child_of',
    '=',
    '!=',
    'like',
    'not like',
    'ilike',
    'not ilike',
    'in',
    'not in',
    '<=',
    '>=',
    '<',
    '>',
)



class ModelStorage(Model):
    """
    Define a model with storage capability in Tryton.
    """

    id = fields.Integer('ID', readonly=True)
    create_uid = fields.Many2One('res.user', 'Create User', required=True,
            readonly=True)
    create_date = fields.DateTime('Create Date', required=True, readonly=True)
    write_uid = fields.Many2One('res.user', 'Write User', readonly=True)
    write_date = fields.DateTime('Write Date', readonly=True)

    def __init__(self):
        super(ModelStorage, self).__init__()
        self._rpc_allowed += [
            'create',
            'read',
            'write',
            'delete',
            'copy',
            'search',
            'search_count',
            'search_read',
            'name_get',
            'name_search',
            'export_data',
            'import_data',
        ]
        self._constraints = []

    def default_create_uid(self, cursor, user, context=None):
        "Default value for uid field"
        return int(user)

    def default_create_date(self, cursor, user, context=None):
        "Default value for create_date field"
        return datetime.datetime.today()

    def default_sequence(self, cursor, user, context=None):
        '''
        Return the default value for sequence field.
        '''
        cursor.execute('SELECT MAX(sequence) ' \
                'FROM "' + self._table + '"')
        res = cursor.fetchone()
        if res:
            return res[0]
        return 0

    def create(self, cursor, user, values, context=None):
        '''
        Create records.

        :param cursor: the database cursor
        :param user: the user id
        :param values: a dictionary with fields names as key
                and created values as value
        :param context: the context
        :return: the id of the created record
        '''
        model_access_obj = self.pool.get('ir.model.access')
        model_access_obj.check(cursor, user, self._name, 'create',
                context=context)
        return False

    def read(self, cursor, user, ids, fields_names=None, context=None):
        '''
        Read records.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param fields_names: fields names to read if None read all fields
        :param context: the context
        :return: a list of dictionnary or a dictionnary if ids is an id
            the dictionnaries will have fields names as key
            and fields value as value
        '''
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, self._name, 'read',
                context=context)
        if isinstance(ids, (int, long)):
            return {}
        return []

    def write(self, cursor, user, ids, values, context=None):
        '''
        Write values on records

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param values: a dictionary with fields names as key
                and written values as value
        :param context: the context
        :return: True if succeed
        '''
        model_access_obj = self.pool.get('ir.model.access')
        rule_group_obj = self.pool.get('ir.rule.group')
        rule_obj = self.pool.get('ir.rule')

        model_access_obj.check(cursor, user, self._name, 'write',
                context=context)
        if not self.check_xml_record(cursor, user, ids, values,
                context=context):
            self.raise_user_error(cursor, 'write_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)
        # Restart rule cache
        if rule_group_obj.search(cursor, 0, [
            ('model.model', '=', self._name),
            ], context=context):
            rule_obj.domain_get(cursor.dbname)
        return False

    def delete(self, cursor, user, ids, context=None):
        '''
        Delete records.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param context: the context
        :return: True if succeed
        '''
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, self._name, 'delete',
                context=context)
        if not self.check_xml_record(cursor, user, ids, None, context=context):
            self.raise_user_error(cursor, 'delete_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)
        return False

    def copy(self, cursor, user, ids, default=None, context=None):
        '''
        Duplicate the record in ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param default: a dictionnary with field name as keys and
            new value for the field as value
        :param context: the context
        :return: a list of new ids or the new id
        '''
        lang_obj = self.pool.get('ir.lang')
        if default is None:
            default = {}
        if context is None:
            context = {}

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](cursor, user,
                        context)

        def convert_data(fields, data):
            for field_name in fields:
                ftype = fields[field_name]['type']

                if field_name in (
                    'create_date',
                    'create_uid',
                    'write_date',
                    'write_uid',
                    ):
                    del data[field_name]

                if field_name in default:
                    data[field_name] = default[field_name]
                elif ftype == 'function':
                    del data[field_name]
                elif ftype == 'many2one':
                    try:
                        data[field_name] = data[field_name] and \
                                data[field_name][0]
                    except:
                        pass
                elif ftype in ('one2many',):
                    res = []
                    rel = self.pool.get(fields[field_name]['relation'])
                    if data[field_name]:
                        data[field_name] = [('add', rel.copy(cursor, user,
                            data[field_name], context=context))]
                    else:
                        data[field_name] = False
                elif ftype == 'many2many':
                    if data[field_name]:
                        data[field_name] = [('set', data[field_name])]
            if 'id' in data:
                del data['id']
            for i in self._inherits:
                if self._inherits[i] in data:
                    del data[self._inherits[i]]

        new_ids = []
        datas = self.read(cursor, user, ids, context=context)
        fields = self.fields_get(cursor, user, context=context)
        for data in datas:
            convert_data(fields, data)
            new_ids.append(self.create(cursor, user, data, context=context))

        fields_translate = {}
        for field_name, field in fields.iteritems():
            if field_name in self._columns and \
                    self._columns[field_name].translate:
                fields_translate[field_name] = field
            elif field_name in self._inherit_fields and \
                    self._inherit_fields[field_name][2].translate:
                fields_translate[field_name] = field

        if fields_translate:
            lang_ids = lang_obj.search(cursor, user, [
                ('translatable', '=', True),
                ], context=context)
            if lang_ids:
                lang_ids += lang_obj.search(cursor, user, [
                    ('code', '=', 'en_US'),
                    ], context=context)
                langs = lang_obj.browse(cursor, user, lang_ids, context=context)
                for lang in langs:
                    ctx = context.copy()
                    ctx['language'] = lang.code
                    datas = self.read(cursor, user, ids,
                            fields_names=fields_translate.keys() + ['id'],
                            context=ctx)
                    for data in datas:
                        data_id = data['id']
                        convert_data(fields_translate, data)
                        self.write(cursor, user, data_id, data, context=ctx)
        if int_id:
            return new_ids[0]
        return new_ids

    def search(self, cursor, user, domain, offset=0, limit=None, order=None,
            context=None, count=False):
        '''
        Return a list of id that match the clauses defined in args.

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a list of tuples or lists
            lists are construct like this:
                ['operator', args, args, ...]
                operator can be 'AND' or 'OR', if it is missing the default
                value will be 'AND'
            tuples are construct like this:
                ('field name', 'operator', value)
                field name: is a field name from the model or a relational field
                    by using '.' as separator.
                operator must be in OPERATORS
        :param offset: an integer to specify the offset for the result
        :param limit: an integer to specify the number of result
        :param order: a list of tuple that are constructed like this:
            ('field name', 'DESC|ASC')
            it allow to specify the order of result
        :param context: the context
        :param count: a boolean to return only the len of the result
        :return: a list of ids or an interger
        '''
        if count:
            return 0
        return []

    def search_count(self, cursor, user, domain, context=None):
        '''
        Return the number of record that match the domain. (See search)

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain like in search
        :param context: the context
        :return: an integer
        '''
        res = self.search(cursor, user, domain, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def search_read(self, cursor, user, domain, offset=0, limit=None, order=None,
            context=None, fields_names=None):
        '''
        Call search function and read in once.
        Usefull for the client to reduce the number of calls.

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain like in search
        :param offset: an integer to specify the offset for the result
        :param limit: an integer to specify the number of result
        :param order: a list of tuple that are constructed like this:
            ('field name', 'DESC|ASC')
            it allow to specify the order of result
        :param context: the context
        :param fields_names: fields names to read if None read all fields
        :return: a list of dictionnary or a dictionnary if limit is 1
            the dictionnaries will have fields names as key
            and fields value as value
        '''
        ids = self.search(cursor, user, domain, offset=offset, limit=limit,
                order=order, context=context)
        if limit == 1:
            ids = ids[0]
        return self.read(cursor, user, ids, fields_names=fields_names,
                context=context)

    def _search_domain_active(self, domain, active_test=True, context=None):
        if context is None:
            context = {}

        domain = domain[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if not (('active' in self._columns or \
                'active' in self._inherit_fields.keys()) \
                and (active_test and context.get('active_test', True))):
            return domain

        def process(domain):
            i = 0
            active_found = False
            while i < len(domain):
                if isinstance(domain[i], list):
                    domain[i] = process(domain[i])
                if isinstance(domain[i], tuple):
                    if domain[i][0] == 'active':
                        active_found = True
                i += 1
            if not active_found:
                if domain and ((isinstance(domain[0], basestring) \
                        and domain[0] == 'AND') \
                        or (not isinstance(domain[0], basestring))):
                    domain.append(('active', '=', 1))
                else:
                    domain = ['AND', domain, ('active', '=', 1)]
            return domain
        return process(domain)

    def name_get(self, cursor, user, ids, context=None):
        '''
        Return a list of tuple for each ids.
        The tuple contains the id and the name of the record.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param context: the context
        :return: a list of tuple for each ids
        '''
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], unicode(r[self._rec_name])) for r in self.read(cursor,
            user, ids, [self._rec_name], context=context)]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        '''
        Return a list of tuple like in name_get
            where the name and the domain match.

        :param cursor: the database cursor
        :param user: the user id
        :param name: the name searched
        :param args: a domain like in search
        :param operator: the operator to use to compare name with _rec_name
        :param context: the context
        :param limit: a integer to limit the result
        :return: a list of tuple for each ids like in name_get
        '''
        if args is None:
            args = []
        if name:
            args = ['AND', args, (self._rec_name, operator, name)]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def browse(self, cursor, user, ids, context=None):
        '''
        Return a browse a BrowseRecordList for the ids
            or BrowseRecord if ids is a integer.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param context: the context
        :return: a BrowseRecordList or a BrowseRecord
        '''
        cache = {}
        if isinstance(ids, (int, long)):
            return BrowseRecord(cursor, user, ids, self, cache,
                    context=context)
        return BrowseRecordList([BrowseRecord(cursor, user, x, self, cache,
            context=context) for x in ids], context)

    def __export_row(self, cursor, user, row, fields_names, context=None):
        lines = []
        data = ['' for x in range(len(fields_names))]
        done = []
        for fpos in range(len(fields_names)):
            field = fields_names[fpos]
            if field:
                row2 = row
                i = 0
                while i < len(field):
                    row2 = row2[field[i]]
                    if not row2:
                        break
                    if isinstance(row2, (BrowseRecordList, list)):
                        first = True
                        fields2 = [(x[:i+1]==field[:i+1] and x[i+1:]) \
                                or [] for x in fields_names]
                        if fields2 in done:
                            break
                        done.append(fields2)
                        for row2 in row2:
                            lines2 = self.__export_row(cursor, user, row2,
                                    fields2, context)
                            if first:
                                for fpos2 in range(len(fields_names)):
                                    if lines2 and lines2[0][fpos2]:
                                        data[fpos2] = lines2[0][fpos2]
                                lines += lines2[1:]
                                first = False
                            else:
                                lines += lines2
                        break
                    i += 1
                if i == len(field):
                    data[fpos] = row2 or ''
        return [data] + lines

    def export_data(self, cursor, user, ids, fields_names, context=None):
        '''
        Return list of list of values for each ids.
        The list of values follow the fields_names.
        Relational fields are defined with '/' at any deep.

        :param cursor: the database cursor
        :param ids: a list of ids
        :param fields_names: a list of fields names
        :param context: the context
        :return: a list of list of values for each ids
        '''
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for row in self.browse(cursor, user, ids, context):
            datas += self.__export_row(cursor, user, row, fields_names, context)
        return datas

    def import_data(self, cursor, user, fields_names, datas, context=None):
        '''
        Create record for each values in datas.
        The fields name of values must be defined in fields_names.

        :param cursor: the database cursor
        :param user: the user id
        :param fields_names: a list of fields names
        :param datas: the datas to import
        :param context: the context
        :return: a tuple with
            - the number of records imported
            - the last values if failed
            - the exception if failed
            - the warning if failed
        '''
        if context is None:
            context = {}
        fields_names = [x.split('/') for x in fields_names]
        logger = logging.getLogger('import')

        def process_liness(self, datas, prefix, fields_def, position=0):
            line = datas[position]
            row = {}
            translate = {}
            todo = []
            warning = ''

            # Import normal fields_names
            for i in range(len(fields_names)):
                if i >= len(line):
                    raise Exception('ImportError',
                            'Please check that all your lines have %d cols.' % \
                            (len(fields_names),))
                field = fields_names[i]
                if (len(field) == len(prefix) + 1) \
                        and field[len(prefix)].endswith(':id'):
                    res_id = False
                    if line[i]:
                        if fields_def[field[len(prefix)][:-3]]['type'] \
                                == 'many2many':
                            res_id = []
                            for word in line[i].split(','):
                                module, xml_id = word.rsplit('.', 1)
                                ir_model_data_obj = \
                                        self.pool.get('ir.model.data')
                                new_id = ir_model_data_obj._get_id(cursor,
                                        user, module, xml_id)
                                res_id2 = ir_model_data_obj.read(cursor, user,
                                        [new_id], ['res_id'])[0]['res_id']
                                if res_id2:
                                    res_id.append(res_id2)
                            if len(res_id):
                                res_id = [('set', res_id)]
                        else:
                            module, xml_id = line[i].rsplit('.', 1)
                            ir_model_data_obj = self.pool.get('ir.model.data')
                            new_id = ir_model_data_obj._get_id(cursor, user,
                                    module, xml_id)
                            res_id = ir_model_data_obj.read(cursor, user,
                                    [new_id], ['res_id'])[0]['res_id']
                    row[field[0][:-3]] = res_id or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        len(field[len(prefix)].split(':lang=')) == 2:
                    field, lang = field[len(prefix)].split(':lang=')
                    translate.setdefault(lang, {})[field]=line[i] or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        (prefix == field[0:len(prefix)]):
                    if fields_def[field[len(prefix)]]['type'] == 'integer':
                        res = line[i] and int(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'float':
                        res = line[i] and float(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'selection':
                        res = False
                        if isinstance(
                                fields_def[field[len(prefix)]]['selection'],
                                (tuple, list)):
                            sel = fields_def[field[len(prefix)]]['selection']
                        else:
                            sel = getattr(self, fields_def[field[len(prefix)]]\
                                    ['selection'])(cursor, user, context)
                        for key, val in sel:
                            if str(key) == line[i]:
                                res = key
                        if line[i] and not res:
                            logger.warning("key '%s' not found " \
                                               "in selection field '%s'" % \
                                               (line[i], field[len(prefix)]))
                    elif fields_def[field[len(prefix)]]['type'] == 'many2one':
                        res = False
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            res2 = self.pool.get(relation).name_search(cursor,
                                    user, line[i], [], operator='=')
                            res = (res2 and res2[0][0]) or False
                            if not res:
                                warning += ('Relation not found: ' + line[i] + \
                                        ' on ' + relation + ' !\n')
                                logger.warning(
                                    'Relation not found: ' + line[i] + \
                                        ' on ' + relation + ' !\n')
                    elif fields_def[field[len(prefix)]]['type'] == 'many2many':
                        res = []
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            for word in line[i].split(','):
                                res2 = self.pool.get(relation).name_search(
                                        cursor, user, word, [], operator='=')
                                res3 = (res2 and res2[0][0]) or False
                                if not res3:
                                    warning += ('Relation not found: ' + \
                                            line[i] + ' on '+relation + ' !\n')
                                    logger.warning(
                                        'Relation not found: ' + line[i] + \
                                                    ' on '+relation + ' !\n')
                                else:
                                    res.append(res3)
                            if len(res):
                                res = [('set', res)]
                    else:
                        res = line[i] or False
                    row[field[len(prefix)]] = res
                elif (prefix==field[0:len(prefix)]):
                    if field[0] not in todo:
                        todo.append(field[len(prefix)])

            # Import one2many fields
            nbrmax = 1
            for field in todo:
                newfd = self.pool.get(fields_def[field]['relation']).fields_get(
                        cursor, user, context=context)
                res = process_liness(self, datas, prefix + [field], newfd,
                        position)
                (newrow, max2, warning2, translate2) = res
                nbrmax = max(nbrmax, max2)
                warning = warning + warning2
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and \
                        [('create', newrow)]) or []
                i = max2
                while (position+i)<len(datas):
                    test = True
                    for j in range(len(fields_names)):
                        field2 = fields_names[j]
                        if (len(field2) <= (len(prefix)+1)) \
                                and datas[position+i][j]:
                            test = False
                    if not test:
                        break

                    (newrow, max2, warning2, translate2) = \
                            process_liness(self, datas, prefix+[field], newfd,
                                    position + i)
                    warning = warning + warning2
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append(('create', newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)

            if len(prefix) == 0:
                for i in range(max(nbrmax, 1)):
                    datas.pop(0)
            result = (row, nbrmax, warning, translate)
            return result

        fields_def = self.fields_get(cursor, user, context=context)
        done = 0

        while len(datas):
            res = {}
            try:
                (res, other, warning, translate) = \
                        process_liness(self, datas, [], fields_def)
                if warning:
                    cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.create(cursor, user, res, context=context)
                for lang in translate:
                    context2 = context.copy()
                    context2['language'] = lang
                    self.write(cursor, user, new_id, translate[lang],
                            context=context2)
            except Exception, exp:
                logger.error(exp)
                cursor.rollback()
                return (-1, res, exp[0], warning)
            done += 1
        return (done, 0, 0, 0)

    def check_xml_record(self, cursor, user, ids, values, context=None):
        """
        Check if a list of records and their corresponding fields are
        originating from xml data. This is used by write and delete
        functions: if the return value is True the records can be
        written/deleted, False otherwise. The default behaviour is to
        forbid all modification on records/fields originating from
        xml. Values is the dictionary of written values. If values is
        equal to None, no field by field check is performed, False is
        return has soon has one of the record comes from the xml.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param values: a dictionary with fields names as key and
            written values as value
        :param context: the context
        :return: True or False
        """
        model_data_obj = self.pool.get('ir.model.data')
        # Allow root user to update/delete
        if user == 0:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        model_data_ids = model_data_obj.search(cursor, 0, [
            ('model', '=', self._name),
            ('db_id', 'in', ids),
            ], context=context)
        if not model_data_ids:
            return True
        if values == None:
            return False
        for line in model_data_obj.browse(cursor, 0, model_data_ids,
                context=context):
            if not line.values:
                continue
            xml_values = eval(line.values, {
                'Decimal': Decimal,
                'datetime': datetime,
                })
            for key, val in values.iteritems():
                if key in xml_values and val != xml_values[key]:
                    return False
        return True

    def check_recursion(self, cursor, user, ids, parent='parent'):
        '''
        Function that check if there is no recursion in the tree
        composed with parent as parent field name.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param parent: the parent field name
        :return: True or False
        '''
        ids_parent = ids[:]
        while len(ids_parent):
            ids_parent2 = set()
            for record in self.browse(cursor, user, ids_parent):
                if record[parent].id:
                    ids_parent2.add(record[parent].id)
            ids_parent = list(ids_parent2)
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def _validate(self, cursor, user, ids, context=None):
        if context is None:
            context = {}
        context = context.copy()
        field_error = []
        field_err_str = []
        for field in self._constraints:
            if not getattr(self, field[0])(cursor, user, ids):
                self.raise_user_error(cursor, field[1], context=context)

        if not 'res.user' in self.pool.object_name_list():
            ctx_pref = {
            }
        else:
            user_obj = self.pool.get('res.user')
            ctx_pref = user_obj.get_preferences(cursor, user,
                context_only=True, context=context)

        def get_error_args(field_name):
            model_field_obj = self.pool.get('ir.model.field')
            error_args = (field_name, self._name)
            if model_field_obj:
                model_field_ids = model_field_obj.search(cursor,
                        user, [
                            ('name', '=', field_name),
                            ('model.model', '=', self._name),
                            ], context=context, limit=1)
                if model_field_ids:
                    model_field = model_field_obj.browse(cursor,
                            user, model_field_ids[0],
                            context=context)
                    error_args = (model_field.field_description,
                            model_field.model.name)
            return error_args

        context.update(ctx_pref)
        records = self.browse(cursor, user, ids, context=context)
        for field_name, field in self._columns.iteritems():
            # validate domain
            if field._type in ('many2one', 'many2many', 'one2many') \
                    and field._domain:
                relation_obj = self.pool.get(field._obj)
                if isinstance(field._domain, basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        domain = eval(field._domain, env)
                        relation_ids = []
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                        if relation_ids and not relation_obj.search(cursor,
                                user, [
                                    'AND',
                                    [('id', 'in', relation_ids)],
                                    domain,
                                    ], context=context):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    relation_ids = []
                    for record in records:
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                    if relation_ids:
                        find_ids = relation_obj.search(cursor, user, [
                            'AND',
                            [('id', 'in', relation_ids)],
                            field._domain,
                            ], context=context)
                        if not set(relation_ids) == set(find_ids):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
            # validate states required
            if field.states and 'required' in field.states:
                if isinstance(field.states['required'], basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        required = eval(field.states['required'], env)
                        if required and not record[field_name]:
                            print record[field_name]
                            print field_name
                            print field.states['required']
                            self.raise_user_error(cursor,
                                    'required_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    if field.states['required']:
                        for record in records:
                            if not record[field_name]:
                                self.raise_user_error(cursor,
                                        'required_validation_record',
                                        error_args=get_error_args(field_name),
                                        context=context)

    def _clean_defaults(self, defaults):
        vals = {}
        for field in defaults.keys():
            fld_def = (field in self._columns) and self._columns[field] \
                    or self._inherit_fields[field][2]
            if fld_def._type in ('many2one',):
                if isinstance(defaults[field], (list, tuple)):
                    vals[field] = defaults[field][0]
                else:
                    vals[field] = defaults[field]
            elif fld_def._type in ('one2many',):
                obj = self.pool.get(self._columns[field]._obj)
                vals[field] = []
                for defaults2 in defaults[field]:
                    vals2 = obj._clean_defaults(defaults2)
                    vals[field].append(('create', vals2))
            elif fld_def._type in ('many2many',):
                vals[field] = [('set', defaults[field])]
            elif fld_def._type in ('boolean',):
                vals[field] = bool(defaults[field])
            else:
                vals[field] = defaults[field]
        return vals

    def _rebuild_tree(self, cursor, user, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        right = left + 1

        child_ids = self.search(cursor, 0, [
            (parent, '=', parent_id),
            ])

        for child_id in child_ids:
            right = self._rebuild_tree(cursor, user, parent, child_id, right)

        field = self._columns[parent]

        if parent_id:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + field.left + '" = %s, ' \
                        '"' + field.right + '" = %s ' \
                    'WHERE id = %s', (left, right, parent_id))
        return right + 1

    def _update_tree(self, cursor, user, object_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
            - the order of the tree respects the default _order
        '''
        cursor.execute('SELECT "' + left + '", "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        if not cursor.rowcount:
            return
        old_left, old_right = cursor.fetchone()
        if old_left == old_right:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + 1 ' \
                    'WHERE id = %s', (object_id,))
            old_right += 1

        parent_right = 1

        cursor.execute('SELECT "' + field_name + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        parent_id = cursor.fetchone()[0] or False

        if parent_id:
            cursor.execute('SELECT "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (parent_id,))
            parent_right = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT MAX("' + right + '") ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE "' + field_name + '" IS NULL')
            if cursor.rowcount:
                parent_right = cursor.fetchone()[0] + 1

        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                (old_left, old_right))
        child_ids = [x[0] for x in cursor.fetchall()]

        # ids for left update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        left_ids = [x[0] for x in cursor.fetchall()]

        # ids for right update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + right + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        right_ids = [x[0] for x in cursor.fetchall()]

        if left_ids:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                        + str(old_right - old_left + 1) + ' ' \
                    'WHERE id IN (' + ','.join(['%s' for x in left_ids]) + ')',
                    left_ids)
        if right_ids:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + ' \
                        + str(old_right - old_left + 1) + ' ' \
                    'WHERE id IN (' + ','.join(['%s' for x in right_ids]) + ')',
                    right_ids)

        cursor.execute('UPDATE "' + self._table + '" ' \
                'SET "' + left + '" = "' + left + '" + ' \
                        + str(parent_right - old_left) + ', ' \
                    '"' + right + '" = "' + right + '" + ' \
                        + str(parent_right - old_left) + ' ' \
                'WHERE id IN (' + ','.join(['%s' for x in child_ids]) + ')',
                child_ids)

        # Use root user to by-pass rules
        brother_ids = self.search(cursor, 0, [
            (field_name, '=', parent_id),
            ])
        if brother_ids[-1] != object_id:
            next_id = brother_ids[brother_ids.index(object_id) + 1]
            cursor.execute('SELECT "' + left + '",  "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (next_id,))
            next_left, next_right = cursor.fetchone()
            cursor.execute('SELECT "' + left + '", "' + right + '" '\
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (object_id,))
            current_left, current_right = cursor.fetchone()


            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                            + str(old_right - old_left + 1) + ', ' \
                        '"' + right + '" = "' + right + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (next_left, current_left))

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" - ' \
                            + str(current_left - next_left) + ', ' \
                        '"' + right + '" = "' + right + '" - ' \
                            + str(current_left - next_left) + ' ' \
                    'WHERE id in (' + ','.join(['%s' for x in child_ids]) + ')',
                    child_ids)