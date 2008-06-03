"Convert"
import re
import StringIO, xml.dom.minidom
from trytond import pooler
from trytond.osv.fields import Integer
import csv
import os.path
from trytond.netsvc import Logger, LOG_ERROR, LOG_INFO, LocalService, LOG_WARNING
from trytond.config import CONFIG
from trytond.version import VERSION
import logging
import time
from xml import sax
from decimal import Decimal
import datetime
import time

CDATA_START = re.compile('^\s*\<\!\[cdata\[', re.IGNORECASE)
CDATA_END = re.compile('\]\]\>\s*$', re.IGNORECASE)

class DummyTagHandler:
    """Dubhandler implementing empty methods. Will be used when whe
    want to ignore the xml content"""

    def __init__(self):
        pass

    def startElement(self, name, attributes):
        pass

    def characters(self, data):
        pass

    def endElement(self, name):
        pass


class MenuitemTagHandler:
    """Taghandler for the tag <record> """
    def __init__(self, master_handler):
        self.mh = master_handler

    def startElement(self, name, attributes):

        values = {}

        self.xml_id = attributes['id'].encode('utf8')

        for attr in ('name', 'icon', 'sequence', 'parent', 'action', 'groups'):
            if attributes.get(attr):
                values[attr] = attributes.get(attr).encode('utf8')


        if values.get('parent'):
            values['parent'] = self.mh.get_id(values['parent'])

        action_name = False
        if values.get('action'):
            action_id = self.mh.get_id(values['action'])

            # TODO maybe use a prefetch for this:
            self.mh.cursor.execute(
            "SELECT a.name, a.type, act.view_type, v.type " \
            "FROM ir_action a " \
                "LEFT JOIN ir_action_report report ON (a.id = report.action) " \
                "LEFT JOIN ir_action_act_window act ON (a.id = act.action) " \
                "LEFT JOIN ir_action_wizard wizard ON (a.id = wizard.action) " \
                "LEFT JOIN ir_action_url url ON (a.id = url.action) " \
                "LEFT JOIN ir_action_act_window_view wv on (act.id = wv.act_window) " \
                "LEFT JOIN ir_ui_view v on (v.id = wv.view) " \
            "WHERE report.id = %s " \
                "OR act.id = %s " \
                "OR wizard.id = %s " \
                "OR url.id = %s " \
            "ORDER by wv.sequence " \
            "LIMIT 1", (action_id, action_id, action_id, action_id))
            action_name, action_type, view_type, view_mode = \
                self.mh.cursor.fetchone()

            values['action'] = '%s,%s' % (action_type, action_id)

            icon = attributes.get('icon', '').encode('utf8')
            if icon:
                values['icon'] = icon
            elif action_type == 'ir.action.wizard':
                values['icon'] = 'STOCK_EXECUTE'
            elif action_type == 'ir.action.report':
                values['icon'] = 'STOCK_PRINT'
            elif action_type == 'ir.action.act_window':
                if view_type == 'tree':
                    values['icon'] = 'STOCK_INDENT'
                elif view_mode and view_mode.startswith('tree'):
                    values['icon'] = 'STOCK_JUSTIFY_FILL'
                elif view_mode and view_mode.startswith('form'):
                    values['icon'] = 'STOCK_NEW'
                elif view_mode and view_mode.startswith('graph'):
                    #TODO better icon
                    values['icon'] = 'STOCK_JUSTIFY_FILL'
                elif view_mode and view_mode.startswith('calendar'):
                    #TODO better icon
                    values['icon'] = 'STOCK_JUSTIFY_FILL'
            elif action_type == 'ir.action.url':
                values['icon'] = 'STOCK_JUMP_TO'
            else:
                values['icon'] = 'STOCK_NEW'

        if values.get('groups'):
            g_names = values['groups'].split(',')
            groups_value = []
            for group in g_names:
                if group.startswith('-'):
                    group_id = self.mh.get_id(group[1:])
                    groups_value.append(('remove', group_id))
                else:
                    group_id = self.mh.get_id(group)
                    groups_value.append(('add', group_id))
            values['groups'] = groups_value

        if not values.get('name'):
            if not action_name:
                raise Exception("Please provide at least a 'name' attributes "
                                "or a 'action' attributes on the menuitem tags.")
            else:
                values['name'] = action_name

        self.values = values


    def characters(self, data):
        pass

    def endElement(self, name):
        """Must return the object to use for the next call """
        if name != "menuitem":
            return self
        else:
            res = self.mh.import_record(
                'ir.ui.menu', self.values, self.xml_id)
            return None

    def current_state(self):
        return "Tag menuitem with id: %s"% \
               (self.xml_id)


class RecordTagHandler:

    """Taghandler for the tag <record> and all the tags inside it"""

    def __init__(self, master_handler):
        # Remind reference of parent handler
        self.mh = master_handler
        # stock xml_id parsed in one module
        self.xml_ids = []


    def startElement(self, name, attributes):

        # Manage the top level tag
        if name == "record":
            self.model = self.mh.pool.get(attributes["model"].encode('utf8'))
            assert self.model, "The model %s does not exist !" % \
                    (attributes["model"].encode('utf8'),)

            self.xml_id = attributes["id"].encode('utf8')
            self.update = bool(int(attributes.get('update', '0').encode('utf8')))

            # create/update a dict containing fields values
            self.values = {}

            self.current_field = None
            self.cdata = False

            return self.xml_id

        # Manage included tags:
        elif name == "field":

            field_name = attributes['name'].encode('utf8')
            field_type = attributes.get('type', '').encode('utf8')
            # Create a new entry in the values
            self.values[field_name] = ""
            # Remind the current name (see characters)
            self.current_field = field_name
            # Put a flag to escape cdata tags
            if field_type == "xml":
                self.cdata = "start"

            # Catch the known attributes
            search_attr = attributes.get('search','').encode('utf8')
            ref_attr = attributes.get('ref', '').encode('utf8')
            eval_attr = attributes.get('eval', '').encode('utf8')

            if search_attr:
                if attributes.get('model', ''):
                    search_model = attributes['model'].encode('utf8')
                else:
                    search_model = self.model._columns[field_name]._obj
                f_obj = self.mh.pool.get(search_model)
                answer = f_obj.browse(
                    self.mh.cursor, self.mh.user,
                    f_obj.search(self.mh.cursor, self.mh.user, eval(search_attr)))

                if not answer: return

                if self.model._columns[field_name]._type == 'many2many':
                    self.values[field_name] = [('set', [x['id'] for x in answer])]

                elif self.model._columns[field_name]._type == 'many2one':
                    self.values[field_name] = answer[0]['id']

            elif ref_attr:
                self.values[field_name] = self.mh.get_id(ref_attr)

            elif eval_attr:
                context = {}
                context['time'] = time
                context['version'] = VERSION.rsplit('.', 1)[0]
                context['ref'] = self.mh.get_id
                context['obj'] = lambda *a: 1
                self.values[field_name] = eval(eval_attr, context)

        else:
            raise Exception("Tags '%s' not supported inside tag record."% (name,))

    def characters(self, data):

        """If whe are in a field tag, consume all the content"""

        if not self.current_field:
            return
        # Escape start cdata tag if necessary
        if self.cdata == "start":
            data = CDATA_START.sub('', data)
            self.start_cdata = "inside"

        self.values[self.current_field] += data.encode('utf8')


    def endElement(self, name):

        """Must return the object to use for the next call, if name is
        not 'record' we return self to keep our hand on the
        process. If name is 'record' we return None to end the
        delegation"""

        if name == "field":
            if not self.current_field:
                raise Exception("Application error"
                                "current_field expected to be set.")
            # Escape end cdata tag :
            if self.cdata in ('inside', 'start'):
                self.values[self.current_field] =\
                    CDATA_END.sub('', self.values[self.current_field])
                self.cdata = 'done'

                value = self.values[self.current_field]
                match = re.findall('[^%]%\((.*?)\)[ds]', value)
                xml_ids = {}
                for xml_id in match:
                    xml_ids[xml_id] = self.mh.get_id(xml_id)
                self.values[self.current_field] = value % xml_ids

            self.current_field = None
            return self

        elif name == "record":
            if self.xml_id in self.xml_ids and not self.update:
                raise Exception('Duplicate id: "%s".' % (self.xml_id,))
            res = self.mh.import_record(
                self.model._name, self.values, self.xml_id)
            self.xml_ids.append(self.xml_id)
            return None
        else:
            raise Exception("Unexpected closing tag '%s'"% (name,))

    def current_state(self):
        return "In tag record: model %s with id %s."% \
               (self.model and self.model._name or "?", self.xml_id)


# Custom exception:
class Unhandled_field(Exception):
    """
    Raised when a field type is not supported by the update mechanism.
    """
    pass

class Fs2bdAccessor:
    """
    Used in TrytondXmlHandler.
    Provide some helper function to ease cache access and management.
    """

    def __init__(self, cursor, user, modeldata_obj):
        self.fs2db = {}
        self.fetched_modules = []
        self.modeldata_obj = modeldata_obj
        self.cursor = cursor
        self.user = user

    def get(self, module, fs_id):
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        return self.fs2db[module].get(fs_id, None)

    def set(self, module, fs_id, values):
        """
        Whe call the prefetch function here to. Like that whe are sure
        not to erase data when get is called.
        """
        if not module in self.fetched_modules:
            self.fetch_new_module(module)
        if fs_id not in self.fs2db[module]:
            self.fs2db[module][fs_id] = {}
        fs2db_val = self.fs2db[module][fs_id]
        for key, val in values.items():
            fs2db_val[key] = val

    def fetch_new_module(self, module):
        if module == "ir.ui.menu": raise
        self.fs2db[module] = {}
        module_data_ids = self.modeldata_obj.search(
            self.cursor, self.user, [('module','=',module)]
            )
        for rec in self.modeldata_obj.browse(
            self.cursor, self.user, module_data_ids):

            self.fs2db[rec.module][rec.fs_id] = {
                "db_id": rec.db_id, "model": rec.model,
                "id": rec.id, "values": rec.values
                }
        self.fetched_modules.append(module)


class TrytondXmlHandler(sax.handler.ContentHandler):

    def __init__(self, cursor, pool, module,):
        "Register known taghandlers, and managed tags."

        self.pool = pool
        self.cursor = cursor
        self.user = 0
        self.module = module
        self.modeldata_obj = pool.get('ir.model.data')
        self.fs2db = Fs2bdAccessor(cursor, self.user, self.modeldata_obj)
        self.to_delete = self.populate_to_delete()

        # Tag handlders are used to delegate the processing
        self.taghandlerlist = {
            'record': RecordTagHandler(self),
            'menuitem': MenuitemTagHandler(self),
            }
        self.taghandler = None

        # Managed tags are handled by the current class
        self.managedtags= ["data", "tryton"]

        # Connect to the sax api:
        self.sax_parser = sax.make_parser()
        # Tell the parser we are not interested in XML namespaces
        self.sax_parser.setFeature(sax.handler.feature_namespaces, 0)
        self.sax_parser.setContentHandler(self)


    def parse_xmlstream(self, stream):
        """
        Take a byte stream has input and parse the xml content.
        """

        source = sax.InputSource()
        source.setByteStream(stream)

        try:
            self.sax_parser.parse(source)
        except:
            Logger().notify_channel(
                "init", LOG_ERROR,
                "Error while parsing xml file:\n" +\
                    self.current_state()
                )

            raise
        return self.to_delete

    def startElement(self, name, attributes):
        """Rebind the current handler if necessary and call
        startElement on it"""

        if not self.taghandler:

            if  name in self.taghandlerlist:
                self.taghandler = self.taghandlerlist[name]
                self.taghandler.startElement(name, attributes)

            elif name == "data":
                self.noupdate = attributes.get("noupdate", False)

            elif name == "tryton":
                pass

            else:
                Logger().notify_channel("init", LOG_INFO,
                            "Tag "+ name + " not supported")
                return
        else:
            self.taghandler.startElement(name, attributes)

    def characters(self, data):
        if self.taghandler:
            self.taghandler.characters(data)

    def endElement(self, name):

        # Closing tag found, if we are in a delegation the handler
        # know what to do:
        if self.taghandler:
            self.taghandler = self.taghandler.endElement(name)

    def current_state(self):
        if self.taghandler:
            return self.taghandler.current_state()
        else:
            return ''

    def get_id(self, xml_id):

        if '.' in xml_id:
            module, xml_id = xml_id.split('.')
        else:
            module = self.module

        if self.fs2db.get(module, xml_id) == None:
            raise Exception("Reference to %s not found"% \
                                ".".join([module,xml_id]))
        return self.fs2db.get(module, xml_id)["db_id"]



    @staticmethod
    def _clean_value(key, browse_record, object_ref):
        """
        Take a field name, a browse_record, and a reference to the
        corresponding object.  Return a raw value has it must look on the
        db.
        """

        # search the field type in the object or in a parent
        if key in object_ref._columns:
            field_type = object_ref._columns[key]._type
        else:
            field_type = object_ref._inherit_fields[key][2]._type

        # handle the value regarding to the type
        if field_type == 'many2one':
            return browse_record[key] and browse_record[key].id or False
        elif field_type in ['one2one', 'one2many', "many2many"]:
            raise Unhandled_field()
        else:
            return browse_record[key]


    def populate_to_delete(self):
        """Create a list of all the records that whe should met in the update
        process. The records that are not encountered are deleted from the
        database in post_import."""

        # Fetch the data in id descending order to avoid depedendcy
        # problem when the corresponding recordds will be deleted:
        module_data_ids = self.modeldata_obj.search(
            self.cursor, self.user, [('module','=',self.module)],
            order=[('id', 'DESC')],
            )
        return [rec.fs_id for rec in self.modeldata_obj.browse(
                self.cursor, self.user, module_data_ids)]

    def import_record(self, model, values, fs_id):

        cursor = self.cursor
        module = self.module
        user = self.user

        if not fs_id:
            raise Exception('import_record : Argument fs_id is mandatory')

        if '.' in fs_id:
            assert len(fs_id.split('.')) == 2, '"%s" contains too many dots. '\
                    'file system ids should contain ot most one dot ! ' \
                    'These are used to refer to other modules data, ' \
                    'as in module.reference_id' % (fs_id)

            module, fs_id = fs_id.split('.')

        object_ref = self.pool.get(model)

        if self.fs2db.get(module, fs_id):
            # this record is already in the db:
            # XXX maybe use only one call to get()
            db_id, db_model, mdata_id, old_values = \
                [self.fs2db.get(module, fs_id)[x] for x in \
                     ["db_id","model","id","values"]
                 ]

            if old_values == None:
                old_values = {}
            else:
                old_values = eval(old_values, {
                    'Decimal': Decimal,
                    'datetime': datetime,
                    })

            # Check if values for this record has been modified in the
            # db, if not it's ok to overwrite them.
            if model != db_model:
                raise Exception("This record try to overwrite"
                "data with the wrong model: %s (module: %s)"% (fs_id, module))

            #Re-create object if it was deleted
            if not object_ref.search(cursor, user, [('id', '=', db_id)]):
                db_id = object_ref.create(cursor, user, values,
                        context={'module': module})
                data_id = self.modeldata_obj.search(cursor, user, [
                    ('fs_id', '=', fs_id),
                    ('module', '=', module),
                    ], limit=1)[0]
                self.modeldata_obj.write(cursor, user, data_id, {
                    'db_id': db_id,
                    })
                self.fs2db.get(module, fs_id)["db_id"] = db_id

            db_val = object_ref.browse(cursor, user, db_id)

            to_update = {}
            for key in values:

                try:
                    db_field = self._clean_value(key, db_val, object_ref)
                except Unhandled_field:
                    logger = Logger()
                    logger.notify_channel('init', LOG_WARNING,
                        'Field %s on %s : integrity not tested.'%(key, model))
                    to_update[key] = values[key]
                    continue

                # if the fs value is the same has in the db, whe ignore it
                if db_field == values[key]:
                    continue

                # we cannot update a field if it was changed by a user...
                if key not in  old_values:
                    expected_value = object_ref._defaults.get(
                        key, lambda *a:None)(cursor, user)
                else:
                    expected_value = old_values[key]

                # ... and we consider that there is an update if the
                # expected value differs from the actual value, _and_
                # if they are not false in a boolean context (ie None,
                # False, {} or [])
                if db_field != expected_value and (db_field or expected_value) :
                    logger = Logger()
                    logger.notify_channel('init', LOG_WARNING,
                        "Field %s of %s@%s not updated (id: %s), because "\
                        "it has changed since the last update"% \
                        (key, db_id, model, fs_id))
                    continue

                # so, the field in the fs and in the db are different,
                # and no user changed the value in the db:
                to_update[key] = values[key]

            # if there is values to update:
            if to_update:
                # write the values in the db:
                object_ref.write(cursor, user, db_id, to_update)
                # re-read it: this ensure that we store the real value
                # in the model_data table:
                db_val = object_ref.browse(cursor, user, db_id)
                for key in to_update:
                    try:
                        values[key] = self._clean_value(
                            key, db_val, object_ref)
                    except Unhandled_field:
                        continue

            if values != old_values:
                self.modeldata_obj.write(cursor, user, mdata_id, {
                    'fs_id': fs_id,
                    'model': model,
                    'module': module,
                    'db_id': db_id,
                    'values': str(values),
                    'date_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                    })

            # Remove this record from the to_delete list. This means that
            # the corresponding record have been found.
            if module == self.module and fs_id in self.to_delete:
                self.to_delete.remove(fs_id)
        else:
            # this record is new, create it in the db:
            db_id = object_ref.create(cursor, user, values,
                    context={'module': module})
            # re-read it: this ensure that we store the real value
            # in the model_data table:
            db_val = object_ref.browse(cursor, user, db_id)
            for key in values:
                try:
                    values[key] = self._clean_value(key, db_val,
                            object_ref)
                except Unhandled_field:
                    continue

            mdata_id = self.modeldata_obj.create(cursor, user, {
                'fs_id': fs_id,
                'model': model,
                'module': module,
                'db_id': db_id,
                'values': str(values),
                })
            # update fs2db:
            self.fs2db.set(module, fs_id, {
                    "db_id": db_id, "model": model,
                    "id": mdata_id, "values": str(values)})


def post_import(cursor, module, to_delete):
    """
    Remove the records that are given in to_delete.
    """

    user = 0
    wf_service = LocalService("workflow")
    mdata_unlink = []
    pool = pooler.get_pool(cursor.dbname)
    modeldata_obj = pool.get("ir.model.data")
    transition_unlink = []

    mdata_ids = modeldata_obj.search(
            cursor, user, [('fs_id','in',to_delete)],
            order=[('id', 'DESC')],
            )

    for mrec in modeldata_obj.browse(cursor, user, mdata_ids):
        mdata_id, model, db_id = mrec.id, mrec.model, mrec.db_id

        # Whe skip transitions, they will be deleted with the
        # corresponding activity:
        if model == 'workflow.transition':
            transition_unlink.append((mdata_id, db_id))
            continue

        if model == 'workflow.activity':

            wkf_todo = []
            # search for records that are in the state/activity that
            # we want to delete...
            cursor.execute('SELECT res_type, res_id ' \
                    'FROM wkf_instance ' \
                    'WHERE id IN (' \
                        'SELECT instance FROM wkf_workitem ' \
                        'WHERE activity = %s)', (db_id,))
            #... connect the transitions backward...
            wkf_todo.extend(cursor.fetchall())
            cursor.execute("UPDATE wkf_transition " \
                    'SET condition = \'True\', "group" = NULL, ' \
                        "signal = NULL, act_to = act_from, " \
                        "act_from = %s " \
                    "WHERE act_to = %s", (db_id, db_id))
            # ... and force the record to follow them:
            for wkf_model,wkf_model_id in wkf_todo:
                wf_service.trg_write(user, wkf_model, wkf_model_id, cursor)

            # Collect the ids of these transition in model_data
            cursor.execute(
                "SELECT md.id FROM ir_model_data md " \
                    "JOIN wkf_transition t ON "\
                    "(md.model='workflow.transition' and md.db_id=t.id)" \
                    "WHERE t.act_to = %s", (db_id,))
            mdata_unlink.extend([x[0] for x in cursor.fetchall()])

            # And finally delete the transitions
            cursor.execute("DELETE FROM wkf_transition " \
                    "WHERE act_to = %s", (db_id,))

            wf_service.trg_write(user, model, db_id, cursor)


        logger = Logger()
        logger.notify_channel('init', LOG_INFO,
                'Deleting %s@%s' % (db_id, model))
        try:
            # Deletion of the record
            pool.get(model).unlink(cursor, user, db_id)
            mdata_unlink.append(mdata_id)
            cursor.commit()
        except:
            cursor.rollback()
            logger.notify_channel('init', LOG_ERROR,
                    'Could not delete id: %d of model %s\n' \
                            'There should be some relation ' \
                            'that points to this resource\n' \
                            'You should manually fix this ' \
                            'and restart --update=module' % \
                            (db_id, model))

    transition_obj = pool.get('workflow.transition')
    for mdata_id, db_id in transition_unlink:
        logger = Logger()
        logger.notify_channel('init', LOG_INFO,
                'Deleting %s@workflow.transition' % (db_id,))
        try:
            transition_obj.unlink(cursor, user, db_id)
            mdata_unlink.append(mdata_id)
            cursor.commit()
        except:
            cursor.rollback()
            logger.notify_channel('init', LOG_ERROR,
                    'Could not delete id: %d of model workflow.transition' % \
                            (db_id,))

    # Clean model_data:
    if mdata_unlink:
        modeldata_obj.unlink(cursor, user, mdata_unlink)
        cursor.commit()

    return True
