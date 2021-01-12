# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
{
    'name': "Facturación Electrónica DIAN",
    'summary': """
        Facturación Electrónica DIAN""",
    'description': """
        Envio de facturas y notas electrónicas, por Avancys SAS como
        proveedor tecnológico o por software propio.  
    """,
    'author': "Avancys SAS",
    'website': "http://www.avancys.com",
    'category': 'Accounting/Accounting',
    'version': '14.0.0.0',
    'depends': [
        # 'account_accountant', 
        'sale'
    ],
    'license': 'OEEL-1',
    'installable': True,
    'data': [
        'data/data.xml',
        # 'data/res.country.state.csv',
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/ei_multi_process.xml',
        'wizard/ei_state_reset.xml',
        'views/res_company.xml',
        'views/electronic_invoice_resolution.xml',
        'views/account_journal.xml',
        'views/account_move.xml',
        'views/account_tax.xml',
        'views/uom_uom.xml',
        'views/sale_order.xml',
        'templates/customer_acknowledge_email.xml',
        'templates/customer_acknowledge_response.xml',
        'templates/electronic_invoice.xml',
        'report/electronic_invoice_report.xml',
    ],
}
