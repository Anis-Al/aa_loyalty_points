# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from . import models
from . import controllers


def uninstall_hook(env):
    env['loyalty.history'].search([('order_model', '=', 'account.move')]).unlink()
