#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha


class Field(object):

    @staticmethod
    def sql_format(value):
        if value is None or value == False:
            return None
        elif isinstance(value, str):
            return unicode(value, 'utf-8')
        elif isinstance(value, unicode):
            return value
        return unicode(value)

    @staticmethod
    def sql_type(field):
        return None


class Boolean(Field):

    @staticmethod
    def sql_format(value):
        return value and 'True' or 'False'


class Integer(Field):

    @staticmethod
    def sql_format(value):
        return int(value or 0)


class BigInteger(Integer):
    pass


class Char(Field):
    pass


class Sha(Field):

    @staticmethod
    def sql_format(value):
        if isinstance(value, basestring):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            if hashlib:
                value = hashlib.sha1(value).hexdigest()
            else:
                value = sha.new(value).hexdigest()
        return Field.sql_format(value)


class Text(Field):
    pass


class Float(Field):

    @staticmethod
    def sql_format(value):
        return float(value or 0.0)


class Numeric(Float):
    pass


class Date(Field):

    @staticmethod
    def sql_format(value):
        return value or None


class DateTime(Field):

    @staticmethod
    def sql_format(value):
        return value or None


class Time(Field):
    pass


class Binary(Field):

    @staticmethod
    def sql_format(value):
        return value or None


class Selection(Char):
    pass


class Reference(Field):
    pass


class Many2One(Field):

    @staticmethod
    def sql_format(value):
        return value and int(value) or None


class One2Many(Field):
    pass


class Many2Many(Field):
    pass


class Function(Field):
    pass


class Property(Function):
    pass
