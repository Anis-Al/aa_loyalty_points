# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    loyalty_points_total = fields.Integer(
        string="Points to Use",
        compute='_compute_loyalty_points_total',
        compute_sudo=True,
        groups='base.group_user',
    )

    def _compute_loyalty_points_total(self):
        self.loyalty_points_total = 0
        groups = self.env['loyalty.card']._read_group(
            domain=[
                '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids),
                ('partner_id', 'in', self.with_context(active_test=False)._search([('id', 'child_of', self.ids)])),
                ('points', '>', 0),
                ('program_id.active', '=', True),
                '|',
                    ('expiration_date', '>=', fields.Date.context_today(self)),
                    ('expiration_date', '=', False),
            ],
            groupby=['partner_id'],
            aggregates=['points:sum'],
        )
        for partner, points in groups:
            while partner:
                if partner in self:
                    partner.loyalty_points_total += int(points)
                partner = partner.parent_id
