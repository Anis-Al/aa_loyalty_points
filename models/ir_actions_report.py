# -*- coding: utf-8 -*-
# Part of aa_loyalty_points by Anis Alim. Licensed under LGPL-3.

import re

from odoo import models

EMPTY_HEADERS = re.compile(r'<div id="minimal_layout_report_headers">\s*</div>')


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        result = super()._prepare_html(html, report_model=report_model)
        if not result:
            return result
        bodies, res_ids, header, footer, specific_paperformat_args = result
        if header and EMPTY_HEADERS.search(header):
            header = ''
        return bodies, res_ids, header, footer, specific_paperformat_args
