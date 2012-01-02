.. _ref-wizard:
.. module:: trytond.wizard

======
Wizard
======

A wizard is a `finite state machine`_.

There is also a more :ref:`practical introduction into wizards
<topics-wizard>`.

.. _`finite state machine`: http://en.wikipedia.org/wiki/Finite-state_machine

.. class:: Wizard()

    This is the base for any wizard. It contains the engine for the finite
    state machine. A wizard must have some :class:`State` instance attributes
    that the engine will use.

Class attributes are:

.. attribute:: Wizard._name

    It contains the unique name to reference the wizard throughout the
    platform.

.. attribute:: Wizard.start_state

    It contains the name of the starting state.

.. attribute:: Wizard.end_state

    It contains the name of the ending state.

.. attribute:: Wizard._rpc

    Same as :attribute:`trytond.model.Model._rpc`.

.. attribute:: Wizard.states

    It contains a dictionary with state name as key and :class:`State` as
    value.

Instance methods are:

.. method:: Wizard.init(module_name)

    Register the wizard.

.. method:: Wizard.create()

    Create a session for the wizard and returns a tuple containing the session
    id, the starting and ending state.

.. method:: Wizard.delete(session_id)

    Delete the session.

.. method:: Wizard.execute(session, data, state_name)

    Execute the wizard for the state.
    `session` can be an instance of :class:`Session` or a session id.
    `data` is a dictionary with the session data to update.
    `active_id`, `active_ids` and `active_model` must be set in the context
    according to the records on which the wizard is run.

=======
Session
=======

.. class:: Session(wizard, session_id)

    A wizard session contains values of each :class:`StateView` associated to
    the wizard.

Instance attributes are:

.. attribute:: Session.data

    Raw storage of session data.

Instance methods are:

.. method:: Session.save()

    Save the session in database.

=====
State
=====

.. class:: State()

    This is the base for any wizard state.

=========
StateView
=========

.. class:: StateView(model_name, view, buttons)

    A :class:`StateView` is a state that will display a form in the client.
    The form is defined by the :class:`~trytond.model.ModelView` with the name
    `model_name`, the `XML` id in `view` and the `buttons`.

Instance attributes are:

.. attribute:: StateView.model_name

    The name of the :class:`~trytond.model.ModelView`.

.. attribute:: StateView.view

    The `XML` id of the form view.

.. attribute:: StateView.buttons

    The list of :class:`Button` instances to display on the form.

Instance methods are:

.. method:: StateView.get_view

    Returns the view definition like
    :method:`~trytond.model.ModelView.fields_view_get`.

.. method:: StateView.get_defaults(wizard, session, state_name, fields)

    Return default values for the fields.

    * wizard is a :class:`Wizard` instance
    * session is a :class:`Session` instance
    * state_name is the name of the :class:`State`
    * fields is the list of field names

.. method:: StateView.get_buttons(wizard, state_name)

    Returns button definitions of the wizard.

    * wizard is a :class:`Wizard` instance
    * state_name is the name of the :class:`StateView` instance

===============
StateTransition
===============

.. class:: StateTransition()

    A :class:`StateTransition` brings the wizard to the `state` returned by the
    method having the same name as the state but starting with `transition_`.

===========
StateAction
===========

.. class:: StateAction(action_id)

    A :class:`StateAction` is a :class:`StateTransition` which let the client
    launch an `ir.action`. This action definition can be customized with a
    method on wizard having the same name as the state but starting with `do_`.

Instance attributes are:

.. attribute:: StateAction.action_id

    The `XML` id of the `ir.action`.

Instance methods are:

.. method:: StateAction.get_action()

    Returns the `ir.action` definition.

======
Button
======

.. class:: Button(string, state[, icon[, default]])

    A :class:`Button` is a single object containing the definition of a wizard
    button.

Instance attributes are:

.. attribute:: Button.string

    The label display on the button.

.. attribute:: Button.state

    The next state to reach if button is clicked.

.. attribute:: Button.icon

    The name of the icon to display on the button.

.. attribute:: Button.default

    A boolean to set it as default on the form.
