#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Lang"
from trytond.osv import fields, OSV


class Lang(OSV):
    "Language"
    _name = "ir.lang"
    _log_access = False
    _description = __doc__
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True,
            help="RFC 4646 tag: http://tools.ietf.org/html/rfc4646")
    translatable = fields.Boolean('Translatable')
    active = fields.Boolean('Active')
    direction = fields.Selection([
       ('ltr', 'Left-to-right'),
       ('rtl', 'Right-to-left'),
       ], 'Direction',required=True)

    #date
    date = fields.Char('Date', required=True)

    #number
    grouping = fields.Char('grouping', required=True)
    decimal_point = fields.Char('decimal_point', required=True)
    thousands_sep = fields.Char('thousands_sep')

    def __init__(self):
        super(Lang, self).__init__()
        self._constraints += [
            ('check_grouping', 'invalid_grouping'),
        ]
        self._error_messages.update({
            'invalid_grouping': 'Invalid Grouping!',
        })

    def default_active(self, cursor, user, context=None):
        return 1

    def default_translatable(self, cursor, user, context=None):
        return 0

    def default_direction(self, cursor, user, context=None):
        return 'ltr'

    def default_date(self, cursor, user, context=None):
        return '%m/%d/%Y'

    def default_grouping(self, cursor, user, context=None):
        return '[]'

    def default_decimal_point(self, cursor, user, context=None):
        return '.'

    def default_thousands_sep(self, cursor, user, context=None):
        return ','

    def check_grouping(self, cursor, user, ids):
        '''
        Check if grouping is list of numbers
        '''
        for lang in self.browse(cursor, user, ids):
            try:
                grouping = eval(lang.grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        return False
            except:
                return False
        return True

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def _group(self, lang, s, monetary=False):
        # Code from _group in locale.py
        if monetary:
            thousands_sep = monetary['mon_thousands_sep']
            grouping = eval(monetary['mon_grouping'])
        else:
            thousands_sep = lang['thousands_sep']
            grouping = eval(lang['grouping'])
        if not grouping:
            return (s, 0)
        result = ""
        seps = 0
        spaces = ""
        if s[-1] == ' ':
            sp = s.find(' ')
            spaces = s[sp:]
            s = s[:sp]
        while s and grouping:
            # if grouping is -1, we are done
            if grouping[0] == -1:
                break
            # 0: re-use last group ad infinitum
            elif grouping[0] != 0:
                #process last group
                group = grouping[0]
                grouping = grouping[1:]
            if result:
                result = s[-group:] + thousands_sep + result
                seps += 1
            else:
                result = s[-group:]
            s = s[:-group]
            if s and s[-1] not in "0123456789":
                # the leading string is only spaces and signs
                return s + result + spaces, seps
        if not result:
            return s + spaces, seps
        if s:
            result = s + thousands_sep + result
            seps += 1
        return result + spaces, seps


    def format(self, lang, percent, value, grouping=False, monetary=None, *additional):
        '''
        Returns the lang-aware substitution of a %? specifier (percent).

        :param lang: the BrowseRecord of the language
        :param percent: the string with %? specifier
        :param value: the value
        :param grouping: a boolean to take grouping into account
        :param monetary: a BrowseRecord of the currency or None
        :param additional: for format strings which contain one or more modifiers

        :return: the formatted string
        '''
        # Code from format in locale.py
        if not lang:
            lang = {
                'decimal_point': self.default_decimal_point(None, None),
                'thousands_sep': self.default_thousands_sep(None, None),
                'grouping': self.default_grouping(None, None),
            }

        # this is only for one-percent-specifier strings and this should be checked
        if percent[0] != '%':
            raise ValueError("format() must be given exactly one %char "
                             "format specifier")
        if additional:
            formatted = percent % ((value,) + additional)
        else:
            formatted = percent % value
        # floats and decimal ints need special action!
        if percent[-1] in 'eEfFgG':
            seps = 0
            parts = formatted.split('.')
            if grouping:
                parts[0], seps = self._group(lang, parts[0], monetary=monetary)
            if monetary:
                decimal_point = monetary['mon_decimal_point']
            else:
                decimal_point = lang['decimal_point']
            formatted = decimal_point.join(parts)
            while seps:
                sp = formatted.find(' ')
                if sp == -1: break
                formatted = formatted[:sp] + formatted[sp+1:]
                seps -= 1
        elif percent[-1] in 'diu':
            if grouping:
                formatted = self._group(lang, formatted, monetary=monetary)[0]
        return formatted


    def currency(self, lang, val, currency, symbol=True, grouping=False):
        """
        Formats val according to the currency settings in lang.

        :param lang: the BrowseRecord of the language
        :param val: the value to format
        :param currency: the BrowseRecord of the currency
        :param symbol: a boolean to include currency symbol
        :param grouping: a boolean to take grouping into account

        :return: the formatted string
        """
        # Code from currency in locale.py
        if not lang:
            lang = {
                'decimal_point': self.default_decimal_point(None, None),
                'thousands_sep': self.default_thousands_sep(None, None),
                'grouping': self.default_grouping(None, None),
            }

        # check for illegal values
        digits = currency.digits
        if digits == 127:
            raise ValueError("Currency formatting is not possible using "
                             "the 'C' locale.")

        s = self.format(lang, '%%.%if' % digits, abs(val), grouping,
                monetary=currency)
        # '<' and '>' are markers if the sign must be inserted between symbol and value
        s = '<' + s + '>'

        if symbol:
            smb = currency.symbol
            precedes = val<0 and currency.n_cs_precedes or currency.p_cs_precedes
            separated = val<0 and currency.n_sep_by_space or currency.p_sep_by_space

            if precedes:
                s = smb + (separated and ' ' or '') + s
            else:
                s = s + (separated and ' ' or '') + smb

        sign_pos = val<0 and currency.n_sign_posn or currency.p_sign_posn
        sign = val<0 and currency.negative_sign or currency.positive_sign

        if sign_pos == 0:
            s = '(' + s + ')'
        elif sign_pos == 1:
            s = sign + s
        elif sign_pos == 2:
            s = s + sign
        elif sign_pos == 3:
            s = s.replace('<', sign)
        elif sign_pos == 4:
            s = s.replace('>', sign)
        else:
            # the default if nothing specified;
            # this should be the most fitting sign position
            s = sign + s

        return s.replace('<', '').replace('>', '')

Lang()
