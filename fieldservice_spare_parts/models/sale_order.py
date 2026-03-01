
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Link to FSM Order
    fsm_order_id = fields.Many2one(
        'fsm.order',
        string='FSM Order',
        readonly=True
    )
    
    # Link to Equipment
    equipment_id = fields.Many2one(
        'fsm.equipment',
        string='Equipment',
        readonly=True
    )
    
    # Flag for spare parts quotation
    is_spare_parts_quotation = fields.Boolean(
        string='Spare Parts Quotation',
        default=False
    )