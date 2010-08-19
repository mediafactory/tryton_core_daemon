#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Binary(Field):
    '''
    Define a binary field (``str``).
    '''
    _type = 'binary'

    @staticmethod
    def get(ids, model, name, values=None):
        '''
        Convert the binary value into ``str``

        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :return: a dictionary with ids as key and values as value
        '''
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name] and str(i[name]) or None
        for i in ids:
            res.setdefault(i, None)
        return res
