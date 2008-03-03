"Action"
from trytond.osv import fields, OSV
from trytond.osv.orm import ExceptORM
from trytond.tools import file_open


class Action(OSV):
    "Action"
    _name = 'ir.action'
    _description = __doc__
    name = fields.char('Name', required=True, size=64, translate=True)
    type = fields.char('Type', required=True, size=32, readonly=True)
    usage = fields.char('Usage', size=32)
    keywords = fields.one2many('ir.action.keyword', 'action',
            'Keywords')
    groups = fields.Many2Many('res.group', 'ir_action_group_rel',
            'action_id', 'gid', 'Groups')

    def default_usage(self, cursor, user, context=None):
        return False

    def get_action_id(self, cursor, user, action_id, context=None):
        if self.search(cursor, user, [
            ('id', '=', action_id),
            ], context=context):
            return action_id
        for action_type in (
                'ir.action.report',
                'ir.action.act_window',
                'ir.action.wizard',
                'ir.action.url',
                ):
            action_obj = self.pool.get(action_type)
            action_id2 = action_obj.search(cursor, user, [
                ('id', '=', action_id),
                ], context=context)
            if action_id2:
                action = action_obj.browse(cursor, user, action_id2[0],
                        context=context)
                return action.action.id
        return False

Action()


class ActionKeyword(OSV):
    "Action keyword"
    _name = 'ir.action.keyword'
    _description = __doc__
    keyword = fields.Selection([
            ('tree_open', 'Open tree'),
            ('tree_action', 'Action tree'),
            ('form_print', 'Print form'),
            ('form_action', 'Action form'),
            ('form_relate', 'Form relate'),
            ], string='Keyword', required=True)
    model = fields.Reference('Model', selection='models_get', size=128)
    action = fields.many2one('ir.action', 'Action',
            ondelete='CASCADE')

    def __init__(self):
        super(ActionKeyword, self).__init__()
        self._rpc_allowed = self._rpc_allowed + [
            'get_keyword',
            'models_get',
        ]

    def _convert_vals(self, cursor, user, vals, context=None):
        vals = vals.copy()
        action_obj = self.pool.get('ir.action')
        if 'action' in vals:
            vals['action'] = action_obj.get_action_id(cursor, user,
                    vals['action'], context=context)
        return vals

    def models_get(self, cursor, user, context=None):
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search(cursor, user, [])
        res = []
        for model in model_obj.browse(cursor, user, model_ids, context=context):
            res.append([model.model, model.name])
        return res

    def unlink(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0]).fields_view_get()
            except:
                pass
        return super(ActionKeyword, self).unlink(cursor, user, ids,
                context=context)

    def create(self, cursor, user, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        if 'model' in vals:
            # Restart the cache view
            try:
                self.pool.get(vals['model'].split(',')[0]).fields_view_get()
            except:
                pass
        return super(ActionKeyword, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        if isinstance(ids, (int, long)):
            ids = [ids]
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0]).fields_view_get()
            except:
                pass
        res = super(ActionKeyword, self).write(cursor, user, ids, vals,
                context=context)
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0]).fields_view_get()
            except:
                pass
        return res

    def get_keyword(self, cursor, user, keyword, value, context=None):
        res = []
        model, model_id = value

        action_keyword_ids = []
        if model_id:
            action_keyword_ids = self.search(cursor, user, [
                ('keyword', '=', keyword),
                ('model', '=', model + ',' + str(model_id)),
                ], context=context)
        action_keyword_ids.extend(self.search(cursor, user, [
            ('keyword', '=', keyword),
            ('model', '=', model + ',0'),
            ], context=context))
        for action_keyword in self.browse(cursor, user, action_keyword_ids,
                context=context):
            try:
                action_obj = self.pool.get(action_keyword.action.type)
            except ExceptORM, exception:
                if exception.name == 'AccessError':
                    continue
                raise
            action_id = action_obj.search(cursor, user, [
                ('action', '=', action_keyword.action.id),
                ], context=context)
            if action_id:
                res.append(action_obj.read(cursor, user, action_id[0],
                    context=context))
                if action_keyword.action.type == 'ir.action.report':
                    del res[-1]['report_content_data']
                    del res[-1]['report_content']
        return res

ActionKeyword()


class ActionReport(OSV):
    "Action report"
    _name = 'ir.action.report'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    model = fields.Char('Model', size=64, required=True)
    report_name = fields.Char('Internal Name', size=64, required=True)
    report = fields.Char('Path', size=128)
    report_content_data = fields.Binary('Content')
    report_content = fields.Function('get_report_content',
        fnct_inv='report_content_inv', type='binary',
        string='Content')
    action = fields.Many2One('ir.action', 'Action', required=True)
    _sql_constraints = [
        ('report_name_uniq', 'unique (report_name)',
            'The internal name must be unique!'),
    ]

    def default_type(self, cursor, user, context=None):
        return 'ir.action.report'

    def default_report_content(self, cursor, user, context=None):
        return False

    def get_report_content(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            data = report[name + '_data']
            if not data and report[name[:-8]]:
                try:
                    data = file_open(report[name[:-8]], mode='rb').read()
                except:
                    data = False
            res[report.id] = data
        return res

    def report_content_inv(self, cursor, user, obj_id, name, value, arg,
            context=None):
        self.write(cursor, user, obj_id, {name+'_data': value}, context=context)

    def copy(self, cursor, user, object_id, default=None, context=None):
        if default is None:
            default = {}
        report = self.browse(cursor, user, object_id, context=context)
        if report.report:
            default['report_content'] = False
        default['report_name'] = report.report_name + '.copy'
        return super(ActionReport, self).copy(cursor, user, object_id,
                default=default, context=context)

ActionReport()


class ActionActWindow(OSV):
    "Action act window"
    _name = 'ir.action.act_window'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    domain = fields.Char('Domain Value', size=250)
    context = fields.Char('Context Value', size=250)
    res_model = fields.Char('Model', size=64)
    src_model = fields.Char('Source model', size=64)
    view_type = fields.Selection([('tree','Tree'), ('form','Form')],
       string='Type of view')
    usage = fields.Char('Action Usage', size=32)
    act_window_views = fields.One2Many('ir.action.act_window.view',
       'act_window', 'Views')
    views = fields.Function('views_get_fnc', type='binary',
       string='Views')
    limit = fields.Integer('Limit',
       help='Default limit for the list view')
    auto_refresh = fields.Integer('Auto-Refresh',
       help='Add an auto-refresh on the view')
    action = fields.Many2One('ir.action', 'Action', required=True)

    def default_type(self, cursor, user, context=None):
        return 'ir.action.act_window'

    def default_view_type(self, cursor, user, context=None):
        return 'form'

    def default_context(self, cursor, user, context=None):
        return '{}'

    def default_limit(self, cursor, user, context=None):
        return 80

    def default_auto_refresh(self, cursor, user, context=None):
        return 0

    def views_get_fnc(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for act in self.browse(cursor, user, ids, context=context):
            res[act.id] = [(view.view.id, view.view.type) \
                    for view in act.act_window_views]
        return res

ActionActWindow()


class ActionActWindowView(OSV):
    "Action act window view"
    _name = 'ir.action.act_window.view'
    _rec_name = 'view'
    _description = __doc__
    sequence = fields.Integer('Sequence')
    view = fields.Many2One('ir.ui.view', 'View', required=True,
            ondelete='CASCADE')
    act_window = fields.Many2One('ir.action.act_window', 'Action',
            ondelete='CASCADE')
    multi = fields.Boolean('On multiple doc.',
            help="If set to true, the action will not be displayed \n" \
                    "on the right toolbar of a form views.")
    _order = 'sequence'

    def default_multi(self, cursor, user, context=None):
        return False

ActionActWindowView()


class ActionWizard(OSV):
    "Action wizard"
    _name = 'ir.action.wizard'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    wiz_name = fields.char('Wizard name', size=64, required=True)
    action = fields.many2one('ir.action', 'Action', required=True)

    def default_type(self, cursor, user, context=None):
        return 'ir.action.wizard'

ActionWizard()


class ActionURL(OSV):
    "Action URL"
    _name = 'ir.action.url'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    url = fields.text('Action Url',required=True)
    target = fields.selection([
       ('new', 'New Window'),
       ('self', 'This Window'),
       ], 'Action Target', required=True)
    action = fields.many2one('ir.action', 'Action', required=True)

    def default_type(self, cursor, user, context=None):
        return 'ir.action.act_url'

    def default_target(self, cursor, user, context=None):
        return 'new'

ActionURL()
