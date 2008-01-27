"Exports"
from trytond.osv import fields, OSV


class Export(OSV):
    "Export"
    _name = "ir.export"
    _description = __doc__
    _columns = {
            'name': fields.char('Export name', size=128),
            'resource': fields.char('Resource', size=128),
            'export_fields': fields.one2many('ir.export.line', 'export_id',
                'Export Id'),
    }

Export()


class ExportLine(OSV):
    "Export line"
    _name = 'ir.export.line'
    _description = __doc__
    _columns = {
            'name': fields.char('Field name', size=64),
            'export_id': fields.many2one('ir.export', 'Exportation',
                select=True),
            }

ExportLine()
