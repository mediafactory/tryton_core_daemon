#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import ModelView
from trytond.config import CONFIG
from trytond.backend import DatabaseIntegrityError
import sys
import copy
from xml import dom
import traceback
import logging
from threading import Lock
from random import randint
from sys import maxint


class Wizard(object):
    _name = ""
    states = {}

    def __new__(cls):
        Pool.register(cls, type='wizard')

    def __init__(self):
        super(Wizard, self).__init__()
        self._rpc = {
            'create': True,
            'delete': True,
            'execute': True,
        }
        self._error_messages = {}
        self._lock = Lock()
        self._datas = {}

    def init(self, cursor, module_name):
        for state in self.states.keys():
            if self.states[state]['result']['type'] == 'form':
                for i, button in enumerate(
                        self.states[state]['result']['state']):
                    button_name = button[0]
                    button_value = button[1]
                    cursor.execute('SELECT id, name, src ' \
                            'FROM ir_translation ' \
                            'WHERE module = %s ' \
                                'AND lang = %s ' \
                                'AND type = %s ' \
                                'AND name = %s',
                            (module_name, 'en_US', 'wizard_button',
                                self._name + ',' + state + ',' + button_name))
                    res = cursor.dictfetchall()
                    if not res:
                        cursor.execute('INSERT INTO ir_translation ' \
                                '(name, lang, type, src, value, module, fuzzy) ' \
                                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                (self._name + ',' + state + ',' + button_name,
                                    'en_US', 'wizard_button', button_value,
                                    '', module_name, False))
                    elif res[0]['src'] != button_value:
                        cursor.execute('UPDATE ir_translation ' \
                                'SET src = %s, ' \
                                    'fuzzy = %s '
                                'WHERE id = %s', (button_value, True,
                                    res[0]['id']))

        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        for error in self._error_messages.values():
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (self._name, 'en_US', 'error', error, '', module_name,
                            False))

    def raise_user_error(self, cursor, error, error_args=None,
            error_description='', error_description_args=None, context=None):
        translation_obj = self.pool.get('ir.translation')

        if context is None:
            context = {}

        error = self._error_messages.get(error, error)

        res = translation_obj._get_source(cursor, self._name, 'error',
                context.get('language', 'en_US'), error)
        if res:
            error = res

        if error_args:
            error = error % error_args

        if error_description:
            error_description = self._error_messages.get(error_description,
                    error_description)

            res = translation_obj._get_source(cursor, self._name, 'error',
                    context.get('language', 'en_US'), error_description)
            if res:
                error_description = res

            if error_description_args:
                error_description = error_description % error_description_args

            raise Exception('UserError', error, error_description)
        raise Exception('UserError', error)

    def create(self, cursor, user):
        self._lock.acquire()
        wiz_id = 0
        while True:
            wiz_id = randint(0, maxint)
            if wiz_id not in self._datas:
                break
        self._datas[wiz_id] = {'user': user, '_wiz_id': wiz_id}
        self._lock.release()
        return wiz_id

    def delete(self, cursor, user, wiz_id):
        if wiz_id not in self._datas:
            return
        if self._datas[wiz_id]['user'] != user:
            raise Exception('AccessDenied')
        self._lock.acquire()
        del self._datas[wiz_id]
        self._lock.release()

    def execute(self, cursor, user, wiz_id, data, state='init', context=None):
        translation_obj = self.pool.get('ir.translation')
        wizard_size_obj = self.pool.get('ir.action.wizard_size')
        if context is None:
            context = {}
        res = {}

        if self._datas[wiz_id]['user'] != user:
            raise Exception('AccessDenied')
        self._datas[wiz_id].update(data)
        data = self._datas[wiz_id]

        state_def = self.states[state]
        result_def = state_def.get('result', {})

        actions_res = {}
        # iterate through the list of actions defined for this state
        for action in state_def.get('actions', []):
            # execute them
            action_res = getattr(self, action)(cursor, user, data, context)
            assert isinstance(action_res, dict), \
                    'The return value of wizard actions ' \
                    'should be a dictionary'
            actions_res.update(action_res)

        res = copy.copy(result_def)
        if state_def.get('actions'):
            res['datas'] = actions_res

        lang = context.get('language', 'en_US')
        if result_def['type'] == 'action':
            res['action'] = getattr(self, result_def['action'])(cursor, user,
                    data, context)
        elif result_def['type'] == 'form':
            obj = self.pool.get(result_def['object'])

            view = obj.fields_view_get(cursor, user, view_type='form',
                    context=context, toolbar=False)
            fields = view['fields']
            arch = view['arch']

            button_list = copy.copy(result_def['state'])

            default_values = obj.default_get(cursor, user, fields.keys(),
                    context=context)
            for field in default_values.keys():
                if '.' in field:
                    continue
                fields[field]['value'] = default_values[field]

            # translate buttons
            for i, button  in enumerate(button_list):
                button_name = button[0]
                res_trans = translation_obj._get_source(cursor,
                        self._name + ',' + state + ',' + button_name,
                        'wizard_button', lang)
                if res_trans:
                    button = list(button)
                    button[1] = res_trans
                    button_list[i] = tuple(button)

            res['fields'] = fields
            res['arch'] = arch
            res['state'] = button_list
            res['size'] = wizard_size_obj.get_size(cursor, user, self._name,
                    result_def['object'], context=context)
        elif result_def['type'] == 'choice':
            next_state = getattr(self, result_def['next_state'])(cursor, user,
                    data, context)
            if next_state == 'end':
                return {'type': 'state', 'state': 'end'}
            return self.execute(cursor, user, wiz_id, data, next_state,
                    context=context)
        return res
