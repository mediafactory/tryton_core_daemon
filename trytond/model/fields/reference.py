#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Reference(Field):
    _type = 'reference'

    def __init__(self, string='', selection=[], **args):
        super(Reference, self).__init__(string=string, **args)
        self.selection = selection

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        for i in ids:
            if not (i in res):
                res[i] = False
                continue
            if not res[i]:
                continue
            ref_model, ref_id = res[i].split(',', 1)
            if not ref_model:
                continue
            ref_obj = model.pool.get(ref_model)
            if not ref_obj:
                continue
            try:
                ref_id = eval(ref_id)
            except:
                pass
            try:
                ref_id = int(ref_id)
            except:
                continue
            ctx = context.copy()
            ctx['active_test'] = False
            if ref_id \
                and not ref_obj.search(cursor, user, [
                    ('id', '=', ref_id),
                    ], context=ctx):
                ref_id = False
            if ref_id:
                ref_name = ref_obj.name_get(cursor, user, ref_id,
                        context=context)
                if ref_name:
                    ref_name = ref_name[0][1]
                else:
                    ref_name = ''
            else:
                ref_name = ''
            res[i] = ref_model + ',(' + str(ref_id) + ',"' + ref_name + '")'
        return res
