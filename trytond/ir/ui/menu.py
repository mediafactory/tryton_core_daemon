"UI menu"
from trytond.osv import fields, OSV

def one_in(i, j):
    """Check the presence of an element of setA in setB
    """
    for k in i:
        if k in j:
            return True
    return False

ICONS = [(x, x) for x in [
    'STOCK_ABOUT',
    'STOCK_ADD',
    'STOCK_APPLY',
    'STOCK_BOLD',
    'STOCK_CANCEL',
    'STOCK_CDROM',
    'STOCK_CLEAR',
    'STOCK_CLOSE',
    'STOCK_COLOR_PICKER',
    'STOCK_CONNECT',
    'STOCK_CONVERT',
    'STOCK_COPY',
    'STOCK_CUT',
    'STOCK_DELETE',
    'STOCK_DIALOG_AUTHENTICATION',
    'STOCK_DIALOG_ERROR',
    'STOCK_DIALOG_INFO',
    'STOCK_DIALOG_QUESTION',
    'STOCK_DIALOG_WARNING',
    'STOCK_DIRECTORY',
    'STOCK_DISCONNECT',
    'STOCK_DND',
    'STOCK_DND_MULTIPLE',
    'STOCK_EDIT',
    'STOCK_EXECUTE',
    'STOCK_FILE',
    'STOCK_FIND',
    'STOCK_FIND_AND_REPLACE',
    'STOCK_FLOPPY',
    'STOCK_GOTO_BOTTOM',
    'STOCK_GOTO_FIRST',
    'STOCK_GOTO_LAST',
    'STOCK_GOTO_TOP',
    'STOCK_GO_BACK',
    'STOCK_GO_DOWN',
    'STOCK_GO_FORWARD',
    'STOCK_GO_UP',
    'STOCK_HARDDISK',
    'STOCK_HELP',
    'STOCK_HOME',
    'STOCK_INDENT',
    'STOCK_INDEX',
    'STOCK_ITALIC',
    'STOCK_JUMP_TO',
    'STOCK_JUSTIFY_CENTER',
    'STOCK_JUSTIFY_FILL',
    'STOCK_JUSTIFY_LEFT',
    'STOCK_JUSTIFY_RIGHT',
    'STOCK_MEDIA_FORWARD',
    'STOCK_MEDIA_NEXT',
    'STOCK_MEDIA_PAUSE',
    'STOCK_MEDIA_PLAY',
    'STOCK_MEDIA_PREVIOUS',
    'STOCK_MEDIA_RECORD',
    'STOCK_MEDIA_REWIND',
    'STOCK_MEDIA_STOP',
    'STOCK_MISSING_IMAGE',
    'STOCK_NETWORK',
    'STOCK_NEW',
    'STOCK_NO',
    'STOCK_OK',
    'STOCK_OPEN',
    'STOCK_PASTE',
    'STOCK_PREFERENCES',
    'STOCK_PRINT',
    'STOCK_PRINT_PREVIEW',
    'STOCK_PROPERTIES',
    'STOCK_QUIT',
    'STOCK_REDO',
    'STOCK_REFRESH',
    'STOCK_REMOVE',
    'STOCK_REVERT_TO_SAVED',
    'STOCK_SAVE',
    'STOCK_SAVE_AS',
    'STOCK_SELECT_COLOR',
    'STOCK_SELECT_FONT',
    'STOCK_SORT_ASCENDING',
    'STOCK_SORT_DESCENDING',
    'STOCK_SPELL_CHECK',
    'STOCK_STOP',
    'STOCK_STRIKETHROUGH',
    'STOCK_UNDELETE',
    'STOCK_UNDERLINE',
    'STOCK_UNDO',
    'STOCK_UNINDENT',
    'STOCK_YES',
    'STOCK_ZOOM_100',
    'STOCK_ZOOM_FIT',
    'STOCK_ZOOM_IN',
    'STOCK_ZOOM_OUT',
    'terp-account',
    'terp-crm',
    'terp-mrp',
    'terp-product',
    'terp-purchase',
    'terp-sale',
    'terp-tools',
    'terp-administration',
    'terp-hr',
    'terp-partner',
    'terp-project',
    'terp-report',
    'terp-stock',
    'terp-calendar',
    'terp-graph',
]]


class Many2ManyUniq(fields.Many2Many):

    def set(self, cursor, obj, obj_id, name, values, user=None, context=None):
        if not values:
            return
        val = values[:]
        for act in values:
            if act[0] == 4:
                cursor.execute('SELECT * FROM ' + self._rel + ' ' \
                        'WHERE ' + self._id1 + ' = %d ' \
                            'AND ' + self._id2 + ' = %d',
                        (obj_id, act[1]))
                if cursor.fetchall():
                    val.remove(act)
        return super(Many2ManyUniq, self).set(cursor, obj, obj_id, name, val,
                user=user, context=context)


class UIMenu(OSV):
    "UI menu"
    _name = 'ir.ui.menu'
    _description = __doc__

    def search(self, cursor, user, args, offset=0, limit=2000, order=None,
            context=None, count=False):
        res_user_obj = self.pool.get('res.user')
        if context is None:
            context = {}
        ids = super(UIMenu, self).search(cursor, user, args, offset, limit,
                order, context=context)
        user_groups = res_user_obj.read(cursor, user, [user])[0]['groups_id']
        result = []
        for menu in self.browse(cursor, user, ids):
            if not len(menu.groups_id):
                result.append(menu.id)
                continue
            for group in menu.groups_id:
                if group.id in user_groups:
                    result.append(menu.id)
                    break
        if count:
            return len(result)
        return result

    def _get_full_name(self, cursor, user, ids, name, args, context):
        res = {}
        for menu in self.browse(cursor, user, ids):
            res[menu.id] = self._get_one_full_name(menu)
        return res

    def _get_one_full_name(self, menu, level=6):
        if level <= 0:
            return '...'
        if menu.parent_id:
            parent_path = self._get_one_full_name(menu.parent_id, level-1) + "/"
        else:
            parent_path = ''
        return parent_path + menu.name

    def copy(self, cursor, user, obj_id, default=None, context=None):
        ir_values_obj = self.pool.get('ir.values')
        res = super(UIMenu, self).copy(cursor, user, obj_id, context=context)
        ids = ir_values_obj.search(cursor, user, [
            ('model', '=', 'ir.ui.menu'),
            ('res_id', '=', obj_id),
            ])
        for ir_value in ir_values_obj.browse(cursor, user, ids):
            ir_values_obj.copy(cursor, user, ir_value.id,
                    default={'res_id': res}, context=context)
        return res

    def _action(self, cursor, user, ids, name, arg, context=None):
        res = {}
        values_obj = self.pool.get('ir.values')
        value_ids = values_obj.search(cursor, user, [
            ('model', '=', self._name), ('key', '=', 'action'),
            ('key2', '=', 'tree_but_open'), ('res_id', 'in', ids)],
            context=context)
        values_action = {}
        for value in values_obj.browse(cursor, user, value_ids,
                context=context):
            values_action[value.res_id] = value.value
        for menu_id in ids:
            res[menu_id] = values_action.get(menu_id, False)
        return res

    def _action_inv(self, cursor, user, menu_id, name, value, arg,
            context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        if 'read_delta' in ctx:
            del ctx['read_delta']
        values_obj = self.pool.get('ir.values')
        values_ids = values_obj.search(cursor, user, [
            ('model', '=', self._name), ('key', '=', 'action'),
            ('key2', '=', 'tree_but_open'), ('res_id', '=', menu_id)],
            context=context)
        if values_ids:
            values_obj.write(cursor, user, values_ids[0], {'value': value},
                    context=ctx)
        else:
            values_obj.create(cursor, user, {
                'name': 'Menuitem',
                'model': self._name,
                'value': value,
                'object': True,
                'key': 'action',
                'key2': 'tree_but_open',
                'res_id': menu_id,
                }, context=ctx)

    _columns = {
        'name': fields.char('Menu', size=64, required=True, translate=True),
        'sequence': fields.integer('Sequence'),
        'child_id' : fields.one2many('ir.ui.menu', 'parent_id','Child ids'),
        'parent_id': fields.many2one('ir.ui.menu', 'Parent Menu', select=True),
        'groups_id': Many2ManyUniq('res.group', 'ir_ui_menu_group_rel',
            'menu_id', 'gid', 'Groups'),
        'complete_name': fields.function(_get_full_name, method=True,
            string='Complete Name', type='char', size=128),
        'icon': fields.selection(ICONS, 'Icon', size=64),
        'action': fields.function(_action, fnct_inv=_action_inv,
            method=True, type='reference', string='Action',
            selection=[
                ('ir.actions.report.custom', 'ir.actions.report.custom'),
                ('ir.actions.report.xml', 'ir.actions.report.xml'),
                ('ir.actions.act_window', 'ir.actions.act_window'),
                ('ir.actions.wizard', 'ir.actions.wizard'),
                ]),
    }
    _defaults = {
        'icon' : lambda *a: 'STOCK_OPEN',
        'sequence' : lambda *a: 10,
    }
    _order = "sequence, id"

UIMenu()


