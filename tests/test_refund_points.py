# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale_loyalty.tests.common import TestSaleCouponCommon


@tagged('post_install', '-at_install')
class TestRefundPoints(TestSaleCouponCommon):

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
        cls.card = cls.env['loyalty.card'].create({
            'program_id': cls.program.id,
            'partner_id': cls.partner_a.id,
            'points': 0,
        })

    # === HELPERS === #

    def _create_order(self, qty=10):
        return self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product_C.id,
                'product_uom_qty': qty,
                'tax_ids': False,
            })],
        })

    def _confirm_order(self, qty=10):
        order = self._create_order(qty)
        order.action_confirm()
        return order

    def _invoice(self, orders):
        invoice = orders._create_invoices()
        invoice.action_post()
        return invoice

    def _refund(self, invoice, ratio=1.0):
        refund = invoice._reverse_moves()
        if ratio != 1.0:
            for line in refund.invoice_line_ids:
                line.quantity *= ratio
        refund.action_post()
        return refund

    def _refund_history(self):
        return self.card.history_ids.filtered(lambda line: line.order_model == 'account.move')

    # === TESTS === #

    def test_full_refund_takes_all_points(self):
        order = self._confirm_order()
        self.assertEqual(self.card.points, 100)

        refund = self._refund(self._invoice(order))

        self.assertEqual(self.card.points, 0)
        history = self._refund_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history.used, 100)
        self.assertEqual(history.issued, 0)
        self.assertEqual(history.order_id, refund.id)

    def test_partial_refund_is_prorated(self):
        order = self._confirm_order()

        self._refund(self._invoice(order), ratio=0.4)

        self.assertEqual(self.card.points, 60)
        self.assertEqual(self._refund_history().used, 40)

    def test_refund_gives_spent_points_back(self):
        self.card.points = 30
        order = self._create_order()
        order._update_programs_and_rewards()
        self._claim_reward(order, self.program)
        order.action_confirm()
        self.assertEqual(self.card.points, 100)

        self._refund(self._invoice(order))

        self.assertEqual(self.card.points, 30)
        history = self._refund_history()
        self.assertEqual(history.used, 100)
        self.assertEqual(history.issued, 30)

    def test_refund_policy_none_does_nothing(self):
        self.program.refund_policy = 'none'
        order = self._confirm_order()

        self._refund(self._invoice(order))

        self.assertEqual(self.card.points, 100)
        self.assertFalse(self._refund_history())

    def test_refund_policy_full_ignores_the_ratio(self):
        self.program.refund_policy = 'full'
        order = self._confirm_order()

        self._refund(self._invoice(order), ratio=0.4)

        self.assertEqual(self.card.points, 0)

    def test_recovery_is_capped_at_the_balance_and_logged(self):
        order = self._confirm_order()
        self.card.points = 20
        message_count = len(self.card.message_ids)

        self._refund(self._invoice(order))

        self.assertEqual(self.card.points, 0)
        self.assertEqual(self._refund_history().used, 20)
        self.assertGreater(len(self.card.message_ids), message_count)

    def test_balance_goes_negative_when_the_program_allows_it(self):
        self.program.allow_negative_points = True
        order = self._confirm_order()
        self.card.points = 20

        self._refund(self._invoice(order))

        self.assertEqual(self.card.points, -80)

    def test_applying_twice_recovers_once(self):
        order = self._confirm_order()
        refund = self._refund(self._invoice(order))
        self.assertEqual(self.card.points, 0)

        refund._apply_loyalty_refund()

        self.assertEqual(self.card.points, 0)
        self.assertEqual(len(self._refund_history()), 1)

    def test_reset_to_draft_restores_the_points(self):
        order = self._confirm_order()
        refund = self._refund(self._invoice(order))

        refund.button_draft()

        self.assertEqual(self.card.points, 100)
        self.assertFalse(self._refund_history())

    def test_manual_refund_without_an_order_does_nothing(self):
        self._confirm_order()

        self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_C.id,
                'quantity': 1,
                'price_unit': 100,
                'tax_ids': False,
            })],
        }).action_post()

        self.assertEqual(self.card.points, 100)
        self.assertFalse(self._refund_history())

    def test_order_cancelled_after_a_refund_is_not_counted_twice(self):
        order = self._confirm_order()
        self._refund(self._invoice(order))
        self.assertEqual(self.card.points, 0)

        order._action_cancel()

        self.assertEqual(self.card.points, 0)
        self.assertFalse(self.card.history_ids)

    def test_each_order_of_a_multi_order_refund_gets_its_own_ratio(self):
        order_a = self._confirm_order(qty=10)
        order_b = self._confirm_order(qty=5)
        self.assertEqual(self.card.points, 150)
        invoice = self._invoice(order_a | order_b)
        self.assertEqual(len(invoice), 1, "Both orders should land on a single invoice")

        refund = invoice._reverse_moves()
        for line in refund.invoice_line_ids:
            if order_b in line.sale_line_ids.order_id:
                line.quantity *= 0.4
        refund.action_post()

        self.assertEqual(self.card.points, 30)
        self.assertEqual(sum(self._refund_history().mapped('used')), 120)


@tagged('post_install', '-at_install')
class TestRefundNextOrderCoupon(TestSaleCouponCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env['res.partner'].create({'name': "Jean Jacques"})
        cls.program = cls.env['loyalty.program'].create({
            'name': "Next order coupon",
            'program_type': 'next_order_coupons',
            'applies_on': 'future',
            'trigger': 'auto',
            'rule_ids': [Command.create({
                'reward_point_mode': 'money',
                'reward_point_amount': 1,
                'minimum_amount': 0,
                'minimum_qty': 0,
            })],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount_mode': 'per_point',
                'discount': 1,
                'discount_applicability': 'order',
                'required_points': 1,
            })],
        })

    # === HELPERS === #

    def _confirm_order(self, qty=10):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product_C.id,
                'product_uom_qty': qty,
                'tax_ids': False,
            })],
        })
        order.action_confirm()
        return order

    def _coupon_of(self, order):
        return self.env['loyalty.card'].with_context(active_test=False).search([
            ('order_id', '=', order.id),
            ('program_id', '=', self.program.id),
        ])

    def _refund(self, order, ratio=1.0):
        invoice = order._create_invoices()
        invoice.action_post()
        refund = invoice._reverse_moves()
        if ratio != 1.0:
            for line in refund.invoice_line_ids:
                line.quantity *= ratio
        refund.action_post()
        return refund

    # === TESTS === #

    def test_a_full_refund_archives_the_unused_coupon(self):
        order = self._confirm_order()
        coupon = self._coupon_of(order)
        self.assertEqual(coupon.points, 1000)
        self.assertTrue(coupon.active)

        self._refund(order)

        self.assertEqual(coupon.points, 0)
        self.assertFalse(coupon.active)

    def test_a_partial_refund_keeps_the_coupon_usable(self):
        order = self._confirm_order()
        coupon = self._coupon_of(order)

        self._refund(order, ratio=0.4)

        self.assertEqual(coupon.points, 600)
        self.assertTrue(coupon.active)

    def test_reset_to_draft_brings_the_coupon_back(self):
        order = self._confirm_order()
        coupon = self._coupon_of(order)
        refund = self._refund(order)
        self.assertFalse(coupon.active)

        refund.button_draft()

        self.assertEqual(coupon.points, 1000)
        self.assertTrue(coupon.active)

    def test_a_coupon_already_used_is_not_archived(self):
        order = self._confirm_order()
        coupon = self._coupon_of(order)
        self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product_C.id,
                'product_uom_qty': 1,
                'tax_ids': False,
                'coupon_id': coupon.id,
            })],
        })
        self.assertTrue(coupon.use_count)

        self._refund(order)

        self.assertEqual(coupon.points, 0)
        self.assertTrue(coupon.active)
