# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale_loyalty.tests.common import TestSaleCouponCommon


@tagged('post_install', '-at_install')
class TestSaleOrderPoints(TestSaleCouponCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env['res.partner'].create({'name': "Jean Jacques"})
        cls.program = cls.env['loyalty.program'].create({
            'name': "10 points per Product C",
            'program_type': 'loyalty',
            'trigger': 'auto',
            'applies_on': 'both',
            'rule_ids': [Command.create({
                'reward_point_mode': 'unit',
                'reward_point_amount': 10,
                'product_ids': [Command.set(cls.product_C.ids)],
            })],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount': 10,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
                'required_points': 30,
            })],
        })
        cls.coupon_program = cls.env['loyalty.program'].create({
            'name': "Coupon for the next order",
            'program_type': 'next_order_coupons',
            'trigger': 'auto',
            'applies_on': 'future',
            'rule_ids': [Command.create({'minimum_amount': 100, 'minimum_qty': 0})],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount': 15,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
            })],
        })
        cls.card = cls.env['loyalty.card'].create({
            'program_id': cls.program.id,
            'partner_id': cls.partner_a.id,
            'points': 0,
        })

    # === HELPERS === #

    def _create_order(self, qty=10, partner=None):
        return self.env['sale.order'].create({
            'partner_id': (partner or self.partner_a).id,
            'order_line': [Command.create({
                'product_id': self.product_C.id,
                'product_uom_qty': qty,
                'tax_ids': False,
            })],
        })

    def _create_coupon(self, source_order=None, points=30, program=None):
        return self.env['loyalty.card'].create({
            'program_id': (program or self.program).id,
            'partner_id': self.partner_a.id,
            'points': points,
            'order_id': source_order and source_order.id,
        })

    def _queries_to_read_counts(self, orders):
        orders.invalidate_recordset(['available_coupon_count'])
        self.env.flush_all()
        self.env.cr.flush()
        before = self.cr.sql_log_count
        orders.mapped('available_coupon_count')
        self.env.cr.flush()
        return self.cr.sql_log_count - before

    # === AVAILABLE COUPONS === #

    def test_no_card_means_no_stat_button(self):
        order = self._create_order(partner=self.env['res.partner'].create({'name': "No Card"}))

        self.assertEqual(order.available_coupon_count, 0)

    def test_a_card_with_points_is_counted(self):
        self.card.points = 50
        order = self._create_order()

        self.assertEqual(order.available_coupon_count, 1)

    def test_an_empty_or_expired_card_is_not_counted(self):
        self.card.points = 0
        expired = self.env['loyalty.card'].create({
            'program_id': self.program.id,
            'partner_id': self.partner_a.id,
            'points': 40,
        })
        expired.expiration_date = fields.Date.today() - relativedelta(days=1)
        order = self._create_order()

        self.assertEqual(order.available_coupon_count, 0)

    def test_a_child_partners_card_is_counted_on_the_parent(self):
        child = self.env['res.partner'].create({
            'name': "Child contact",
            'parent_id': self.partner_a.id,
        })
        self.env['loyalty.card'].create({
            'program_id': self.program.id,
            'partner_id': child.id,
            'points': 25,
        })
        order = self._create_order()

        self.assertEqual(order.available_coupon_count, 1)

    def test_the_action_opens_only_the_available_cards(self):
        self.card.points = 50
        empty_card = self.env['loyalty.card'].create({
            'program_id': self.program.id,
            'partner_id': self.partner_a.id,
            'points': 0,
        })
        order = self._create_order()

        action = order.action_view_available_coupons()
        cards = self.env['loyalty.card'].search(action['domain'])

        self.assertIn(self.card, cards)
        self.assertNotIn(empty_card, cards)
        self.assertFalse(action['context']['create'])
        self.assertEqual(action['target'], 'new')

    def test_only_coupons_from_earlier_orders_are_offered(self):
        older_order = self._create_order()
        order = self._create_order()
        newer_order = self._create_order()
        coupons = self.coupon_program
        from_older = self._create_coupon(source_order=older_order, program=coupons)
        own = self._create_coupon(source_order=order, program=coupons)
        from_newer = self._create_coupon(source_order=newer_order, program=coupons)
        no_source = self._create_coupon(program=coupons)

        self.assertEqual(order.available_coupon_count, 2)

        cards = self.env['loyalty.card'].search(order.action_view_available_coupons()['domain'])

        self.assertIn(from_older, cards)
        self.assertIn(no_source, cards)
        self.assertNotIn(own, cards)
        self.assertNotIn(from_newer, cards)

    def test_a_customer_whose_only_coupons_are_newer_gets_no_button(self):
        self.card.points = 0
        order = self._create_order()
        self._create_coupon(source_order=order, program=self.coupon_program)
        self._create_coupon(
            source_order=self._create_order(), program=self.coupon_program
        )

        self.assertEqual(order.available_coupon_count, 0)

    def test_a_nominative_card_is_offered_on_the_order_that_created_it(self):
        self.card.points = 0
        order = self._create_order()
        own = self._create_coupon(source_order=order)

        self.assertEqual(order.available_coupon_count, 1)

        cards = self.env['loyalty.card'].search(
            order.action_view_available_coupons()['domain']
        )

        self.assertIn(own, cards)

    def test_the_coupon_count_does_not_query_per_order(self):
        self.card.points = 50
        small = self.env['sale.order'].union(*[self._create_order() for _ in range(8)])
        large = self.env['sale.order'].union(*[self._create_order() for _ in range(80)])

        self._queries_to_read_counts(small)

        self.assertEqual(
            self._queries_to_read_counts(large),
            self._queries_to_read_counts(small),
            "available_coupon_count must not issue a query per order",
        )

    def test_no_button_when_a_coupon_is_already_used_on_the_order(self):
        self.card.points = 50
        order = self._create_order()

        self.assertEqual(order.available_coupon_count, 1)

        reward = self.program.reward_ids[0]
        order.write({'order_line': [Command.create({
            'name': "10% discount",
            'product_id': reward.discount_line_product_id.id,
            'reward_id': reward.id,
            'coupon_id': self.card.id,
            'price_unit': -100,
            'tax_ids': False,
        })]})
        order.invalidate_recordset(['available_coupon_count'])

        self.assertEqual(order.available_coupon_count, 0)

    def test_the_partner_totals_the_points_left_to_use(self):
        self.card.points = 50
        self._create_coupon(points=30)
        self.env['loyalty.card'].create({
            'program_id': self.program.id,
            'partner_id': self.partner_a.id,
            'points': 20,
            'expiration_date': fields.Date.today() - relativedelta(days=1),
        })

        self.assertEqual(self.partner_a.loyalty_points_total, 80)

    def test_a_partner_with_no_points_totals_zero(self):
        self.card.points = 0

        self.assertEqual(self.partner_a.loyalty_points_total, 0)
