
from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Link to spare part
    fsm_spare_part_id = fields.Many2one(
        'fsm.order.spare.part',
        string='Related Spare Part',
        readonly=True
    )

    # Equipment info based on warranty state
    equipment_id = fields.Many2one(
        'fsm.equipment',
        string='Equipment',
        related='fsm_spare_part_id.equipment_id',
        readonly=True,
        store=True
    )

    warranty_state = fields.Selection(
        related='fsm_spare_part_id.warranty_state',
        string='Warranty Status',
        readonly=True,
        store=True
    )

    agreement_id = fields.Many2one(
        'agreement',
        string='Agreement',
        related='equipment_id.agreement_id',
        readonly=True,
        store=True
    )

    # Smart fields for links
    equipment_link = fields.Char(
        string='Equipment Link',
        compute='_compute_links'
    )

    agreement_link = fields.Char(
        string='Agreement Link',
        compute='_compute_links'
    )

    @api.depends('warranty_state', 'equipment_id', 'agreement_id')
    def _compute_links(self):
        for picking in self:
            if picking.warranty_state == 'in_warranty' and picking.equipment_id:
                picking.equipment_link = picking.equipment_id.name
                picking.agreement_link = False
            elif picking.warranty_state == 'in_agreement_spare' and picking.agreement_id:
                picking.equipment_link = False
                picking.agreement_link = picking.agreement_id.name
            else:
                picking.equipment_link = False
                picking.agreement_link = False

    def action_view_equipment(self):
        """View equipment"""
        self.ensure_one()
        if self.equipment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'fsm.equipment',
                'res_id': self.equipment_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {}

    def action_view_agreement(self):
        """View agreement"""
        self.ensure_one()
        if self.agreement_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'agreement',
                'res_id': self.agreement_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {}