# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

{
    'name': "Loyalty Points Extension",
    'version': '19.0.1.7.0',
    'category': 'Sales/Sales',
    'summary': "Points recovered on credit notes, and a points statement on the card report and email",
    'author': "Anis Alim",
    'maintainer': "Anis Alim",
    'depends': ['sale_loyalty', 'account', 'base_automation'],
    'data': [
        'data/report_paperformat.xml',
        'data/loyalty_card_automation.xml',
        'report/points_statement_templates.xml',
        'data/mail_template_data.xml',
        'views/loyalty_program_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aa_loyalty_points/static/src/scss/coupon_dialog.scss',
        ],
    },
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'installable': True,
}
