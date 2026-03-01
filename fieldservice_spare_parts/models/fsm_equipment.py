# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class FsmEquipment(models.Model):
    _inherit = 'fsm.equipment'

    # Add warranty fields
    warranty_start_date = fields.Date(string='Warranty Start Date')
    warranty_end_date = fields.Date(string='Warranty End Date')
    
    # Add x_spare_included field to avoid errors from other views
    x_spare_included = fields.Boolean(
        string='Spare Included',
        related='agreement_id.x_spare_parts_included',
        store=True,
        readonly=True
    )

    # All spare parts
    spare_part_ids = fields.One2many(
        'fsm.order.spare.part',
        'equipment_id',
        string='All Spare Parts',
        readonly=True
    )

    # === COUNTERS ===
    spare_parts_count = fields.Integer(
        string='Total Spare Parts',
        compute='_compute_spare_parts_stats',
        store=True
    )
    
    total_installed_qty = fields.Float(
        string='Total Installed Qty',
        compute='_compute_spare_parts_stats',
        store=True
    )
    
    total_returned_qty = fields.Float(
        string='Total Returned Qty',
        compute='_compute_spare_parts_stats',
        store=True
    )

    current_spare_parts_qty = fields.Float(
        string='Current Installed Qty',
        compute='_compute_spare_parts_stats',
        store=True,
        help='Net quantity currently installed'
    )

    @api.depends('spare_part_ids.state', 'spare_part_ids.installed_qty', 'spare_part_ids.returned_qty')
    def _compute_spare_parts_stats(self):
        for equipment in self:
            # Count all records
            equipment.spare_parts_count = len(equipment.spare_part_ids)
            
            # Get parts by state
            installed_parts = equipment.spare_part_ids.filtered(lambda p: p.state == 'installed')
            returned_parts = equipment.spare_part_ids.filtered(lambda p: p.state == 'returned')
            
            # Calculate totals
            equipment.total_installed_qty = sum(installed_parts.mapped('installed_qty'))
            equipment.total_returned_qty = sum(returned_parts.mapped('returned_qty'))
            equipment.current_spare_parts_qty = equipment.total_installed_qty

    def action_view_installed_spare_parts(self):
        """View installed spare parts for this equipment"""
        self.ensure_one()
        return {
            'name': _('Installed Spare Parts'),
            'type': 'ir.actions.act_window',
            'res_model': 'fsm.order.spare.part',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id), ('state', '=', 'installed')],
            'context': {'default_equipment_id': self.id},
        }