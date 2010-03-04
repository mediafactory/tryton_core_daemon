#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import datetime
from trytond.tools import reduce_ids, safe_eval, datetime_strftime


class ToolsTestCase(unittest.TestCase):
    '''
    Test tools.
    '''

    def test0000reduce_ids_empty(self):
        '''
        Test reduce_ids empty list.
        '''
        self.assert_(('(%s)', [False]) == reduce_ids('id', []))

    def test0010reduce_ids_continue(self):
        '''
        Test reduce_ids continue list.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)))', [0, 9]) == \
                reduce_ids('id', range(10)))

    def test0020reduce_ids_one_hole(self):
        '''
        Test reduce_ids continue list with one hole.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR ' \
                '((id >= %s) AND (id <= %s)))', [0, 9, 20, 29]) == \
                reduce_ids('id', range(10) + map(lambda x: x + 20, range(10))))

    def test0030reduce_ids_short_continue(self):
        '''
        Test reduce_ids short continue list.
        '''
        self.assert_(('((id IN (%s,%s,%s,%s)))', [0, 1, 2, 3]) == \
                reduce_ids('id', range(4)))

    def test0040reduce_ids_complex(self):
        '''
        Test reduce_ids complex list.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR ' \
                '(id IN (%s,%s,%s,%s,%s)))', [0, 14, 25, 26, 27, 28, 29]) == \
                reduce_ids('id', range(10) + map(lambda x: x + 25, range(5)) + \
                map(lambda x: x + 5, range(10))))

    def test0050reduce_ids_complex_small_continue(self):
        '''
        Test reduce_ids complex list with small continue.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR (id IN (%s,%s,%s,%s)))',
            [1, 12, 15, 18, 19, 21]) == \
                    reduce_ids('id', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15,
                        18, 19, 21]))

    def test0060safe_eval_builtin(self):
        '''
        Attempt to access a unsafe builtin.
        '''
        self.assertRaises(Exception, safe_eval, "open('test.txt', 'w')")

    def test0061safe_eval_getattr(self):
        '''
        Attempt to get arround direct attr access.
        '''
        self.assertRaises(Exception, safe_eval, "getattr(int, '__abs__')")

    def test0062safe_eval_func_globals(self):
        '''
        Attempt to access global enviroment where fun was defined.
        '''
        self.assertRaises(Exception, safe_eval,
                "def x(): pass; print x.func_globals")

    def test0063safe_eval_lowlevel(self):
        '''
        Lowlevel tricks to access 'object'.
        '''
        self.assertRaises(Exception, safe_eval,
                "().__class__.mro()[1].__subclasses__()")

    def test0070datetime_strftime(self):
        '''
        Test datetime_strftime
        '''
        self.assert_(datetime_strftime(datetime.date(2005, 3, 2),
            '%Y-%m-%d'), '2005-03-02')
        self.assert_(datetime_strftime(datetime.date(1805, 3, 2),
            '%Y-%m-%d'), '1805-03-02')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ToolsTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
