#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"WebDAV"
import os
import base64
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.version import PACKAGE, VERSION, WEBSITE
from trytond.report import Report


class Collection(ModelSQL, ModelView):
    "Collection"
    _name = "webdav.collection"
    _description = __doc__
    name = fields.Char('Name', size=128, required=True, select=1)
    parent = fields.Many2One('webdav.collection', 'Parent',
       ondelete='RESTRICT', domain=[('model', '=', False)])
    childs = fields.One2Many('webdav.collection', 'parent', 'Children')
    model = fields.Many2One('ir.model', 'Model')
    domain = fields.Char('Domain', size=250)

    def __init__(self):
        super(Collection, self).__init__()
        self._sql_constraints += [
            ('name_parent_uniq', 'UNIQUE (name, parent)',
                'The collection name must be unique inside a collection!'),
        ]
        self._constraints += [
            ('check_recursion', 'recursive_collections'),
            ('check_attachment', 'collection_file_name'),
        ]
        self._error_messages.update({
            'recursive_collections': 'You can not create recursive ' \
                    'collections!',
            'collection_file_name': 'You can not create a collection\n' \
                    'in a collection with the name of an ' \
                    'existing file!',
        })
        self.ext2mime = {
            '.png': 'image/png',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.pdf': 'application/pdf',
        }

    def default_domain(self, cursor, user, context=None):
        return '[]'

    def check_attachment(self, cursor, user, ids):
        attachment_obj = self.pool.get('ir.attachment')
        for collection in self.browse(cursor, user, ids):
            if collection.parent:
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', self._name),
                    ('res_id', '=', collection.parent.id),
                    ])
                for attachment in attachment_obj.browse(cursor, user,
                        attachment_ids):
                    if attachment.name == collection.name:
                        return False
        return True

    def _uri2object(self, cursor, user, uri, object_name=_name, object_id=False,
            context=None, cache=None):
        attachment_obj = self.pool.get('ir.attachment')
        report_obj = self.pool.get('ir.action.report')
        cache_uri = uri

        if cache is not None:
            cache.setdefault('_uri2object', {})
            if cache_uri in cache['_uri2object']:
                return cache['_uri2object'][cache_uri]

        if not uri:
            if cache is not None:
                cache['_uri2object'][cache_uri] = (self._name, False)
            return self._name, False
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == self._name:
            collection_ids = None
            if cache is not None:
                cache.setdefault('_parent2collection_ids', {})
                if object_id in cache['_parent2collection_ids']:
                    collection_ids = cache['_parent2collection_ids']\
                            [object_id].get(name, [])
            if collection_ids is None:
                collection_ids = self.search(cursor, user, [
                    ('parent', '=', object_id),
                    ], context=context)
                collections = self.browse(cursor, user, collection_ids,
                        context=context)
                collection_ids = []
                if cache is not None:
                    cache['_parent2collection_ids'].setdefault(object_id, {})
                for collection in collections:
                    if cache is not None:
                        cache['_parent2collection_ids'][object_id]\
                                .setdefault(collection.name, [])
                        cache['_parent2collection_ids'][object_id]\
                                [collection.name].append(collection.id)
                    if collection.name == name:
                        collection_ids.append(collection.id)
            if collection_ids:
                object_id = collection_ids[0]
                object_name2 = None
                if cache is not None:
                    cache.setdefault('_collection_name', {})
                    if object_id in cache['_collection_name']:
                        object_name2 = cache['_collection_name'][object_id]
                if object_name2 is None:
                    collection = self.browse(cursor, user, object_id,
                            context=context)
                    if collection.model and uri:
                        object_name = collection.model.model
                        if cache is not None:
                            cache['_collection_name'][object_id] = object_name
                else:
                    object_name = object_name2
            else:
                if uri:
                    if cache is not None:
                        cache['_uri2object'][cache_uri] = (None, 0)
                    return None, 0

                attachment_ids = None
                if cache is not None:
                    cache.setdefault('_model&id2attachment_ids', {})
                    if (object_name, object_id) in \
                            cache['_model&id2attachment_ids']:
                        attachment_ids = cache['_model&id2attachment_ids']\
                                [(object_name, object_id)].get(name, [])
                if attachment_ids is None:
                    attachment_ids = attachment_obj.search(cursor, user, [
                        ('res_model', '=', object_name),
                        ('res_id', '=', object_id),
                        ], context=context)
                    attachments = attachment_obj.browse(cursor, user,
                            attachment_ids, context=context)
                    key = (object_name, object_id)
                    attachment_ids = []
                    if cache is not None:
                        cache['_model&id2attachment_ids'].setdefault(key, {})
                    for attachment in attachments:
                        if cache is not None:
                            cache['_model&id&name2attachment_ids'][key]\
                                    .setdefault(attachment.name, [])
                            cache['_model&id&name2attachment_ids'][key]\
                                    [attachment.name].append(attachment.id)
                        if attachment.name == name:
                            attachment_ids.append(attachment.id)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
        else:
            splitted_name = name.rsplit('-', 1)
            if len(splitted_name) != 2:
                if cache is not None:
                    cache['_uri2object'][cache_uri] = (object_name, 0)
                return object_name, 0
            object_id = int(splitted_name[1].strip())
            if uri:
                if '/' in uri:
                    if cache is not None:
                        cache['_uri2object'][cache_uri] = (None, 0)
                    return None, 0
                report_ids = report_obj.search(cursor, user, [
                    ('model', '=', object_name),
                    ], context=context)
                reports = report_obj.browse(cursor, user, report_ids,
                    context=context)
                for report in reports:
                    report_name = report.name + '-' + str(report.id) \
                            + '.' + report.output_format.format
                    if uri == report_name:
                        if cache is not None:
                            cache['_uri2object'][cache_uri] = \
                                    ('ir.action.report', object_id)
                        return 'ir.action.report', object_id
                name = uri
                attachment_ids = None
                if cache is not None:
                    cache.setdefault('_model&id2attachment_ids', {})
                    if (object_name, object_id) in \
                            cache['_model&id2attachment_ids']:
                        attachment_ids = cache['_model&id2attachment_ids']\
                                [(object_name, object_id)].get(name, [])
                if attachment_ids is None:
                    attachment_ids = attachment_obj.search(cursor, user, [
                        ('res_model', '=', object_name),
                        ('res_id', '=', object_id),
                        ], context=context)
                    attachments = attachment_obj.browse(cursor, user,
                        attachment_ids, context=context)
                    key = (object_name, object_id)
                    attachment_ids = []
                    if cache is not None:
                        cache['_model&id2attachment_ids'].setdefault(key, {})
                    for attachment in attachments:
                        if cache is not None:
                            cache['_model&id2attachment_ids'][key]\
                                    .setdefault(attachment.name, [])
                            cache['_model&id2attachment_ids'][key]\
                                    [attachment.name].append(attachment.id)
                        if attachment.name == name:
                            attachment_ids.append(attachment.id)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
                if cache is not None:
                    cache['_uri2object'][cache_uri] = (object_name, object_id)
                return object_name, object_id
        if uri:
            res = self._uri2object(cursor, user, uri, object_name,
                    object_id, context=context, cache=cache)
            if cache is not None:
                cache['_uri2object'][cache_uri] = res
            return res
        if cache is not None:
            cache['_uri2object'][cache_uri] = (object_name, object_id)
        return object_name, object_id

    def get_childs(self, cursor, user, uri, context=None, cache=None):
        report_obj = self.pool.get('ir.action.report')
        res = []
        if not uri:
            collection_ids = self.search(cursor, user, [
                ('parent', '=', False),
                ], context=context)
            for collection in self.browse(cursor, user, collection_ids,
                    context=context):
                if '/' in collection.name:
                    continue
                res.append(collection.name)
                if cache is not None:
                    cache.setdefault(self._name, {})
                    cache[self._name][collection.id] = {}
            return res
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name == self._name and object_id:
            collection = self.browse(cursor, user, object_id, context=context)
            if collection.model:
                model_obj = self.pool.get(collection.model.model)
                if not model_obj:
                    return res
                model_ids = model_obj.search(cursor, user,
                        eval(collection.domain or "[]"), context=context)
                for child in model_obj.browse(cursor, user,
                        model_ids, context=context):
                    if '/' in child.rec_name:
                        continue
                    res.append(child.rec_name + '-' + str(child.id))
                    if cache is not None:
                        cache.setdefault(model_obj._name, {})
                        cache[model_obj._name][child.id] = {}
                return res
            else:
                for child in collection.childs:
                    if '/' in child.name:
                        continue
                    res.append(child.name)
                    if cache is not None:
                        cache.setdefault(self._name, {})
                        cache[self._name][child.id] = {}
        if object_name not in ('ir.attachment', 'ir.action.report'):
            report_ids = report_obj.search(cursor, user, [
                ('model', '=', object_name),
                ], context=context)
            reports = report_obj.browse(cursor, user, report_ids,
                context=context)
            for report in reports:
                report_name = report.name + '-' + str(report.id) \
                        + '.' + report.output_format.format
                if '/' in report_name:
                    continue
                res.append(report_name)
                if cache is not None:
                    cache.setdefault(report_obj._name, {})
                    cache[report_obj._name][report.id] = {}

            attachment_obj = self.pool.get('ir.attachment')
            attachment_ids = attachment_obj.search(cursor, user, [
                ('res_model', '=', object_name),
                ('res_id', '=', object_id),
                ], context=context)
            for attachment in attachment_obj.browse(cursor, user, attachment_ids,
                    context=context):
                if attachment.name and not attachment.link:
                    if '/' in attachment.name:
                        continue
                    res.append(attachment.name)
                    if cache is not None:
                        cache.setdefault(attachment_obj._name, {})
                        cache[attachment_obj._name][attachment.id] = {}
        return res

    def get_resourcetype(self, cursor, user, uri, context=None, cache=None):
        from DAV.constants import COLLECTION, OBJECT
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    def get_contentlength(self, cursor, user, uri, context=None, cache=None):
        attachment_obj = self.pool.get('ir.attachment')

        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name == 'ir.attachment':

            if cache is not None:
                cache.setdefault('ir.attachment', {})
                ids = cache['ir.attachment'].keys()
                if object_id not in ids:
                    ids.append(object_id)
                elif 'contentlength' in cache['ir.attachment'][object_id]:
                    return cache['ir.attachment'][object_id]['contentlength']
            else:
                ids = [object_id]

            attachments = attachment_obj.browse(cursor, user, ids,
                    context=context)

            res = '0'
            for attachment in attachments:
                try:
                    if attachment.datas_size:
                        size = str(attachment.datas_size)
                except:
                    size = '0'
                if attachment.id == object_id:
                    res = size
                if cache is not None:
                    cache['ir.attachment'].setdefault(attachment.id, {})
                    cache['ir.attachment'][attachment.id]['contentlength'] = \
                            size
            return res
        return '0'

    def get_contenttype(self, cursor, user, uri, context=None, cache=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return self.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    def get_creationdate(self, cursor, user, uri, context=None, cache=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name:
            model_obj = self.pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(model_obj._name, {})
                    ids = cache[model_obj._name].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'creationdate' in cache[model_obj._name][object_id]:
                        return cache[model_obj._name][object_id]['creationdate']
                else:
                    ids = [object_id]
                cursor.execute('SELECT id, EXTRACT(epoch FROM create_date) ' \
                        'FROM "' + model_obj._table +'" ' \
                        'WHERE id IN (' + \
                            ','.join(['%s' for x in ids]) + ')', ids)
                res = None
                for object_id2, date in cursor.fetchall():
                    if object_id2 == object_id:
                        res = date
                    if cache is not None:
                        cache[model_obj._name].setdefault(object_id2, {})
                        cache[model_obj._name][object_id2]['creationdate'] = \
                                date
                if res is not None:
                    return res
        return time.time()

    def get_lastmodified(self, cursor, user, uri, context=None, cache=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name:
            model_obj = self.pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(model_obj._name, {})
                    ids = cache[model_obj._name].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'lastmodified' in cache[model_obj._name][object_id]:
                        return cache[model_obj._name][object_id]['lastmodified']
                else:
                    ids = [object_id]
                cursor.execute('SELECT id, EXTRACT(epoch FROM write_date) ' \
                        'FROM "' + model_obj._table +'" ' \
                        'WHERE id IN (' + \
                            ','.join(['%s' for x in ids]) + ')', ids)
                res = None
                for object_id2, date in cursor.fetchall():
                    if object_id2 == object_id:
                        res = date
                    if cache is not None:
                        cache[model_obj._name].setdefault(object_id2, {})
                        cache[model_obj._name][object_id2]['lastmodified'] = \
                                date
                if res is not None:
                    return res
        return time.time()

    def get_data(self, cursor, user, uri, context=None, cache=None):
        from DAV.errors import DAV_NotFound
        attachment_obj = self.pool.get('ir.attachment')
        report_obj = self.pool.get('ir.action.report')

        if uri:
            object_name, object_id = self._uri2object(cursor, user, uri,
                    context=context, cache=cache)

            if object_name == 'ir.attachment' and object_id:
                if cache is not None:
                    cache.setdefault('ir.attachment', {})
                    ids = cache['ir.attachment'].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'data' in cache['ir.attachment'][object_id]:
                        res = cache['ir.attachment'][object_id]['data']
                        if res == DAV_NotFound:
                            raise DAV_NotFound
                        return res
                else:
                    ids = [object_id]
                attachments = attachment_obj.browse(cursor, user, ids,
                        context=context)

                res = DAV_NotFound
                for attachment in attachments:
                    try:
                        if attachment.datas:
                            data = base64.decodestring(attachment.datas)
                    except:
                        data = DAV_NotFound
                    if attachment.id == object_id:
                        res = data
                    if cache is not None:
                        cache['ir.attachment'].setdefault(attachment.id, {})
                        cache['ir.attachment'][attachment.id]['data'] = data
                if res == DAV_NotFound:
                    raise DAV_NotFound
                return res

            if object_name == 'ir.action.report' and object_id:
                report_id = int(uri.rsplit('/', 1)[-1].rsplit('-',
                    1)[-1].rsplit('.', 1)[0])
                report = report_obj.browse(cursor, user, report_id,
                        context=context)
                if report.report_name:
                    report_obj = self.pool.get(report.report_name,
                            type='report')
                    val = report_obj.execute(cursor, user, [object_id],
                            {'id': object_id, 'ids': [object_id]},
                            context=context)
                    return base64.decodestring(val[1])
        raise DAV_NotFound

    def put(self, cursor, user, uri, data, content_type, context=None,
            cache=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context, cache=cache)
        if not object_name \
                or object_name in ('ir.attachment') \
                or not object_id:
            raise DAV_Forbidden
        attachment_obj = self.pool.get('ir.attachment')
        object_name2, object_id2 = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if not object_id2:
            name = get_urifilename(uri)
            try:
                attachment_obj.create(cursor, user, {
                    'name': name,
                    'datas': base64.encodestring(data),
                    'name': name,
                    'res_model': object_name,
                    'res_id': object_id,
                    }, context=context)
            except:
                raise DAV_Forbidden
        else:
            try:
                attachment_obj.write(cursor, user, object_id2, {
                    'datas': base64.encodestring(data),
                    }, context=context)
            except:
                raise DAV_Forbidden
        return 201

    def mkcol(self, cursor, user, uri, context=None, cache=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        if uri[-1:] == '/':
            uri = uri[:-1]
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context, cache=cache)
        if object_name != 'webdav.collection':
            raise DAV_Forbidden
        name = get_urifilename(uri)
        try:
            self.create(cursor, user, {
                'name': name,
                'parent': object_id,
                }, context=context)
        except:
            raise DAV_Forbidden
        return 201

    def rmcol(self, cursor, user, uri, context=None, cache=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name != 'webdav.collection' \
                or not object_id:
            raise DAV_Forbidden
        try:
            self.delete(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def rm(self, cursor, user, uri, context=None, cache=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if not object_name:
            raise DAV_Forbidden
        if object_name != 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        model_obj = self.pool.get(object_name)
        try:
            model_obj.delete(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def exists(self, cursor, user, uri, context=None, cache=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context, cache=cache)
        if object_name and object_id:
            return 1
        return None

Collection()


class Attachment(ModelSQL, ModelView):
    _name = 'ir.attachment'

    def __init__(self):
        super(Attachment, self).__init__()
        self._constraints += [
            ('check_collection', 'collection_attachment_name'),
        ]
        self._error_messages.update({
            'collection_attachment_name': 'You can not create a attachment\n' \
                    'in a collection with the name\n' \
                    'of an existing child collection!',
        })

    def check_collection(self, cursor, user, ids):
        collection_obj = self.pool.get('webdav.collection')
        for attachment in self.browse(cursor, user, ids):
            if attachment.res_model == 'webdav.collection':
                collection = collection_obj.browse(cursor, user,
                        attachment.res_id)
                for child in collection.childs:
                    if child.name == attachment.name:
                        return False
        return True

Attachment()
