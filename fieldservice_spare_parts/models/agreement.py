
from odoo import models, fields, api, _


class Agreement(models.Model):
    _inherit = 'agreement'

    x_spare_parts_included = fields.Boolean(
        string='Spare Parts Included',
        help='If checked, spare parts are included in the agreement'
    )
    
    x_spare_included = fields.Boolean(
        string='Spare Included',
        related='x_spare_parts_included',
        store=True
    )

    # Related equipments
    equipment_ids = fields.One2many(
        'fsm.equipment',
        'agreement_id',
        string='Equipments'
    )

    # === COUNTERS ===
    total_installed_qty = fields.Float(
        string='Total Installed Qty',
        compute='_compute_spare_parts',
        store=True
    )
    
    total_returned_qty = fields.Float(
        string='Total Returned Qty',
        compute='_compute_spare_parts',
        store=True
    )

    current_spare_parts_qty = fields.Float(
        string='Current Installed Qty',
        compute='_compute_spare_parts',
        store=True,
        help='Net quantity currently installed'
    )

    @api.depends('equipment_ids.total_installed_qty', 
                 'equipment_ids.total_returned_qty',
                 'equipment_ids.current_spare_parts_qty')
    def _compute_spare_parts(self):
        for agreement in self:
            agreement.total_installed_qty = sum(agreement.equipment_ids.mapped('total_installed_qty'))
            agreement.total_returned_qty = sum(agreement.equipment_ids.mapped('total_returned_qty'))
            # الصافي = الموجود حالياً (مثبت فقط)
            agreement.current_spare_parts_qty = sum(agreement.equipment_ids.mapped('current_spare_parts_qty'))

    def action_view_all_spare_parts(self):
        """View all installed spare parts for all equipments in this agreement"""
        self.ensure_one()
        return {
            'name': _('Installed Spare Parts - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'fsm.order.spare.part',
            'view_mode': 'list,form',
            'domain': [
                ('equipment_id', 'in', self.equipment_ids.ids),
                ('state', '=', 'installed')
            ],
            'context': {'group_by': 'equipment_id'},
        }