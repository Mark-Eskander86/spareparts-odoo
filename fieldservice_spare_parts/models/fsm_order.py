
from odoo import models, fields, api


class FsmOrder(models.Model):
    _inherit = 'fsm.order'

    spare_part_ids = fields.One2many(
        'fsm.order.spare.part',
        'fsm_order_id',
        string='Spare Parts'
    )

    spare_parts_count = fields.Integer(
        string='Spare Parts Count',
        compute='_compute_spare_parts_count'
    )

    @api.depends('spare_part_ids')
    def _compute_spare_parts_count(self):
        for order in self:
            order.spare_parts_count = len(order.spare_part_ids)

    def action_view_spare_parts(self):
        """View spare parts for this order"""
        self.ensure_one()
        return {
            'name': 'Spare Parts',
            'type': 'ir.actions.act_window',
            'res_model': 'fsm.order.spare.part',
            'view_mode': 'list,form',
            'domain': [('fsm_order_id', '=', self.id)],
            'context': {
                'default_fsm_order_id': self.id,
            },
        }