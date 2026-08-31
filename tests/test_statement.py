# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale_loyalty.tests.common import TestSaleCouponCommon


@tagged('post_install', '-at_install')
class TestPointsStatement(TestSaleCouponCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env['res.partner'].create({
            'name': "Jean Jacques",
            'lang': 'en_US',
        })
        cls.program = cls.env['loyalty.program'].create({
            'name': "Statement program",
            'program_type': 'loyalty',
            'trigger': 'auto',
            'applies_on': 'both',
            'company_id': cls.env.company.id,
            'rule_ids': [Command.create({
                'reward_point_mode': 'unit',
                'reward_point_amount': 10,
                'product_ids': [Command.set(cls.product_C.ids)],
            })],
        })
        cls.card = cls.env['loyalty.card'].create({
            'program_id': cls.program.id,
            'partner_id': cls.partner_a.id,
            'points': 120,
        })
        cls.coupon_card = cls.env['loyalty.card'].create({
            'program_id': cls.code_promotion_program.id,
            'partner_id': cls.partner_a.id,
            'points': 1,
        })

    # === HELPERS === #

    def _add_history(self, count):
        self.env['loyalty.history'].create([{
            'card_id': self.card.id,
            'description': f"Movement {index}",
            'issued': 10,
            'used': 0,
        } for index in range(count)])

    def _render_report(self, card):
        html, _dummy = self.env['ir.actions.report']._render_qweb_html(
            'loyalty.report_loyalty_card', card.ids
        )
        return html.decode()

    def _render_mail(self, card):
        template = self.env.ref('loyalty.mail_template_loyalty_card')
        return template._render_field('body_html', card.ids, engine='qweb')[card.id]

    # === REPORT === #

    def test_report_renders_on_a_card_without_history(self):
        html = self._render_report(self.card)

        self.assertIn("Your points balance", html)
        self.assertIn("No movement recorded on this card yet.", html)

    def test_report_lists_the_history(self):
        self._add_history(3)

        html = self._render_report(self.card)

        for index in range(3):
            self.assertIn(f"Movement {index}", html)
        self.assertNotIn("Showing the last", html)

    def test_report_truncates_to_the_configured_limit(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aa_loyalty_points.statement_max_lines', '5'
        )
        self._add_history(7)

        html = self._render_report(self.card)

        self.assertIn("Movement 6", html)
        self.assertIn("Movement 2", html)
        self.assertNotIn("Movement 1", html)
        self.assertNotIn("Movement 0", html)
        self.assertIn("Showing the last", html)

    def test_a_zero_limit_prints_everything(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aa_loyalty_points.statement_max_lines', '0'
        )
        self._add_history(7)

        html = self._render_report(self.card)

        self.assertIn("Movement 0", html)
        self.assertNotIn("Showing the last", html)

    def test_report_drops_the_stock_header_and_footer(self):
        html = self._render_report(self.card)

        self.assertNotIn('<div class="header">', html)
        self.assertNotIn('<div class="footer">', html)
        self.assertIn('class="article"', html)

    def test_report_on_a_coupon_has_no_statement(self):
        html = self._render_report(self.coupon_card)

        self.assertNotIn("Your points balance", html)
        self.assertIn(self.coupon_card.code, html)

    # === EMAIL === #

    def test_mail_shows_the_balance_and_the_code(self):
        body = self._render_mail(self.card)

        self.assertIn("Your current balance", body)
        self.assertIn(self.card.points_display, body)
        self.assertIn(self.card.code, body)

    def test_mail_on_a_coupon_has_no_balance(self):
        body = self._render_mail(self.coupon_card)

        self.assertNotIn("Your current balance", body)
        self.assertIn(self.coupon_card.code, body)

    def test_the_balance_shows_its_money_value(self):
        self.program.reward_ids.unlink()
        reward = self.env['loyalty.reward'].create({
            'program_id': self.program.id,
            'reward_type': 'discount',
            'discount_mode': 'per_point',
            'discount': 0.01,
        })

        money = self.card._get_points_money_value()
        self.assertIn("1,20", money.replace('.', ','))
        self.assertIn(money, self._render_mail(self.card))
        self.assertIn("1.20", self._render_report(self.card).replace(',', '.'))

        reward.discount = 1
        self.assertEqual(self.card._get_points_money_value(), '')
        self.assertNotIn("1.20", self._render_report(self.card).replace(',', '.'))

    def test_our_body_replaces_the_stock_one(self):
        template = self.env.ref('loyalty.mail_template_loyalty_card')

        self.assertIn("reward coupon from", template.subject)
        for stock_wording in ("Here is your reward from", "Use this promo code"):
            self.assertNotIn(stock_wording, template.body_html)
        self.assertIn("Your current balance", template.body_html)
