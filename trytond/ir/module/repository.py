"Repository"
from trytond.osv import OSV, fields


class Repository(OSV):
    "Module repository"
    _name = "ir.module.repository"
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=128),
        'url': fields.Char('Url', size=256, required=True),
        'sequence': fields.Integer('Sequence', required=True),
        'filter': fields.Char('Filter', size=128, required=True,
            help='Regexp to search module on the repository webpage:\n'
            '- The first parenthesis must match the name of the module.\n'
            '- The second parenthesis must match all the version number.\n'
            '- The last parenthesis must match the extension of the module.'),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'sequence': lambda *a: 5,
        'filter': lambda *a: 'href="([a-zA-Z0-9_]+)-' \
                '((\\d+)((\\.\\d+)*)([a-z]?)' \
                '((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?)(\.zip)"',
        'active': lambda *a: 1,
    }
    _order = "sequence"

Repository()
