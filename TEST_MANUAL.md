# aa_loyalty_points — manual test pass

Run on `mconfort`. 28 checks plus 5 cleanup steps. Tick as you go; report failures
as `D-01: saw X, expected Y`.

---

## Before you start

**1. Restart the service.** Python changes never reach the live site otherwise —
templates come from the database and go live at once, controllers do not.

```powershell
Restart-Service odoo-server-19.0 -Force
```

**2. These steps write to the live database**, including posted credit notes.
Use only the `TEST` records created below. **Never post a credit note against a
real customer order** — it now removes their points for real.

**3. Optional — re-run the automated suite first** (49 tests, all green as of
2026-08-31). `--http-port` is required: the portal tests need an HTTP daemon and
8069 is held by the live service.

```powershell
& "C:\Program Files\Odoo 19.0.20260724\python\python.exe" `
  "C:\Program Files\Odoo 19.0.20260724\server\odoo-bin" `
  -c "C:\Program Files\Odoo 19.0.20260724\server\odoo.conf" `
  -d mconfort -u aa_loyalty_points --test-enable `
  --test-tags=/aa_loyalty_points --stop-after-init --no-http `
  --http-port=8269 --logfile=- --log-level=test
```

A `SerializationFailure` on startup is transient — just run it again.

**What you are testing against.** The live program is
**"Bons de réduction pour la prochaine commande"** (`next_order_coupons`):
1 point per 1 spent, unit *Point(s) de réduction*, Points on Credit Note =
*Proportional*, negative balance not allowed. Confirming an order creates a **new
coupon card** for that order, so each test below gets its own card.

---

## S — Setup

- [ ] **S-01** Create a customer `TEST Fidélité` with a valid e-mail.
- [ ] **S-02** New quotation for it, one line, untaxed total exactly **1000**. Confirm.
      → A new coupon card exists with **1000 points**. Find it under Sales ▸ Products ▸
      Discount & Loyalty ▸ the live program ▸ Coupons. Keep it open.
- [ ] **S-03** On the order: Create Invoice ▸ Regular ▸ Confirm.
      → Card still 1000. Invoicing alone changes nothing.

Repeat S-02 and S-03 whenever a test needs a fresh order.

---

## D — Credit notes

The lot that closes the leak. Card balance is read on the coupon card form.

- [ ] **D-01 Full credit note takes everything and retires the coupon.**
      Invoice ▸ Credit Note ▸ confirm ▸ Post.
      → Balance **1000 → 0**. One history line pointing at the credit note,
      Used 1000. The card is now **archived** — it disappears from the coupon
      list unless you filter on Archived. It was never used, so it is dead.

- [ ] **D-02 Partial credit note is prorated and keeps the coupon.**
      Fresh order. Credit only **400** of the 1000 before posting.
      → Balance **1000 → 600**, Used 400, card still **active** and usable.

- [ ] **D-03 Reset to draft undoes everything.**
      Take the D-01 credit note ▸ Reset to Draft.
      → Balance back to **1000**, the history line is **gone**, and the card is
      **un-archived**.

- [ ] **D-04 Re-posting recovers once, not twice.**
      Post that same credit note again.
      → Balance **0**, not −1000. Exactly **one** history line.

- [ ] **D-05 A coupon already used is kept.**
      Fresh order. Spend some of its points on a second order, then credit the
      first invoice in full.
      → Points deducted, but the card stays **active** — its history must stay
      coherent.

- [ ] **D-06 Recovery is capped at the balance and logged.**
      Fresh order. On the card use **Update Balance** to drop it to **200**, then
      credit the invoice in full.
      → Balance stops at **0**, never negative. Used = **200**, not 1000. A message
      in the card chatter names the credit note and the shortfall.

- [ ] **D-07 Policy "No recovery" does nothing.**
      Set Points on Credit Note = *No recovery* on the program. Fresh order,
      credit in full.
      → Balance unchanged, no history line. **Set it back to Proportional.**

- [ ] **D-08 Manual credit note with no order does nothing.**
      Accounting ▸ Customers ▸ Credit Notes ▸ New, free-typed line, Post.
      → No error, no points move.

- [ ] **D-09 Cancelling the order after a credit note does not double-count.**
      Fresh order → invoice → full credit note (balance 0) → **cancel the order**.
      → Balance stays **0**. If it goes to −1000, stop and report — this is the
      highest-severity risk.

---

## B — Sale order

- [ ] **B-01 Coupons stat button opens a dialog.**
      Open an order for a customer holding a card with points — 397 customers
      qualify; GOULAMHOUSSEIN (card 1256, 5301 pts) is a known one.
      → A ticket button showing the count, next to Gift Cards. Clicking it opens
      a **dialog** (not a full page) listing only cards with a balance above
      zero, active and unexpired, with no **New** button. A customer with no
      card → no button at all.

- [ ] **B-02 The code can be copied.**
      In that dialog, click the clipboard icon on a **Code** cell.
      → It turns to "Copied" and the code is on the clipboard. Paste it into the
      order's **Coupon Code** button to check it is the real code.

- [ ] **B-03 No points block under the totals.**
      The order's totals show only the native **Carte de fidélité / Émis(e) /
      Utilisé(e)** block. Our own points block is gone.

---

## A — Customer portal

Grant portal access to `TEST Fidélité` (Action ▸ Grant portal access), or log in
as one of the 28 customers who already hold a card.

- [ ] **A-01 The tile appears, last, with its icon.** `/my` shows a **My Points**
      tile linking to `/my/loyalty`, and the sidebar also lists the card.
      → The tile is the **last one on the page**, after **Connection & Security**.
      → The voucher icon renders at the same size as the icons on the Addresses
      and Connection & Security tiles beside it — not oversized, not missing.
      Hard-refresh if you have looked at this page before; the SVG is cached.

- [ ] **A-02 Everything on one page.** Open `/my/loyalty`.
      → A total per unit, then **Your cards** (program, masked code showing only
      the last 4 characters, balance, expiry), then **History** inline: Document,
      Date, Program, Earned, Used, with paging. There is **no** separate history
      route any more.

- [ ] **A-03 Documents link.** A history row for an order links to that order; a
      row created by a credit note links to the credit note. Both open with a
      portal token.

- [ ] **A-04 No card, no page.** Log in as a customer with no card.
      → No tile, and typing `/my/loyalty` redirects to `/my`.

- [ ] **A-05 Customers are isolated.** While logged in as one customer, request
      `/my/loyalty_card/<another customer's card id>/history`.
      → Redirects to `/my`. Never a 500, never their data. `/my/loyalty` lists
      only your own movements.

---

## C — Statement

- [ ] **C-01 The card PDF carries the balance and movements.**
      Coupon card ▸ Print ▸ Coupon Code.
      → Below the barcode: **Your points balance**, then a table of Date /
      Description / Earned / Spent. The coupon layout above is unchanged.

- [ ] **C-02 A card with no movements still prints.**
      → Valid PDF showing the balance and "No movement recorded on this card yet."

- [ ] **C-03 Long histories are truncated.**
      Settings ▸ Technical ▸ System Parameters ▸ New, key
      `aa_loyalty_points.statement_max_lines`, value `2`. Print a card with more
      than two movements.
      → Only the two most recent, then "Showing the last 2 of N movements."
      Default is 50 when the parameter is absent; `0` prints everything.
      **Delete the parameter afterwards.**

- [ ] **C-04 The e-mail is a statement.**
      Card ▸ Send by Email.
      → Body reads "Hello …, Thank you for your loyalty", then balance, card code,
      expiry. The old wording — "Here is your reward from", "Use this promo code" —
      is **gone**. The subject is deliberately unchanged. The PDF is attached.

---

## R — Regression

- [ ] **R-01 Orders with no loyalty are untouched.** No Coupons button when the
      customer holds no card.

- [ ] **R-02 Native features still work.** Gift Cards stat button, Coupon Code and
      Reward buttons, `/my/loyalty_card/<id>/history`, and the portal sidebar.

- [ ] **R-03 Ordinary accounting is unaffected.** Post a normal customer invoice, a
      vendor bill and a vendor refund.
      → No loyalty movement. Only **customer** credit notes are in scope.

- [ ] **R-04 Existing cards were not disturbed.** 1046 cards, 397 with a balance,
      all three programs on **Proportional** with negative balance disallowed.

---

## Cleanup

- [ ] Reset every `TEST` credit note and invoice to draft, then cancel them.
- [ ] Cancel the `TEST` sales orders.
- [ ] Archive the `TEST` coupon cards and the `TEST Fidélité` contact; revoke its
      portal access.
- [ ] Delete `aa_loyalty_points.statement_max_lines` if C-03 was run.
- [ ] Confirm the live program is back on **Proportional**, negative balance
      disallowed — D-07 changes it.
