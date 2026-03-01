
{
    'name': 'Field Service Spare Parts Management',
    'version': '18.0.1.0.0',
    'category': 'Field Service',
    'summary': 'Manage spare parts in FSM orders with warranty and agreement checks',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': [
        'fieldservice',
        'fieldservice_equipment_stock',
        'fieldservice_equipment_warranty',
        'fieldservice_agreement',
        'agreement',  # تأكد من وجود هذه الوحدة
        'stock',
        'sale',
    ],
    'data': [
    'security/security.xml',
    'data/sequence.xml',
    'views/fsm_order_spare_part_views.xml',
    'views/fsm_equipment_views.xml',
    'views/fsm_order_views.xml',
    'views/agreement_views.xml',
    'views/stock_picking_views.xml',
],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}