#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import datetime
from decimal import Decimal
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval


class Boolean(ModelSQL):
    'Boolean'
    _name = 'test.boolean'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

Boolean()


class BooleanDefault(ModelSQL):
    'Boolean Default'
    _name = 'test.boolean_default'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

    def default_boolean(self, cursor, user, context=None):
        return True

BooleanDefault()


class Integer(ModelSQL):
    'Integer'
    _name = 'test.integer'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

Integer()


class IntegerDefault(ModelSQL):
    'Integer Default'
    _name = 'test.integer_default'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    def default_integer(self, cursor, user, context=None):
        return 5

IntegerDefault()


class IntegerRequired(ModelSQL):
    'Integer Required'
    _name = 'test.integer_required'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=True)

IntegerRequired()


class Float(ModelSQL):
    'Float'
    _name = 'test.float'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

Float()


class FloatDefault(ModelSQL):
    'Float Default'
    _name = 'test.float_default'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

    def default_float(self, cursor, user, context=None):
        return 5.5

FloatDefault()


class FloatRequired(ModelSQL):
    'Float Required'
    _name = 'test.float_required'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=True)

FloatRequired()


class FloatDigits(ModelSQL):
    'Float Digits'
    _name = 'test.float_digits'
    _description = __doc__
    digits = fields.Integer('Digits')
    float = fields.Float(string='Float', help='Test float',
            required=False, digits=(16, Eval('digits', 2)))

FloatDigits()


class Numeric(ModelSQL):
    'Numeric'
    _name = 'test.numeric'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

Numeric()


class NumericDefault(ModelSQL):
    'Numeric Default'
    _name = 'test.numeric_default'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

    def default_numeric(self, cursor, user, context=None):
        return Decimal('5.5')

NumericDefault()


class NumericRequired(ModelSQL):
    'Numeric Required'
    _name = 'test.numeric_required'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=True)

NumericRequired()


class NumericDigits(ModelSQL):
    'Numeric Digits'
    _name = 'test.numeric_digits'
    _description = __doc__
    digits = fields.Integer('Digits')
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False, digits=(16, Eval('digits', 2)))

NumericDigits()


class Char(ModelSQL):
    'Char'
    _name = 'test.char'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

Char()


class CharDefault(ModelSQL):
    'Char Default'
    _name = 'test.char_default'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

    def default_char(self, cursor, user, context=None):
        return 'Test'

CharDefault()


class CharRequired(ModelSQL):
    'Char Required'
    _name = 'test.char_required'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=True)

CharRequired()


class CharSize(ModelSQL):
    'Char Size'
    _name = 'test.char_size'
    _description = __doc__
    char = fields.Char(string='Char', size=5, help='Test char',
            required=False)

CharSize()


class Text(ModelSQL):
    'Text'
    _name = 'test.text'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

Text()


class TextDefault(ModelSQL):
    'Text Default'
    _name = 'test.text_default'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

    def default_text(self, cursor, user, context=None):
        return 'Test'

TextDefault()


class TextRequired(ModelSQL):
    'Text Required'
    _name = 'test.text_required'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=True)

TextRequired()


class TextSize(ModelSQL):
    'Text Size'
    _name = 'test.text_size'
    _description = __doc__
    text = fields.Text(string='Text', size=5, help='Test text',
            required=False)

TextSize()


class Sha(ModelSQL):
    'Sha'
    _name = 'test.sha'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=False)

Sha()


class ShaDefault(ModelSQL):
    'Sha Default'
    _name = 'test.sha_default'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=False)

    def default_sha(self, cursor, user, context=None):
        return 'Sha'

ShaDefault()


class ShaRequired(ModelSQL):
    'Sha Required'
    _name = 'test.sha_required'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=True)

ShaRequired()


class Date(ModelSQL):
    'Date'
    _name = 'test.date'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=False)

Date()


class DateDefault(ModelSQL):
    'Date Default'
    _name = 'test.date_default'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=False)

    def default_date(self, cursor, user, context=None):
        return datetime.date(2000, 1, 1)

DateDefault()


class DateRequired(ModelSQL):
    'Date Required'
    _name = 'test.date_required'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=True)

DateRequired()


class DateTime(ModelSQL):
    'DateTime'
    _name = 'test.datetime'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

DateTime()


class DateTimeDefault(ModelSQL):
    'DateTime Default'
    _name = 'test.datetime_default'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

    def default_datetime(self, cursor, user, context=None):
        return datetime.datetime(2000, 1, 1, 12, 0, 0, 0)

DateTimeDefault()


class DateTimeRequired(ModelSQL):
    'DateTime Required'
    _name = 'test.datetime_required'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=True)

DateTimeRequired()
