#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Res',
    'category': 'Generic',
    'description': '''Basic module handling internal tasks of the application.
Provides concepts and administration of users and internal communication.
''',
    'active': True,
    'depends': ['ir'],
    'xml': [
        'res.xml',
        'group.xml',
        'user.xml',
        'request.xml',
        'ir.xml',
        ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
