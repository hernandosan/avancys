# -*- coding: utf-8 -*-
{
    'name': "account_avancys",

    'summary': """
        Modulo Contabilidad Avancys""",

    'description': """
CONTABILIDAD AVANCYS
=================
En este modulo se maneja:
    * Impuestos.
    * Ordenes de Pago
    * Ordenes de Cobro
    * Anticipos a Proveedores
    * Anticipos a Clientes

Procesos:
---------
    * Cálculo de impuestos para facturas de ventas y compra.
    """,

    'author': "AVANCYS",
    'website': "http://www.avancys.com/",

    'category': 'Accounting/Accounting',
    'version': '14.0.0.0',

    # any module necessary for this one to work correctly
    'depends': [
        # 'base', 
        'account', 
        'sale', 
        'account_payment_mode', 
        'product', 
        'analytic', 
        # 'web_tour'
    ],

    # always loaded
    'data': [
        # Views
        'views/account_fiscal_position/account_fiscal_position_tax.xml',
        'views/product_product_avancys/product_product.xml',
        'views/account_tax/account_tax.xml',
        'views/res_config_settings/res_config_settings.xml',
        'views/account_move/account_move.xml',
        'views/res_ciiu/res_ciiu.xml',
        'views/account_analytic_account/account_analytic_account.xml',
        'views/res_partner/res_partner.xml',
        'views/account_advance/account_advance_supplier.xml',
        'views/account_advance/account_advance_customer.xml',
        'views/account_journal/account_journal.xml',
        'views/account_financial_reports/account_financial_structure.xml',
        'views/account_account/account_account_type.xml',

        # Wizards
        'wizards/account_financial_reports/account_financial_report_balance_wizard_view.xml',
        'wizards/account_financial_reports/account_financial_report_assistant_wizard_view.xml',
        'wizards/account_financial_reports/account_financial_report_taxes_wizard_view.xml',
        'wizards/account_financial_reports/excel_report_avancys_wizard.xml',

        # Security
        'security/ir.model.access.csv',

        # Sequences
        'views/account_advance/sequences/account_advance_sequence.xml',

    ],

    'installable': True,
    'auto_install': False,
    'application': True,
}
