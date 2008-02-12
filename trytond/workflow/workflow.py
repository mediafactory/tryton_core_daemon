"Workflow"
import os
from trytond.osv import fields, OSV, ExceptOSV
from trytond.netsvc import LocalService
from trytond.report import Report
from trytond.tools import exec_command_pipe


class Workflow(OSV):
    "Workflow"
    _name = "workflow"
    _table = "wkf"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'osv': fields.char('Resource Model', size=64, required=True),
        'on_create': fields.boolean('On Create'),
        'activities': fields.one2many('workflow.activity', 'wkf_id',
            'Activities'),
    }
    _defaults = {
        'on_create': lambda *a: True
    }

    def write(self, cursor, user, ids, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor, user)
        return super(Workflow, self).write(cursor, user, ids, vals,
                context=context)

    def create(self, cursor, user, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor, user)
        return super(Workflow, self).create(cursor, user, vals,
                context=context)

Workflow()


class WorkflowActivity(OSV):
    "Workflow activity"
    _name = "workflow.activity"
    _table = "wkf_activity"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'wkf_id': fields.many2one('workflow', 'Workflow', required=True,
            select=1, ondelete='cascade'),
        'split_mode': fields.selection([
            ('XOR', 'Xor'),
            ('OR', 'Or'),
            ('AND', 'And'),
            ], 'Split Mode', size=3, required=True),
        'join_mode': fields.selection([
            ('XOR', 'Xor'),
            ('AND', 'And'),
            ], 'Join Mode', size=3, required=True),
        'kind': fields.selection([
            ('dummy', 'Dummy'),
            ('function', 'Function'),
            ('subflow', 'Subflow'),
            ('stopall', 'Stop All'),
            ], 'Kind', size=64, required=True),
        'action': fields.char('Action', size=64),
        'flow_start': fields.boolean('Flow Start'),
        'flow_stop': fields.boolean('Flow Stop'),
        'subflow_id': fields.many2one('workflow', 'Subflow'),
        'signal_send': fields.char('Signal (subflow.*)', size=32),
        'out_transitions': fields.one2many('workflow.transition', 'act_from',
            'Outgoing transitions'),
        'in_transitions': fields.one2many('workflow.transition', 'act_to',
            'Incoming transitions'),
    }
    _defaults = {
        'kind': lambda *a: 'dummy',
        'join_mode': lambda *a: 'XOR',
        'split_mode': lambda *a: 'XOR',
    }

WorkflowActivity()


class WorkflowTransition(OSV):
    "Workflow transition"
    _table = "wkf_transition"
    _name = "workflow.transition"
    _log_access = False
    _rec_name = 'signal'
    _description = __doc__
    _columns = {
        'trigger_model': fields.char('Trigger Type', size=128),
        'trigger_expr_id': fields.char('Trigger Expr ID', size=128),
        'signal': fields.char('Signal (button Name)', size=64),
        'group': fields.many2one('res.group', 'Group Required'),
        'condition': fields.char('Condition', required=True, size=128),
        'act_from': fields.many2one('workflow.activity', 'Source Activity',
            required=True, select=1, ondelete='cascade'),
        'act_to': fields.many2one('workflow.activity', 'Destination Activity',
            required=True, select=1, ondelete='cascade'),
    }
    _defaults = {
        'condition': lambda *a: 'True',
    }

WorkflowTransition()


class WorkflowInstance(OSV):
    "Workflow instance"
    _table = "wkf_instance"
    _name = "workflow.instance"
    _rec_name = 'res_type'
    _log_access = False
    _description = __doc__
    _columns = {
        'wkf_id': fields.many2one('workflow', 'Workflow', ondelete="restrict"),
        'uid': fields.integer('User ID'),
        'res_id': fields.integer('Resource ID'),
        'res_type': fields.char('Resource Model', size=64),
        'state': fields.char('State', size=32),
    }

    def _auto_init(self, cursor, module_name):
        super(WorkflowInstance, self)._auto_init(cursor, module_name)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = ' \
                    '\'wkf_instance_res_id_res_type_state_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX ' \
                        'wkf_instance_res_id_res_type_state_index ' \
                    'ON wkf_instance (res_id, res_type, state)')
            cursor.commit()

WorkflowInstance()


class WorkflowWorkitem(OSV):
    "Workflow workitem"
    _table = "wkf_workitem"
    _name = "workflow.workitem"
    _log_access = False
    _rec_name = 'state'
    _description = __doc__
    _columns = {
        'act_id': fields.many2one('workflow.activity', 'Activity',
            required=True, ondelete="cascade"),
        'subflow_id': fields.many2one('workflow.instance', 'Subflow',
            ondelete="cascade"),
        'inst_id': fields.many2one('workflow.instance', 'Instance',
            required=True, ondelete="cascade", select=1),
        'state': fields.char('State', size=64),
    }

WorkflowWorkitem()


class WorkflowTrigger(OSV):
    "Workflow trigger"
    _table = "wkf_triggers"
    _name = "workflow.triggers"
    _log_access = False
    _description = __doc__
    _columns = {
        'res_id': fields.integer('Resource ID', size=128),
        'model': fields.char('Model', size=128),
        'instance_id': fields.many2one('workflow.instance',
            'Destination Instance', ondelete="cascade"),
        'workitem_id': fields.many2one('workflow.workitem', 'Workitem',
            required=True, ondelete="cascade"),
    }

    def _auto_init(self, cursor, module_name):
        super(WorkflowTrigger, self)._auto_init(cursor, module_name)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = \'wkf_triggers_res_id_model_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX wkf_triggers_res_id_model_index ' \
                    'ON wkf_triggers (res_id, model)')
            cursor.commit()

WorkflowTrigger()


class InstanceGraph(Report):
    _name = 'workflow.instance.graph'

    def execute(self, cursor, user, ids, datas, context=None):
        import pydot
        workflow_obj = self.pool.get('workflow')
        instance_obj = self.pool.get('workflow.instance')
        workflow_id = workflow_obj.search(cursor, user, [
            ('osv', '=', datas['model']),
            ], limit=1, context=context)
        if not workflow_id:
            raise ExceptOSV('UserError', 'No workflow defined!')
        workflow_id = workflow_id[0]
        workflow = workflow_obj.browser(cursor, user, workflow_id,
                context=context)
        instance_id = instance_obj.search(cursor, user, [
            ('res_id', '=', datas['id']),
            ('wkf_id', '=', workflow.id),
            ], limit=1, context=context)
        if not instance_id:
            raise ExceptOSV('UserError', 'No workflow instance defined!')
        instance_id = instance_id[0]

        graph = pydot.Dot(fontsize=16,
                label="\\n\\nWorkflow: %s\\n OSV: %s" % \
                        (worflow.name, workflow.osv))
        graph.set('size', '10.7,7.3')
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        graph.set('rotate', '90')
        graph.set('rankdir', 'LR') #TODO depend of the language
        self.graph_instance_get(cursor, graph, instance_id,
                datas.get('nested', False), context=context)
        ps_string = graph.create(prog='dot', format='ps')

        if os.name == 'nt':
            prog = 'ps2pdf.bat'
        else:
            prog = 'ps2pdf'
        args = (prog, '-', '-')
        inpt, oupt = exec_command_pipe(*args)
        inpt.write(ps_string)
        inpt.close()
        data = outpt.read()
        outpt.close()
        return ('pdf', base64.encodestring(data))

    def graph_instance_get(self, cursor, graph, instance_id, nested=False,
            context=None):
        instance_obj = self.pool.get('workflow.instance')
        instance = instance_obj.browse(cursor, user, instance_id,
                context=context)
        self.graph_get(cursor, user, graph, instance.wkf_id.id, nested,
                self.workitem_get(cursor, user, instance.id, context=context),
                context=context)

    def workitem_get(self, cursor, user, instance_id, context=None):
        res = {}
        workitem_obj = self.pool.get('workflow.workitem')
        workitem_ids = workitem_obj.search(cursor, user, [
            ('inst_id', '=', instance_id),
            ], context=context)
        workitems = workitem_obj.browse(cursor, user, workitem_ids,
                context=context)
        for workitem in workitems:
            res.setdefault(workitem.act_id.id, 0)
            res[workitem.act_id.id] += 1
            if workitem.subflow_id:
                res.update(self.workitem_get(cursor, user,
                    workitem.subflow_id.id, context=context))
        return res

    def graph_get(self, cursor, user, graph, workflow_id, nested=False,
            workitem=None, context=None):
        import pydot
        if workitem is None:
            workitem = {}
        activity_obj = self.pool.get('workfow.activity')
        workflow_obj = self.pool.get('workflow')
        transition_obj = self.pool.get('workflow.transition')
        activity_ids = activity_obj.search(cursor, user, [
            ('wkf_id', '=', workflow_id),
            ], context=context)
        id2activities = {}
        actfrom = {}
        actto = {}
        activities = activity_obj.browse(cursor, user, activity_ids,
                context=context)
        start = 0
        stop = {}
        for activity in activities:
            if activity.flow_start:
                start = activity.id
            if activity.flow_stop:
                stop['subflow.' + activity.name] =  activity.id
            id2activities[activity.id] = activity
            if activity.subflow_id and nested:
                workflow = workflow_obj.browse(cursor, user,
                        activity.subflow_id.id, context=context)
                subgraph = pydot.Cluster('subflow' + str(workflow.id),
                        fontsize=12, label="Subflow: " + activity.name + \
                                '\\nOSV: ' + workflow.osv)
                (substart, substop) = self.graph_get(cursor, user,
                        subgraph, workflow.id, nested, workitem,
                        context=context)
                graph.add_subgraph(subgraph)
                actfrom[activity.id] = substart
                actto[activity.id] = substop
            else:
                args = {}
                if activity.flow_start or activity.flow_stop:
                    args['style'] = 'filled'
                    args['color'] = 'lightgrey'
                args['label'] = activity.name
                if activity.subflow_id:
                    args['shape'] = 'box'
                if activity.id in workitem:
                    args['label'] += '\\nx ' + str(workitem[activity.id])
                    args['color'] = 'red'
                graph.add_node(pydot.Node(activity.id, **args))
                actfrom[activity.id] = (activity.id, {})
                actto[activity.id] = (activity.id, {})
        transition_ids = transition_obj.search(cursor, user, [
            ('act_from', 'in', [x.id for x in activities]),
            ], context=context)
        transitions = transition_obj.browse(cursor, user, transition_ids,
                context=context)
        for transition in transitions:
            args = {}
            args['label'] = str(transition.condition).replace(' or ',
                    '\\nor ').replace(' and ', '\\nand ')
            if transition.signal:
                args['label'] += '\\n' + str(transition.signal)
                args['style'] = 'bold'
            if id2activities[transition.act_from.id].split_mode == 'AND':
                args['arrowtail'] = 'box'
            elif id2activities[transition.act_from.id].split_mode == 'OR':
                args['arrowtail'] = 'inv'
            if id2activities[transition.act_to.id].join_mode == 'AND':
                args['arrowhead'] = 'crow'

            activity_from = actfrom[transition.act_from.id][1].get(
                    transition.signal, actfrom[transition.act_from.id][0])
            activity_to = actto[transition.act_to.id][1].get(
                    transition.signal, actto[transition.act_to.id][0])
            graph.add_edge(pydot.Edge(activity_from, activity_to,
                fontsize=10, **args))
        return ((start, {}), (stop.values()[0], stop))

InstanceGraph()
