# -*- coding: utf-8 -*-

from . import models

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    remove_view_menu = ['l10n_latam_base.view_partner_latam_form',
                        'hr.menu_hr_employee', 'hr.menu_hr_department_tree', 'hr.menu_hr_main']
    change_parent_menu = {
        'hr.menu_hr_department_kanban': 'hr.menu_human_resources_configuration'}
    for view in remove_view_menu:
        try:
            view_id = env.ref(view)
            view_id.unlink()
        except ValueError as e:
            _logger.warning(e)
    for menu in change_parent_menu:
        try:
            parent = change_parent_menu[menu]
            env.ref(menu).write({'parent_id': env.ref(parent).id})
        except ValueError as e:
            _logger.warning(e)
    return


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu_root_old = 'hr.menu_hr_root'
    menu_root_new = 'hr_avancys.hr_avancys_menu_root'
    try:
        menu_old = env.ref(menu_root_old)
        menu_new = env.ref(menu_root_new)
        menu_new.write({
            'groups_id': [(6, 0, menu_old.groups_id.ids)],
            'child_id': [(6, 0, list(dict.fromkeys(menu_old.child_id.ids + menu_new.child_id.ids)))],
            'web_icon': menu_old.web_icon,
            'web_icon_data': menu_old.web_icon_data,
        })
        menu_old.unlink()
    except ValueError as e:
        _logger.warning(e)
    return


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    dependencies = ['hr', 'l10n_co']
    try:
        _logger.warning('hola')
        # env['ir.module.module'].search([('name','=','base')]).button_immediate_upgrade()
        env['ir.module.module'].search(
            [('name', 'in', dependencies)]).write({'state': 'to upgrade'})
    except ValueError as e:
        _logger.warning(e)
    return
