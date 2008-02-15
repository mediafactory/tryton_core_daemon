"Attachment"
import os
import md5
import base64
from trytond.osv import fields, OSV
from trytond.config import CONFIG

class Attachment(OSV):
    "Attachment"
    _name = 'ir.attachment'
    _description = __doc__
    _columns = {
        'name': fields.Char('Attachment Name',size=64, required=True),
        'datas': fields.Function('datas', fnct_inv='datas_inv',
            type='binary', string='Datas'),
        'datas_fname': fields.Char('Data Filename',size=64),
        'description': fields.Text('Description'),
        'res_model': fields.Char('Resource Model',size=64, readonly=True),
        'res_id': fields.Integer('Resource ID', readonly=True),
        'link': fields.Char('Link', size=256),
        'digest': fields.Char('Digest', size=32),
        'collision': fields.Integer('Collision'),
    }
    _defaults = {
        'collision': lambda *a: 0,
    }

    def datas(self, cursor, user, ids, name, arg, context=None):
        res = {}
        db_name = cursor.dbname
        for attachment in self.browse(cursor, user, ids, context=context):
            value = False
            if attachment.digest:
                filename = attachment.digest
                if attachment.collision:
                    filename = filename + '-' + str(attachment.collision)
                filename = os.path.join(CONFIG['data_path'], db_name,
                        filename[0:2], filename[2:4], filename)
                file_p = file(filename, 'rb')
                value = base64.encodestring(file_p.read())
                file_p.close()
            res[attachment.id] = value
        return res

    def datas_inv(self, cursor, user, obj_id, name, value, args, context=None):
        if not value:
            return
        db_name = cursor.dbname
        directory = os.path.join(CONFIG['data_path'], db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        data = base64.decodestring(value)
        digest = md5.new(data).hexdigest()
        directory = os.path.join(directory, digest[0:2], digest[2:4])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        filename = os.path.join(directory, digest)
        collision = 0
        if os.path.isfile(filename):
            file_p = file(filename, 'rb')
            data2 = file_p.read()
            file_p.close()
            if data != data2:
                cursor.execute('SELECT DISTINCT(collision) FROM ir_attachment ' \
                        'WHERE digest = %s ' \
                            'AND collision != 0 ' \
                        'ORDER BY collision', (digest,))
                collision2 = 0
                for row in cursor.fetchall():
                    collision2 = row[0]
                    filename = os.path.join(directory,
                            digest + '-' + str(collision2))
                    if os.path.isfile(filename):
                        file_p = file(filename, 'rb')
                        data2 = file_p.read()
                        file_p.close()
                        if data == data2:
                            collision = collision2
                            break
                if collision == 0:
                    collision = collision2 + 1
                    filename = os.path.join(directory,
                            digest + '-' + str(collision))
                    file_p = file(filename, 'wb')
                    file_p.write(data)
                    file_p.close()
        else:
            file_p = file(filename, 'wb')
            file_p.write(data)
            file_p.close()
        cursor.execute('UPDATE ir_attachment ' \
                'SET digest = %s, ' \
                    'collision = %d ' \
                'WHERE id = %d', (digest, collision, obj_id))

Attachment()
