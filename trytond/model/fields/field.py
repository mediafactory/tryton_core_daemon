#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pyson import PYSON

def domain_validate(value):
    from trytond.model.modelstorage import OPERATORS
    assert isinstance(value, list), 'domain must be a list'
    def test_domain(dom):
        for arg in dom:
            if isinstance(arg, basestring):
                if arg not in ('AND', 'OR'):
                    return False
            elif isinstance(arg, tuple) or \
                    (isinstance(arg, list) and len(arg) > 2 and \
                    (arg[1] in OPERATORS) or \
                    (isinstance(arg[1], PYSON) and \
                    arg[1].types() == set([str]))):
                pass
            elif isinstance(arg, list):
                if not test_domain(arg):
                    return False
        return True
    assert test_domain(value), 'invalid domain'

def states_validate(value):
    assert isinstance(value, dict), 'states must be a dict'
    for state in value:
        if state == 'icon':
            continue
        assert isinstance(value[state], PYSON), \
                'values of states must be PYSON'
        assert value[state].types() == set([bool]), \
                'values of states must return boolean'

def on_change_validate(value):
    if value:
        assert isinstance(value, list), 'on_change must be a list'

def on_change_with_validate(value):
    if value:
        assert isinstance(value, list), 'on_change_with must be a list'

def depends_validate(value):
    assert isinstance(value, list), 'depends must be a list'

def context_validate(value):
    assert isinstance(value, dict), 'context must be a dict'


class Field(object):
    _type = None

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, priority=0, change_default=False,
            translate=False, select=0, on_change=None, on_change_with=None,
            depends=None, order_field=None, context=None):
        '''
        :param string: A string for label of the field.
        :param help: A multi-line help string.
        :param required: A boolean if ``True`` the field is required.
        :param readonly: A boolean if ``True`` the field is not editable in
            the user interface.
        :param domain: A list that defines a domain constraint. See domain on
            ModelStorage.search.
        :param states: A dictionary. Possible keys are ``required``,
            ``readonly`` and ``invisible``. Values are pyson expressions that
            will be evaluated with record values. This allows to change
            dynamically the attributes of the field.
        :param priority: Give the order in which set methods are called.
        :param change_default: A boolean. If ``True`` the field can be used as
        condition for a custom default value.
        :param translate: A boolean. If ``True`` the field is translatable.
        :param select: An integer. When equal to ``1``, the field appears in the
            search box in list view and the search will be optimized. When equal to
            ``2`` the field appears in the *Advanced Search* in the search box.
        :param on_change: A list of values. If set, the client will call the
            method ``on_change_<field_name>`` when the user changes the field
            value. It then passes this list of values as arguments to the
            function.
        :param on_change_with: A list of values. Like ``on_change``, but defined
            the other way around. The list contains all the fields that must
            update the current field.
        :param depends: A list of field name on which this one depends.
        :param order_field: A string. If set it will use the string when
            ordering records on the field.
        :param context: A dictionary which will be given to open the relation
            fields.
        '''
        self.string = string
        self.help = help
        self.required = required
        self.readonly = readonly
        self.__domain = None
        self.domain = domain or []
        self.__states = None
        self.states = states or {}
        self.priority = priority
        self.change_default = change_default
        self.translate = translate
        self.select = select
        self.__on_change = None
        self.on_change = on_change
        self.__on_change_with = None
        self.on_change_with = on_change_with
        self.__depends = None
        self.depends = depends or []
        self.order_field = order_field
        self.__context = None
        self.context = context or {}

    def _get_domain(self):
        return self.__domain

    def _set_domain(self, value):
        domain_validate(value)
        self.__domain = value

    domain = property(_get_domain, _set_domain)

    def _get_states(self):
        return self.__states

    def _set_states(self, value):
        states_validate(value)
        self.__states = value

    states = property(_get_states, _set_states)

    def _get_on_change(self):
        return self.__on_change

    def _set_on_change(self, value):
        on_change_validate(value)
        self.__on_change = value
    on_change = property(_get_on_change, _set_on_change)

    def _get_on_change_with(self):
        return self.__on_change_with

    def _set_on_change_with(self, value):
        on_change_with_validate(value)
        self.__on_change_with = value

    on_change_with = property(_get_on_change_with, _set_on_change_with)

    def _get_depends(self):
        return self.__depends

    def _set_depends(self, value):
        depends_validate(value)
        self.__depends = value

    depends = property(_get_depends, _set_depends)

    def _get_context(self):
        return self.__context

    def _set_context(self, value):
        context_validate(value)
        self.__context = value

    context = property(_get_context, _set_context)
