#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

class BrowseRecordList(list):
    '''
    A list of BrowseRecord
    '''
    #TODO: execute an object method on BrowseRecordList

    def __init__(self, lst, context=None):
        super(BrowseRecordList, self).__init__(lst)
        self.context = context

    def get_eval(self):
        res = []
        for record in self:
            res2 = {}
            for field_name, field in record._model._columns.iteritems():
                if not isinstance(record[field_name], BrowseRecordList):
                    res2[field_name] = record.get_eval(field_name)
            res.append(res2)
        return res


class BrowseRecordNull(object):
    '''
    An object that represents an empty record.
    '''

    def __init__(self):
        self.id = False

    def __getitem__(self, name):
        return False

    def __int__(self):
        return False

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False


class BrowseRecord(object):
    '''
    An object that represents record defined by a ORM object.
    '''

    def __init__(self, cursor, user, record_id, model, cache, context=None):
        self._cursor = cursor
        self._user = user
        self._id = record_id
        self._model = model
        self._model_name = self._model._name
        self._context = context or {}
        self._language_cache = {}

        cache.setdefault(model._name, {})
        self._data = cache[model._name]
        if not record_id in self._data:
            self._data[record_id] = {'id': record_id}
        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id
        if name == 'setLang':
            return self.setLang
        if not self._data[self._id].has_key(name):
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._model._columns:
                col = self._model._columns[name]
            elif name in self._model._inherit_fields:
                col = self._model._inherit_fields[name][2]
            elif hasattr(self._model, name):
                return getattr(self._model, name)
            else:
                raise Exception('Error', 'Programming error: field "%s" ' \
                        'does not exist in model "%s"!' \
                        % (name, self._model._name))

            if not hasattr(col, 'get'):
                # gen the list of "local" (ie not inherited)
                ffields = [x for x in self._model._columns.items() \
                        if not hasattr(x[1], 'get') \
                        and x[0] not in self._data[self._id] \
                        and ((not x[1].translate \
                                and x[1]._type not in ('text', 'binary')) \
                            or x[0] == name)]
                # gen the list of inherited fields
                inherits = [(x[0], x[1][2]) for x in \
                        self._model._inherit_fields.items()]
                # complete the field list with the inherited fields
                ffields += [x for x in inherits if not hasattr(x[1], 'get') \
                        and x[0] not in self._data[self._id] \
                        and ((not x[1].translate \
                                and x[1]._type not in ('text', 'binary')) \
                            or x[0] == name)]
            # otherwise we fetch only that field
            else:
                ffields = [(name, col)]

            # add datetime_field
            for i, j in ffields:
                if j._type == 'many2one' and hasattr(j, 'datetime_field') \
                        and j.datetime_field:
                    if j.datetime_field in self._model._columns:
                        col = self._model._columns[j.datetime_field]
                    else:
                        col = self._model._inherit_fields[j.datetime_field][2]
                    ffields.append((j.datetime_field, col))

            ids = [x for x in self._data.keys() \
                    if not self._data[x].has_key(name)]
            # read the data
            datas = self._model.read(self._cursor, self._user, ids,
                    [x[0] for x in ffields], context=self._context)

            # create browse records for 'remote' models
            for data in datas:
                for i, j in ffields:
                    model = None
                    if hasattr(j, 'model_name'):
                        if j.model_name not in self._model.pool.object_name_list():
                            continue
                        model = self._model.pool.get(j.model_name)
                    elif hasattr(j, 'get_target'):
                        model = j.get_target(self._model.pool)
                    if j._type in ('many2one',):
                        if not data[i]:
                            data[i] = BrowseRecordNull()
                        else:
                            ctx = self._context
                            if hasattr(j, 'datetime_field') and j.datetime_field:
                                ctx = self._context.copy()
                                ctx['_datetime'] = data[j.datetime_field]
                            data[i] = BrowseRecord(self._cursor, self._user,
                                    data[i], model, self._cache,
                                    context=ctx)
                    elif j._type in ('one2many', 'many2many') and len(data[i]):
                        data[i] = BrowseRecordList([BrowseRecord(self._cursor,
                            self._user,
                            isinstance(x, (list, tuple)) and x[0] or x, model,
                            self._cache, context=self._context) for x in data[i]],
                            self._context)
                self._data[data['id']].update(data)
        return self._data[self._id][name]

    def __getattr__(self, name):
        # TODO raise an AttributeError exception
        return self[name]

    def __contains__(self, name):
        return (name in self._model._columns) \
                or (name in self._model._inherit_fields) \
                or hasattr(self._model, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "BrowseRecord(%s, %d)" % (self._model_name, self._id)

    def __eq__(self, other):
        return (self._model_name, self._id) == (other._model_name, other._id)

    def __ne__(self, other):
        return (self._model_name, self._id) != (other._model_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._model_name, self._id))

    def __nonzero__(self):
        return bool(self._id)

    __repr__ = __str__

    def setLang(self, lang):
        self._context = self._context.copy()
        prev_lang = self._context.get('language') or 'en_US'
        self._context['language'] = lang
        for model in self._cache:
            for record_id in self._cache[model]:
                self._language_cache.setdefault(prev_lang,
                        {}).setdefault(model, {}).update(
                                self._cache[model][record_id])
                if lang in self._language_cache \
                        and model in self._language_cache[lang] \
                        and record_id in self._language_cache[lang][model]:
                    self._cache[model][record_id] = \
                            self._language_cache[lang][model][record_id]
                else:
                    self._cache[model][record_id] = {'id': record_id}

    def get_eval(self, name):
        res = self[name]
        if isinstance(res, BrowseRecord):
            res = res.id
        if isinstance(res, BrowseRecordList):
            res = res.get_eval()
        if isinstance(res, BrowseRecordNull):
            res = False
        return res


class EvalEnvironment(dict):

    def __init__(self, record, model):
        super(EvalEnvironment, self).__init__()
        self._record = record
        self._model = model

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            if field in self._model._columns:
                model_name = self._model._columns[field].model_name
            else:
                model_name = self._model._inherit_fields[field][2].model_name
            model = self._model.pool.get(model_name)
            return EvalEnvironment(self._record[field], model)
        if item in self._model._columns \
                or item in self._model._inherit_fields:
            return self._record.get_eval(item)
        return super(EvalEnvironment, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)

    def get(self, item):
        try:
            return self.__getitem__(item)
        except:
            pass
        return super(EvalEnvironment, self).get(item)

    def __nonzero__(self):
        return bool(self._record)
