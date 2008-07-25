#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Properties"
from trytond.osv import OSV, fields
from decimal import Decimal


class Property(OSV):
    "Property"
    _name = 'ir.property'
    _description = __doc__
    name = fields.Char('Name')
    #TODO add function field for other type than many2one
    value = fields.Reference('Value', selection='models_get')
    res = fields.Reference('Resource', selection='models_get')
    field = fields.Many2One('ir.model.field', 'Field',
        ondelete='CASCADE', required=True)

    def models_get(self, cursor, user, context=None):
        cursor.execute('SELECT model, name FROM ir_model ORDER BY name ASC')
        res = cursor.fetchall() + [('', '')]
        return res

    def get(self, cursor, user, name, model, res_ids=None, context=None):
        """
        Return property value for each res_ids
        name: property name
        model: object name
        """
        model_field_obj = self.pool.get('ir.model.field')
        res = {}

        field_id = model_field_obj.search(cursor, user, [
            ('name', '=', name),
            ('model.model', '=', model),
            ], limit=1, context=context)[0]
        field = model_field_obj.browse(cursor, user, field_id, context=context)

        default_id = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', False),
            ], limit=1, context=context)
        default_val = False
        if default_id:
            value = self.browse(cursor, user, default_id[0],
                    context=context).value
            val = False
            if value:
                if value.split(',')[0]:
                    val = int(value.split(',')[1])
                else:
                    if field.ttype == 'numeric':
                        val = Decimal(value.split(',')[1])
                    elif field.ttype == 'char':
                        val = prop.value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            default_val = val

        if not res_ids:
            if field.ttype == 'many2one':
                obj = self.pool.get(field.relation)
                if not obj.search(cursor, user, [('id', '=', default_val)],
                        context=context):
                    return False
            return default_val

        for obj_id in res_ids:
            res[obj_id] = default_val

        property_ids = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', 'in', [model + ',' + str(obj_id) \
                    for obj_id in  res_ids]),
            ])
        for prop in self.browse(cursor, user, property_ids):
            val = False
            if prop.value:
                if prop.value.split(',')[0]:
                    val = int(prop.value.split(',')[1])
                else:
                    if field.ttype == 'numeric':
                        val = Decimal(prop.value.split(',')[1])
                    elif field.ttype == 'char':
                        val = prop.value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            res[int(prop.res.split(',')[1])] = val

        if field.ttype == 'many2one':
            obj = self.pool.get(field.relation)
            obj_ids = obj.search(cursor, user, [('id', 'in', res.values())],
                    context=context)
            for res_id in res:
                if res[res_id] not in obj_ids:
                    res[res_id] = False
        return res

    def set(self, cursor, user, name, model, res_id, val, context=None):
        """
        Set property value for res_id
        """
        model_field_obj = self.pool.get('ir.model.field')
        field_id = model_field_obj.search(cursor, user, [
            ('name', '=', name),
            ('model.model', '=', model),
            ], limit=1, context=context)[0]

        property_ids = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', model + ',' + str(res_id)),
            ], context=context)
        self.delete(cursor, user, property_ids, context=context)

        default_id = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', False),
            ], limit=1, context=context)
        default_val = False
        if default_id:
            default_val = self.browse(cursor, user, default_id[0],
                    context=context).value

        res = False
        if (val != default_val):
            res = self.create(cursor, user, {
                'name': name,
                'value': val,
                'res': model + ',' + str(res_id),
                'field': field_id,
            }, context=context)
        return res

Property()
