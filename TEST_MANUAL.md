# aa_loyalty_points — manual test pass

Run on `mconfort`. 30 checks plus 5 cleanup steps. Tick as you go; report failures
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

**3. Optional — re-run the automated suite first** (52 tests, all green as of
2026-09-04). `--http-port` is required: the portal tests need an HTTP daemon and
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
      a **dialog** (not a full page) with two columns only — **Code** and
      **Balance** — listing cards with a balance above zero, active and
      unexpired, with no **New** button. A customer with no card → no button at
      all.

- [ ] **B-01b The dialog lists only coupons older than the order.**
      Confirm an order on a `next_order_coupons` program so it issues a coupon,
      then reopen it.
      → That coupon is **not in the dialog** and **not in the stat button count**.
      Open an **older** order for the same customer → still absent there. Create a
      **new** order for that customer → it does appear in both.
      → The count and the number of rows in the dialog **always** match — both come from
      the same method, so a mismatch is a bug in that method, not a filter drift. `S03294`
      is the regression case: three cards on the customer, all issued by that order
      or by a later one, so the button must not appear at all.
      → On a **`loyalty`** (nominative) program the rule must **not** apply: the
      customer's card carries the id of the first order that made it and is reused
      forever, so it stays listed on that order and on every later one.

- [ ] **B-01c The Code column lines up.**
      In the dialog, the value under **Code** starts at the same left edge as the
      **Code** header, not centred in its cell.

- [ ] **B-02 The code can be copied.**
      In that dialog, click the clipboard icon on a **Code** cell.
      → It turns to "Copied" and the code is on the clipboard. Paste it into the
      order's **Coupon Code** button to check it is the real code.

- [ ] **B-04 No button once a *discount code* is used on the order.**
      Take an order whose stat button shows a count, apply one of its
      `next_order_coupons` codes (**Coupon Code** button), then reload the form.
      → The **Coupons** button is gone entirely. Remove the reward line → it comes
      back. 20 live orders already carry a coupon line and must show no button.

- [ ] **B-04b A nominative card keeps its button.**
      Open an order for a customer holding a card on a **`loyalty`** program. Core
      loads that card into the order by itself once the customer is set.
      → The **Coupons** button is **still there**, showing the card and its code.
      This is the whole point of B-04 not applying here: a nominative card is the
      customer's permanent card, never consumed, so the code must stay readable.

- [ ] **B-06 An order cannot spend the points it just earned.**
      On a `loyalty` program set to **Use points on = Future orders**: take a customer
      whose card is at **zero**, create an order that earns points, confirm it, then try
      to apply the card's code on that same order.
      → **No Coupons button at all** — the card holds nothing this order can spend, so it
      is not offered. If you reach the code another way, applying it is refused with
      *"The coupon does not have enough points for the selected reward."*
      Create a **new** order for that customer → the button is back and the points are
      spendable there.
      → With a carried-over balance the order may still redeem **that** balance, never
      more: a card at 500 on an order earning 100 offers 500, not 600.
      → Set the program to **Current & Future orders** and the same order may spend its
      own points again, on the quotation as well.

- [ ] **B-05 Points to Use on the contact.**
      Open a customer holding a balance — CENTRE DE SANTE ONAKIA (partner 458)
      totals **8628**.
      → **One** stat button, the native money icon, now reading **Points à
      utiliser** with that number — the card count is gone and there is no second
      button beside it. Clicking it opens that customer's loyalty cards.
      A customer with no card, or one whose cards are all at zero or expired → no
      button at all. Check as a **salesperson** too, not only as admin.

- [ ] **B-03 No points block under the totals.**
      The order's totals show only the native **Carte de fidélité / Émis(e) /
      Utilisé(e)** block. Our own points block is gone.

---

## A — Customer portal

Grant portal access to `TEST Fidélité` (Action ▸ Grant portal access), or log in
as one of the 28 customers who already hold a card.

- [ ] **A-01 The tile appears, last, with its icon.** `/my` shows a **My Points**
      tile linking to `/my/loyalty`. The sidebar next to the personal info shows
      **no loyalty cards block** — it was removed.
      → The tile is the **last one on the page**, after **Connection & Security**.
      → The voucher icon renders at the same size as the icons on the Addresses
      and Connection & Security tiles beside it — not oversized, not missing.
      Hard-refresh if you have looked at this page before; the SVG is cached.
      → The gap above the tile is the **same** as the gap between the other tile
      groups on the page — it sits in its own row, not crammed under Addresses /
      Connection & Security.

- [ ] **A-02 Everything on one page.** Open `/my/loyalty`.
      → A total per unit, then **Your cards** (the **full** coupon code in bold —
      not masked, no program name, balance, expiry), then **History** inline: Document,
      Date, Program, Earned, Used, with paging. There is **no** separate history
      route any more, and **no Sort By dropdown** — history is newest first.

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

- [ ] **C-01 The card PDF is the designed voucher.**
      Coupon card ▸ Print ▸ Coupon Code.
      → **No Odoo report header** (no date / company name / page numbers line) and
      **no footer**. Top to bottom: logo + *Récompense de fidélité*, cream
      congratulations card, navy card with the code and the barcode, the points
      card (balance, money value, statement table Date / Description /
      Gagnés / Utilisés, *Solde actuel* row), *Validité* / *Besoin d'aide ?*
      (reading "du lundi au vendredi de 8h à 17h, et le samedi de 8h à 14h"),
      thank-you block, navy contact bar.
      → **Everything on one page**, accents correct (*réduction*, not *rÃ©duction*),
      logos and icons visible, sans-serif type.

- [ ] **C-02 A card with no movements still prints.**
      → Valid PDF showing the balance and "No movement recorded on this card yet."

- [ ] **C-03 Long histories are truncated.**
      Settings ▸ Technical ▸ System Parameters ▸ New, key
      `aa_loyalty_points.statement_max_lines`, value `2`. Print a card with more
      than two movements.
      → Only the two most recent, then "Showing the last 2 of N movements."
      Default is 50 when the parameter is absent; `0` prints everything.
      **Delete the parameter afterwards.**

- [ ] **C-03b *Détail de vos points* shrinks past 3 movements.**
      Print a card with exactly **3** movements, then one with **4** or more.
      → At 3 the table keeps its normal type and row height. At 4 it switches to
      smaller type and tighter rows, so a long history stays on the page. Nothing
      else on the card changes size — the balance column, the headings and the
      *Solde actuel* row are identical on both PDFs.

- [ ] **C-04 The e-mail is a statement.**
      Card ▸ Send by Email.
      → Body reads "Hello …, Thank you for your loyalty", then balance, card code,
      expiry. The old wording — "Here is your reward from", "Use this promo code" —
      is **gone**. The subject is deliberately unchanged. The PDF is attached.

---

## F — Expiry on discount codes and loyalty cards

- [ ] **F-01 A new discount code expires in 12 months.** Confirm an order that
      generates a next-order coupon, open **Sales > Products > Coupons** (or the order's
      **Coupons** button) and read the new card.
      → **Expiration Date** = the day it was created, one year on.

- [ ] **F-01b A new loyalty card expires in 12 months.** Confirm an order for a
      customer with no card yet on a **`loyalty`** program, then read the card core
      created for them.
      → **Expiration Date** = the day it was created, one year on. ⚠️ On a
      nominative program this is the customer's **only** card: on that date the
      running balance stops being spendable and the card drops out of the portal,
      the **Points to Use** total and the **Coupons** button.

- [ ] **F-02 An eWallet card gets no expiry.** Generate a card on the Gift Cards
      program.
      → **Expiration Date** empty.

- [ ] **F-03 A date you set yourself is kept.** Loyalty program → **Generate Coupons**,
      fill **Valid Until** with a date a month out.
      → The card keeps your date; the rule does not stamp over it.

- [ ] **F-04 Existing coupons were not touched.** Open any card created before today.
      → **Expiration Date** still empty. The rule applies to new cards only.

- [ ] **F-05 The rule is visible and editable.** Settings > Technical > Automation
      Rules → **Discount code: expires 12 months after creation**, on `loyalty.card`,
      trigger **On create**.

## R — Regression

- [ ] **R-01 Orders with no loyalty are untouched.** No Coupons button when the
      customer holds no card.

- [ ] **R-02 Native features still work.** Gift Cards stat button, Coupon Code and
      Reward buttons and `/my/loyalty_card/<id>/history`. The portal sidebar
      renders normally minus the loyalty cards block.

- [ ] **R-03 Ordinary accounting is unaffected.** Post a normal customer invoice, a
      vendor bill and a vendor refund.
      → No loyalty movement. Only **customer** credit notes are in scope.

- [ ] **R-04 Existing cards were not disturbed.** 1046 cards, 397 with a balance,
      all three programs on **Proportional** with negative balance disallowed.

## L — French

- [ ] **L-01 Portal is French.** `/my/loyalty` as a French customer shows
      **Mes points**, **Vos cartes**, **Historique**, and the columns
      **Document / Date / Programme / Gagnés / Utilisés**.

- [ ] **L-02 Program form is French.** Loyalty program → **Avoirs** group,
      **Points sur avoir** with **Proportionnelle au montant remboursé** /
      **Totale, dès le premier avoir** / **Aucune reprise**.

- [ ] **L-03 Statement report is French.** Print a loyalty card whose contact has
      `lang = fr_FR` → **Votre solde de points**, columns
      **Date / Description / Gagnés / Utilisés**. With the cap hit:
      *"Affichage des 50 derniers mouvements sur 500 au total."*

- [ ] **L-04 Coupon email is French, and is OURS.** Send the card to a French
      contact → body starts **Bonjour**, then *Merci pour votre fidélité*,
      *Votre solde actuel*, *Code de votre carte*.
      → It must **not** say *Voici votre récompense* or carry the 🤍 emoji: that is
      Odoo's stock French body, and seeing it means the `fr_FR` slot was rewritten
      (run `-u aa_loyalty_points --i18n-overwrite`).

- [ ] **L-05 English is intact.** Same checks as L-03 and L-04 with a contact on
      `lang = en_US`.

- [ ] **L-06 Email is plain.** View source of the sent email → **no**
      `background`, no `background-color`, no coloured chip around the code.
      → It ends on *"L'équipe M'Confort"*: **no `--` separator, no signature
      block** repeating the company name below it.

- [ ] **L-07 Balance shows its money value.** Card on the live program
      (`0,01 €`/point) with 430 points → *"Votre solde actuel : 430 Point(s) de
      réduction (4,30 €)"*.
      → On the **eWallet** program (rate 1) there must be **no** parenthesis:
      *"100 € "* alone, not *"100 € (100,00 €)"*.
      → Same figure on the **PDF** (Print ▸ Coupon Code): *430 Point(s) de
      réduction (4,30 €)* under **Votre solde de points**, and no parenthesis on
      the eWallet.

---

## Cleanup

- [ ] Reset every `TEST` credit note and invoice to draft, then cancel them.
- [ ] Cancel the `TEST` sales orders.
- [ ] Archive the `TEST` coupon cards and the `TEST Fidélité` contact; revoke its
      portal access.
- [ ] Delete `aa_loyalty_points.statement_max_lines` if C-03 was run.
- [ ] Reset the `lang` of any contact switched to English for L-05.
- [ ] Confirm the live program is back on **Proportional**, negative balance
      disallowed — D-07 changes it.
