# -*- coding: utf-8 -*-
{
    'name': "hr_avancys",

    'summary': """
        Nómina Colombiana""",

    'description': """
NÓMINA DE AVANCYS
=================
Este modulo provee de los procesos de nómina colombiana, controlando:
    * Ausencias.
    * Novedades.
    * Conceptos fijos.

Procesos:
---------
    * Cálculo de nómina del empleado.
    * Cálculo de autoliquidación.
    """,

    'author': "AVANCYS",
    'website': "http://www.avancys.com/",

    'category': 'Human Resources/Payroll',
    'version': '14.0.0.0',

    # any module necessary for this one to work correctly
    'depends': [
        'contacts', 
        'stock', 
        # 'base_address_city',
        # 'website_hr_recruitment', 
        # 'hr_expense',
        # 'hr_gamification', 
        # 'hr_org_chart',
        # 'hr_skills_slides', 
        # 'hr_skills_survey',
        'hr', 
        'l10n_latam_base',
    ],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'data/hr_avancys_data.xml',
        'data/res_partner_document_type_data.xml',
        'data/hr_fiscal_type_data.xml',
        'data/hr_fiscal_subtype_data.xml',
        'data/hr_concept_data.xml',
        'data/economic_variables_data.xml',
        'data/hr_leave_cause_data.xml',
        'data/res_partner_tags.xml',

        'views/hr_payslip_noveltys/model_basic_payslip_novelty_type.xml',
        'views/hr_payslip_noveltys/model_basic_payslip_novelty.xml',
        'views/hr_payslip_noveltys/hr_novelty_type.xml',
        'views/hr_payslip_noveltys/hr_novelty.xml',
        'views/hr_payslip_noveltys/hr_leave_type.xml',
        'views/hr_payslip_noveltys/hr_leave.xml',
        'views/hr_payslip_noveltys/hr_overtime_type.xml',
        'views/hr_payslip_noveltys/hr_overtime.xml',

        'views/hr_payslip_period/hr_period.xml',
        'views/hr_payslip_period/hr_period_creator.xml',

        'views/hr_payslip/hr_concept.xml',
        'views/hr_payslip/hr_payslip_line.xml',
        'views/hr_payslip/hr_payslip_processing.xml',
        'views/hr_payslip/hr_payslip_type.xml',
        'views/hr_payslip/hr_payslip.xml',

        'views/hr_contract/hr_contract.xml',
        'views/hr_contract/hr_contract_type.xml',
        'views/hr_contract/hr_contract_group.xml',
        'views/hr_contract/eps_update_history.xml',
        'views/hr_contract/pension_update_history.xml',
        'views/hr_contract/severance_update_history.xml',
        'views/hr_contract/wage_update_history.xml',
        'views/hr_contract/hr_equipment.xml',
        'views/hr_contract/resource_calendar.xml',

        'views/res_partner.xml',
        'views/hr_employee.xml',
        'views/res_config_settings.xml',
        'views/res_company.xml',

        'views/economic_variables/economic_variables.xml',
        'views/economic_variables/economic_variables_line.xml',
        'views/economic_variables/economic_variables_line_detail.xml',

        'views/hr_contribution_form/hr_contribution_form.xml',
        'views/hr_contribution_form/hr_contribution_form_line.xml',

    ],

    'installable': True,
    'auto_install': False,
    'application': True,
    'pre_init_hook': "pre_init_hook",
    'post_init_hook': "post_init_hook",
    'uninstall_hook': "uninstall_hook",
}
