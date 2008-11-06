#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'IR',
    'name_de_DE': 'Interne Administration',
    'description': '''Basic module handling internal tasks of the application.
Provides concepts and administration of models, actions, sequences, localizations, cron jobs etc.
''',
    'description_de_DE': '''Basismodul für interne Aufgaben der Anwendung

 - Stellt Konzept und Administration für Modelle, Aktionen, Sequenzen, Lokalisierungen, Zeitplaner etc. zur Verfügung
''',
    'active': True,
    'xml': [
        'ir.xml',
        'ui/ui.xml',
        'ui/menu.xml',
        'ui/view.xml',
        'action.xml',
        'model.xml',
        'sequence.xml',
        'attachment.xml',
        'cron.xml',
        'lang.xml',
        'translation.xml',
        'export.xml',
        'rule.xml',
        'property.xml',
        'module/module.xml',
        'default.xml',
        ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
