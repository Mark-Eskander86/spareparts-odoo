
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class FsmOrderSparePart(models.Model):
    _name = 'fsm.order.spare.part'
    _description = 'FSM Order Spare Part'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # === Fields ===
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    fsm_order_id = fields.Many2one(
        'fsm.order',
        string='FSM Order',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    equipment_id = fields.Many2one(
        'fsm.equipment',
        string='Equipment',
        required=True,
        tracking=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Spare Part',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
        tracking=True
    )

    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        tracking=True
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True
    )

    warranty_state = fields.Selection([
        ('in_warranty', 'In Warranty'),
        ('out_warranty', 'Out of Warranty'),
        ('in_agreement_spare', 'In Agreement (With Spare Parts)'),
        ('in_agreement_no_spare', 'In Agreement (Without Spare Parts)'),
    ], string='Warranty Status', compute='_compute_warranty_state', store=True)

    # === STATUS FLOW ===
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('received', 'Received'),
        ('installed', 'Installed'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    is_auto_flow = fields.Boolean(
        string='Auto Flow',
        compute='_compute_is_auto_flow',
        store=True
    )

    # Related documents
    sale_order_id = fields.Many2one('sale.order', string='Quotation', readonly=True)
    delivery_order_id = fields.Many2one('stock.picking', string='Delivery Order', readonly=True)
    return_picking_id = fields.Many2one('stock.picking', string='Return Picking', readonly=True)
    
    # Grouping for quotation
    quotation_group_id = fields.Char(
        string='Quotation Group',
        help='Used to group spare parts in one quotation',
        readonly=True
    )
    
    # Quantities tracking
    requested_qty = fields.Float(string='Requested Qty', default=0.0)
    received_qty = fields.Float(string='Received Qty', default=0.0)
    installed_qty = fields.Float(string='Installed Qty', default=0.0)
    returned_qty = fields.Float(string='Returned Qty', default=0.0)

    notes = fields.Text(string='Notes')
    installation_date = fields.Date(string='Installation Date')
    return_date = fields.Date(string='Return Date')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # === Defaults & Sequences ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fsm.order.spare.part') or _('New')
        return super(FsmOrderSparePart, self).create(vals_list)

    # === Compute Methods ===
    @api.depends('equipment_id', 'equipment_id.warranty_start_date', 'equipment_id.warranty_end_date', 'equipment_id.agreement_id')
    def _compute_warranty_state(self):
        for record in self:
            if not record.equipment_id:
                record.warranty_state = False
                continue

            equipment = record.equipment_id
            today = date.today()

            # Check agreement first
            if equipment.agreement_id:
                has_spare_parts = hasattr(equipment.agreement_id, 'x_spare_parts_included') and \
                                equipment.agreement_id.x_spare_parts_included
                if has_spare_parts:
                    record.warranty_state = 'in_agreement_spare'
                else:
                    record.warranty_state = 'in_agreement_no_spare'
            # Then check warranty
            elif equipment.warranty_end_date and equipment.warranty_end_date >= today:
                record.warranty_state = 'in_warranty'
            elif equipment.warranty_start_date and not equipment.warranty_end_date:
                record.warranty_state = 'in_warranty'
            else:
                record.warranty_state = 'out_warranty'

    @api.depends('warranty_state')
    def _compute_is_auto_flow(self):
        for record in self:
            record.is_auto_flow = record.warranty_state in ['in_warranty', 'in_agreement_spare']

    # === Action Methods ===
    def action_confirm(self):
        """Confirm and start the flow based on warranty state"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Only draft spare parts can be confirmed.'))

        if not self.warranty_state:
            raise UserError(_('Cannot determine warranty state. Please check equipment configuration.'))

        if self.is_auto_flow:
            self._create_delivery_order()
            self.state = 'requested'
            self.requested_qty = self.quantity
        else:
            self._add_to_quotation()
            self.state = 'requested'
            self.requested_qty = self.quantity

        return True

    def _add_to_quotation(self):
        """Add to existing quotation or create new one for same equipment"""
        self.ensure_one()
        
        existing_quotation = self.env['sale.order'].search([
            ('fsm_order_id', '=', self.fsm_order_id.id),
            ('equipment_id', '=', self.equipment_id.id),
            ('state', 'in', ['draft', 'sent']),
            ('is_spare_parts_quotation', '=', True),
        ], limit=1, order='id desc')
        
        if existing_quotation:
            self._add_line_to_quotation(existing_quotation)
            self.sale_order_id = existing_quotation.id
            self.quotation_group_id = existing_quotation.name
        else:
            self._create_new_quotation()

    def _create_new_quotation(self):
        """Create new quotation for spare parts"""
        self.ensure_one()

        partner_id = False
        if hasattr(self.fsm_order_id, 'location_id') and self.fsm_order_id.location_id:
            if hasattr(self.fsm_order_id.location_id, 'partner_id') and self.fsm_order_id.location_id.partner_id:
                partner_id = self.fsm_order_id.location_id.partner_id.id
        
        if not partner_id and hasattr(self.fsm_order_id, 'customer_id') and self.fsm_order_id.customer_id:
            partner_id = self.fsm_order_id.customer_id.id
            
        if not partner_id and hasattr(self.fsm_order_id, 'partner_id') and self.fsm_order_id.partner_id:
            partner_id = self.fsm_order_id.partner_id.id
        
        if not partner_id:
            raise UserError(_('Cannot find partner for this FSM Order.'))

        equipment = self.equipment_id
        
        equipment_product_name = ''
        if hasattr(equipment, 'product_id') and equipment.product_id:
            equipment_product_name = equipment.product_id.name
        else:
            equipment_product_name = equipment.name or 'Unknown Equipment'
        
        serial_number = ''
        if hasattr(equipment, 'serial_no') and equipment.serial_no:
            serial_number = equipment.serial_no
        elif hasattr(equipment, 'lot_id') and equipment.lot_id:
            serial_number = equipment.lot_id.name

        sale_vals = {
            'partner_id': partner_id,
            'origin': _('FSM Order: %s - Equipment: %s') % (self.fsm_order_id.name, equipment.name),
            'company_id': self.company_id.id,
            'fsm_order_id': self.fsm_order_id.id,
            'equipment_id': self.equipment_id.id,
            'is_spare_parts_quotation': True,
            'note': _('Spare Parts for:\nEquipment: %s\nS.N: %s') % (equipment_product_name, serial_number or 'N/A'),
        }

        sale_order = self.env['sale.order'].create(sale_vals)
        
        self._add_line_to_quotation(sale_order)
        
        self.sale_order_id = sale_order.id
        self.quotation_group_id = sale_order.name
        self.message_post(body=_("Quotation %s created for spare parts.") % sale_order.name)

    def _add_line_to_quotation(self, sale_order):
        """Add line to existing quotation"""
        self.ensure_one()
        
        equipment = self.equipment_id
        product = self.product_id
        
        equipment_product_name = ''
        if hasattr(equipment, 'product_id') and equipment.product_id:
            equipment_product_name = equipment.product_id.name
        else:
            equipment_product_name = equipment.name or 'Unknown Equipment'
        
        serial_number = ''
        if hasattr(equipment, 'serial_no') and equipment.serial_no:
            serial_number = equipment.serial_no
        elif hasattr(equipment, 'lot_id') and equipment.lot_id:
            serial_number = equipment.lot_id.name
        
        # Build description - بدون سطر فاضي
        description_lines = [
            _('قيمة:'),
            product.name,
            _('لجهاز:'),
            equipment_product_name,
        ]
        
        if serial_number:
            description_lines.append(_('S.N: %s') % serial_number)
        
        description = '\n'.join(description_lines)

        self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': product.id,
            'product_uom_qty': self.quantity,
            'product_uom': self.uom_id.id,
            'name': description,
        })

    def action_mark_received(self):
        """Mark as received from warehouse"""
        self.ensure_one()
        if self.state not in ['requested', 'draft']:
            raise UserError(_('Only requested parts can be marked as received.'))
        
        self.state = 'received'
        self.received_qty = self.quantity
        self.message_post(body=_("Spare part received from warehouse."))

    def action_mark_installed(self):
        """Mark as installed on equipment"""
        self.ensure_one()
        if self.state != 'received':
            raise UserError(_('Only received parts can be marked as installed.'))
        
        self.state = 'installed'
        self.installed_qty = self.quantity
        self.installation_date = date.today()
        self.message_post(body=_("Spare part installed on equipment."))

    def action_create_return(self):
        """Create return to warehouse"""
        self.ensure_one()
        if self.state not in ['received', 'installed']:
            raise UserError(_('Only received or installed parts can be returned.'))
        
        if self.delivery_order_id:
            StockReturnPicking = self.env['stock.return.picking']
            
            return_wizard = StockReturnPicking.with_context(
                active_id=self.delivery_order_id.id,
                active_model='stock.picking',
                active_ids=[self.delivery_order_id.id]
            ).create({})
            
            if return_wizard.product_return_moves:
                return_wizard.product_return_moves[0].write({
                    'quantity': self.quantity
                })
            
            try:
                result = return_wizard.action_create_returns()
                
                if isinstance(result, dict) and 'res_id' in result:
                    self.return_picking_id = result['res_id']
                elif isinstance(result, int):
                    self.return_picking_id = result
                elif isinstance(result, models.Model):
                    self.return_picking_id = result.id
                    
            except AttributeError:
                picking_type_id = self.delivery_order_id.picking_type_id.return_picking_type_id.id
                
                if not picking_type_id:
                    raise UserError(_('No return picking type configured.'))
                
                return_picking = self.env['stock.picking'].create({
                    'picking_type_id': picking_type_id,
                    'origin': _('Return of %s') % self.delivery_order_id.name,
                    'location_id': self.delivery_order_id.location_dest_id.id,
                    'location_dest_id': self.delivery_order_id.location_id.id,
                    'partner_id': self.delivery_order_id.partner_id.id,
                })
                
                self.env['stock.move'].create({
                    'name': self.product_id.display_name,
                    'product_id': self.product_id.id,
                    'product_uom_qty': self.quantity,
                    'product_uom': self.uom_id.id,
                    'picking_id': return_picking.id,
                    'location_id': self.delivery_order_id.location_dest_id.id,
                    'location_dest_id': self.delivery_order_id.location_id.id,
                })
                
                self.return_picking_id = return_picking.id
        
        self.state = 'returned'
        self.returned_qty = self.quantity
        self.return_date = date.today()
        self.message_post(body=_("Spare part returned to warehouse."))

    def _create_delivery_order(self):
        """Create stock picking for delivery"""
        self.ensure_one()

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not picking_type:
            raise UserError(_('No outgoing picking type found.'))

        location_id = picking_type.default_location_src_id.id or self.env.ref('stock.stock_location_stock').id
        location_dest_id = self.fsm_order_id.location_id.inventory_location_id.id or self.env.ref('stock.stock_location_customers').id

        picking_vals = {
            'picking_type_id': picking_type.id,
            'partner_id': self.fsm_order_id.location_id.partner_id.id if self.fsm_order_id.location_id.partner_id else False,
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'origin': _('FSM: %s - Part: %s') % (self.fsm_order_id.name, self.name),
            'fsm_spare_part_id': self.id,
            'move_ids_without_package': [(0, 0, {
                'name': self.product_id.display_name,
                'product_id': self.product_id.id,
                'product_uom_qty': self.quantity,
                'product_uom': self.uom_id.id,
                'location_id': location_id,
                'location_dest_id': location_dest_id,
            })]
        }

        picking = self.env['stock.picking'].create(picking_vals)
        self.delivery_order_id = picking.id
        self.message_post(body=_("Delivery Order %s created.") % picking.name)

    def action_view_sale_order(self):
        """View related sale order"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No quotation created.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_delivery(self):
        """View related delivery order"""
        self.ensure_one()
        if not self.delivery_order_id:
            raise UserError(_('No delivery order created.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.delivery_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def get_equipment_info(self):
        """Return equipment info based on warranty state"""
        self.ensure_one()
        if not self.equipment_id:
            return {}
        
        equipment = self.equipment_id
        
        if self.warranty_state == 'in_warranty':
            return {
                'type': 'equipment',
                'name': equipment.name,
                'id': equipment.id,
                'warranty_date': equipment.warranty_end_date or equipment.warranty_start_date,
            }
        elif self.warranty_state == 'in_agreement_spare':
            return {
                'type': 'agreement',
                'name': equipment.agreement_id.name if equipment.agreement_id else 'N/A',
                'id': equipment.agreement_id.id if equipment.agreement_id else False,
            }
        else:
            return {
                'type': 'none',
                'name': 'Out of Warranty / No Agreement',
            }