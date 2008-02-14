"WebDAV"
import os
import base64
from trytond.osv import fields, OSV
from trytond.version import PACKAGE, VERSION, WEBSITE


class Directory(OSV):
    "Directory"
    _name = "webdav.directory"
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=128, required=True, select=1),
        'parent': fields.Many2One('webdav.directory', 'Parent'),
        'childs': fields.One2Many('webdav.directory', 'parent', 'Childs'),
        'model': fields.Many2One('ir.model', 'Model'),
        'domain': fields.Char('Domain', size=250),
    }
    _default = {
        'domain': lambda *a: '[]',
    }
    _sql_constraints = [
        ('name_parent_uniq', 'UNIQUE (name, parent)',
            'The directory name must be unique inside a directory!'),
    ]
    ext2mime = {
        '.png': 'image/png',
    }

    def _uri2object(self, cursor, user, uri, object_name=_name, object_id=False,
            context=None):
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == self._name:
            object_id = self.search(cursor, user, [
                ('name', '=', name),
                ('parent', '=', object_id),
                ], limit=1, context=context)
            if object_id:
                object_id = object_id[0]
                directory = self.browse(cursor, user, object_id,
                        context=context)
                if directory.model and uri:
                    object_name = directory.model.model
            else:
                if uri:
                    return None, 0
                object_name = 'ir.attachment'
                object_id = int(os.path.splitext(name)[0].rsplit('-',
                    1)[1].strip())
        else:
            if uri:
                if '/' in uri:
                    return None, 0
                #TODO add report
                object_name = 'ir.attachment'
                object_id = int(os.path.splitext(uri)[0].rsplit('-',
                    1)[1].strip())
                uri = None
            else:
                object_id = int(name.rsplit('-', 1)[1].strip())
        if uri:
            return self._uri2object(cursor, user, uri, object_name,
                    object_id, context)
        return object_name, object_id

    def get_childs(self, cursor, user, uri, context=None):
        res = []
        if not uri:
            directory_ids = self.search(cursor, user, [
                ('parent', '=', False),
                ], context=context)
            for directory in self.browse(cursor, user, directory_ids,
                    context=context):
                res.append(directory.name)
            return res
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == self._name:
            directory = self.browse(cursor, user, object_id, context=context)
            if directory.model:
                model_obj = self.pool.get(directory.model.model)
                model_ids = model_obj.search(cursor, user,
                        eval(directory.domain or "[]"), context=context)
                for child_id, child_name in model_obj.name_get(cursor, user,
                        model_ids, context=context):
                    res.append(child_name + '-' + str(child_id))
                return res
            else:
                for child in directory.childs:
                    res.append(child.name)
        if object_name not in ('ir.attachment', 'ir.action.report'):
            attachment_obj = self.pool.get('ir.attachment')
            attachment_ids = attachment_obj.search(cursor, user, [
                ('res_model', '=', object_name),
                ('res_id', '=', object_id),
                ], context=context)
            for attachment in attachment_obj.browse(cursor, user, attachment_ids,
                    context=context):
                if attachment.datas_fname and not attachment.link:
                    fname, fext = os.path.splitext(attachment.datas_fname)
                    if not fext:
                        fext = 'data'
                    res.append(fname + '-' + str(attachment.id) + fext)
        return res

    def get_resourcetype(self, cursor, user, uri, context=None):
        from DAV.constants import COLLECTION, OBJECT
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    def get_contentlength(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == 'ir.attachment':
            attachment_obj = self.pool.get('ir.attachment')
            attachment = attachment_obj.browse(cursor, user, object_id,
                    context=context)
            return str(len(attachment.datas))
        return '0'

    def get_contenttype(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == 'ir.attachment':
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return self.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    def get_data(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_NotFound
        if uri:
            object_name, object_id = self._uri2object(cursor, user, uri,
                    context=context)
            if object_name == 'ir.attachment':
                attachment_obj = self.pool.get('ir.attachment')
                attachment = attachment_obj.browse(cursor, user, object_id,
                        context=context)
                return base64.decodestring(attachment.datas)
        return DAV_NotFound

    def exists(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name:
            return 1
        return None

Directory()
