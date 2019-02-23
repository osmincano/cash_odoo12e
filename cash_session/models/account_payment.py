# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _default_session(self):
        return self.env['cash.session'].search([('state', '=', 'opened'), ('user_id', '=', self.env.uid)], limit=1)

    session_id = fields.Many2one(
        'cash.session', string='Session', required=True, index=True,
        domain="[('state', '=', 'opened')]", states={'draft': [('readonly', False)]},
        readonly=True, default=_default_session)
    picking_id = fields.Many2one('stock.picking', string='Picking', readonly=True, copy=False)
    statement_ids = fields.One2many('account.bank.statement.line', 'cash_statement_id', string='Payments', states={
                                    'draft': [('readonly', False)]}, readonly=True)

    def _create_account_move(self, dt, ref, journal_id, company_id):
        date_tz_user = fields.Datetime.context_timestamp(self, fields.Datetime.from_string(dt))
        date_tz_user = fields.Date.to_string(date_tz_user)
        return self.env['account.move'].sudo().create({'ref': ref, 'journal_id': journal_id, 'date': date_tz_user})

    @api.multi
    def action_cash_order_done(self):
        return self._create_account_move_line()

    def _create_account_move_line(self, session=None, move=None):
        return True
