"Rule"
from trytond.osv import fields, OSV
from trytond.tools import Cache
import time


class RuleGroup(OSV):
    "Rule group"
    _name = 'ir.rule.group'
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=128, select=1),
        'model_id': fields.many2one('ir.model', 'Model', select=1,
            required=True),
        'global': fields.boolean('Global', select=1,
            help="Make the rule global \n" \
                    "or it needs to be put on a group or user"),
        'rules': fields.one2many('ir.rule', 'rule_group', 'Tests',
            help="The rule is satisfied if at least one test is True"),
        'groups': fields.many2many('res.groups', 'group_rule_group_rel',
            'rule_group_id', 'group_id', 'Groups'),
        'users': fields.many2many('res.users', 'user_rule_group_rel',
            'rule_group_id', 'user_id', 'Users'),
    }
    _order = 'model_id, global DESC'
    _defaults = {
        'global': lambda *a: True,
    }

    def unlink(self, cursor, user, ids, context=None):
        res = super(RuleGroup, self).unlink(cursor, user, ids,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(RuleGroup, self).create(cursor, user, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(RuleGroup, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

RuleGroup()


class Rule(OSV):
    "Rule"
    _name = 'ir.rule'
    _rec_name = 'field_id'
    _description = __doc__

    def _operand(self, cursor, user, context):

        def get(obj_name, level=3, recur=None, root_tech='', root=''):
            res = []
            if not recur:
                recur = []
            obj_fields = self.pool.get(obj_name).fields_get(cursor, user)
            key = obj_fields.keys()
            key.sort()
            for k in key:

                if obj_fields[k]['type'] in ('many2one'):
                    res.append((root_tech + '.' + k + '.id',
                        root + '/' + obj_fields[k]['string']))

                elif obj_fields[k]['type'] in ('many2many', 'one2many'):
                    res.append(('\',\'.join(map(lambda x: str(x.id), ' + \
                            root_tech + '.' + k + '))',
                        root + '/' + obj_fields[k]['string']))

                else:
                    res.append((root_tech + '.' + k,
                        root + '/' + obj_fields[k]['string']))

                if (obj_fields[k]['type'] in recur) and (level>0):
                    res.extend(get(obj_fields[k]['relation'], level-1,
                        recur, root_tech + '.' + k, root + '/' + \
                                obj_fields[k]['string']))

            return res

        res = [("False", "False"), ("True", "True"), ("user.id", "User")]
        res += get('res.users', level=1,
                recur=['many2one'], root_tech='user', root='User')
        return res

    _columns = {
        'field_id': fields.many2one('ir.model.fields', 'Field',
            domain="[('model_id','=', parent.model_id)]", select=1,
            required=True),
        'operator':fields.selection([
            ('=', '='),
            ('<>', '<>'),
            ('<=', '<='),
            ('>=', '>='),
            ('in', 'in'),
            ('child_of', 'child_of'),
            ], 'Operator', required=True),
        'operand':fields.selection(_operand,'Operand', size=64, required=True),
        'rule_group': fields.many2one('ir.rule.group', 'Group', select=2,
            required=True, ondelete="cascade")
    }

    def domain_get(self, cursor, user, model_name):
        # root user above constraint
        if user == 1:
            return '', []

        cursor.execute("SELECT r.id FROM ir_rule r " \
                "JOIN (ir_rule_group g " \
                    "JOIN ir_model m ON (g.model_id = m.id)) " \
                    "ON (g.id = r.rule_group) " \
                "WHERE m.model = %s "
                    "AND (g.id IN (" \
                            "SELECT rule_group_id FROM user_rule_group_rel " \
                                "WHERE user_id = %d " \
                            "UNION SELECT rule_group_id " \
                                "FROM group_rule_group_rel g_rel " \
                                "JOIN res_groups_users_rel u_rel " \
                                    "ON (g_rel.group_id = u_rel.gid) " \
                                "WHERE u_rel.uid = %d) "
                    "OR g.global)", (model_name, user, user))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            return '', []
        obj = self.pool.get(model_name)
        clause = {}
        clause_global = {}
        # Use root user to prevent recursion
        for rule in self.browse(cursor, 1, ids):
            if rule.operator in ('in', 'child_of'):
                dom = eval("[('%s', '%s', [%s])]" % \
                        (rule.field_id.name, rule.operator, rule.operand),
                        {'user': self.pool.get('res.users').browse(cursor, 1,
                            user), 'time': time})
            else:
                dom = eval("[('%s', '%s', %s)]" % \
                        (rule.field_id.name, rule.operator, rule.operand),
                        {'user': self.pool.get('res.users').browse(cursor, 1,
                            user), 'time': time})

            if rule.rule_group['global']:
                clause_global.setdefault(rule.rule_group.id, [])
                clause_global[rule.rule_group.id].append(
                        obj._where_calc(cursor, user, dom, active_test=False))
            else:
                clause.setdefault(rule.rule_group.id, [])
                clause[rule.rule_group.id].append(
                        obj._where_calc(cursor, user, dom, active_test=False))

        def _query(clauses, test):
            query = ''
            val = []
            for groups in clauses.values():
                if not groups:
                    continue
                if len(query):
                    query += ' '+test+' '
                query += '('
                first = True
                for group in groups:
                    if not first:
                        query += ' OR '
                    first = False
                    query += '('
                    first2 = True
                    for clause in group[0]:
                        if not first2:
                            query += ' AND '
                        first2 = False
                        query += clause
                    query += ')'
                    val += group[1]
                query += ')'
            return query, val

        query = ''
        val = []

        # Test if there is no rule_group that have no rule
        cursor.execute("""SELECT g.id FROM
            ir_rule_group g
                JOIN ir_model m ON (g.model_id = m.id)
            WHERE m.model = %s
                AND (g.id NOT IN (SELECT rule_group FROM ir_rule))
                AND (g.id IN (SELECT rule_group_id FROM user_rule_group_rel
                    WHERE user_id = %d
                    UNION SELECT rule_group_id FROM group_rule_group_rel g_rel
                        JOIN res_groups_users_rel u_rel
                            ON g_rel.group_id = u_rel.gid
                        WHERE u_rel.user = %d))""", (model_name, user, user))
        if not cursor.fetchall():
            query, val = _query(clause, 'OR')

        query_global, val_global = _query(clause_global, 'AND')
        if query_global:
            if query:
                query = '('+query+') AND '+query_global
                val.extend(val_global)
            else:
                query = query_global
                val = val_global

        return query, val
    domain_get = Cache()(domain_get)

    def unlink(self, cursor, user, ids, context=None):
        res = super(Rule, self).unlink(cursor, user, ids, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(Rule, self).create(cursor, user, vals, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get()
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Rule, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.domain_get()
        return res

Rule()
