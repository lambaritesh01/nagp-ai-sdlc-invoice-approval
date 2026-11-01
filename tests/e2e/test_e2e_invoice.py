"""Browser E2E tests against the real running app (system Chrome via Playwright).

Each test creates its own invoice, so tests are order-independent and isolated.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _create(page, base, vendor, amount) -> int:
    page.goto(base + "/")
    page.fill("#vendor", vendor)
    page.fill("#amount", str(amount))
    page.click("#create-form button[type=submit]")
    msg = page.locator("#create-msg")
    expect(msg).to_contain_text("Created invoice #")
    return int(re.search(r"#(\d+)", msg.inner_text()).group(1))


def _approve(page, invoice_id, approver, role):
    page.fill("#inv-id", str(invoice_id))
    page.fill("#approver", approver)
    page.select_option("#role", role)
    page.click("#approve-form button[type=submit]")
    return page.locator("#approve-msg")


def _row_status(page, invoice_id) -> str:
    page.click("#refresh-btn")
    badge = page.locator(f'#invoices tbody tr:has(td:text-is("{invoice_id}")) .status')
    return badge.inner_text()


def _row_approvals(page, invoice_id) -> str:
    page.click("#refresh-btn")
    cell = page.locator(f'#invoices tbody tr:has(td:text-is("{invoice_id}")) td.approvals')
    return cell.inner_text()


# 1. UI loads
def test_ui_loads(page, live_server):
    page.goto(live_server + "/")
    expect(page.locator("h1")).to_have_text("Invoice Approval")
    expect(page.locator("#create-form")).to_be_visible()
    expect(page.locator("#approve-form")).to_be_visible()


# 2. Create invoice
def test_create_invoice(page, live_server):
    inv_id = _create(page, live_server, "Acme E2E", 1000)
    assert inv_id > 0
    expect(page.locator(f'#invoices tbody tr:has(td:text-is("{inv_id}"))')).to_be_visible()


# 3. Manager approves an eligible invoice
def test_manager_approves_eligible(page, live_server):
    inv_id = _create(page, live_server, "SmallCo", 40_000)
    msg = _approve(page, inv_id, "mandy", "MANAGER")
    expect(msg).to_contain_text("Invoice approved")
    assert _row_status(page, inv_id) == "APPROVED"


# 4 + 5. Manager rejected above 50,000; reason displayed; state unchanged
def test_manager_rejected_above_limit_state_unchanged(page, live_server):
    inv_id = _create(page, live_server, "BigCo", 60_000)
    msg = _approve(page, inv_id, "mandy", "MANAGER")
    expect(msg).to_contain_text("Rejected")
    expect(msg).to_contain_text("MANAGER")  # reason mentions the limit/role
    # State must be unchanged: still PENDING with no approvals.
    assert _row_status(page, inv_id) == "PENDING"
    assert _row_approvals(page, inv_id) == "—"


# 6. Director approves an eligible invoice
def test_director_approves_eligible(page, live_server):
    inv_id = _create(page, live_server, "MidCo", 300_000)
    msg = _approve(page, inv_id, "dana", "DIRECTOR")
    expect(msg).to_contain_text("Invoice approved")
    assert _row_status(page, inv_id) == "APPROVED"


# 7. Above 500,000 first approval -> pending second approval
def test_highvalue_first_approval_pending(page, live_server):
    inv_id = _create(page, live_server, "MegaCo", 600_000)
    msg = _approve(page, inv_id, "alice", "DIRECTOR")
    expect(msg).to_contain_text("First approval recorded")
    assert _row_status(page, inv_id) == "PENDING_SECOND_APPROVAL"


# 8. Same-person second approval is rejected
def test_highvalue_same_person_second_rejected(page, live_server):
    inv_id = _create(page, live_server, "MegaCo2", 600_000)
    _approve(page, inv_id, "alice", "DIRECTOR")
    msg = _approve(page, inv_id, "alice", "DIRECTOR")
    expect(msg).to_contain_text("Rejected")
    expect(msg).to_contain_text("different")
    assert _row_status(page, inv_id) == "PENDING_SECOND_APPROVAL"


# 9. Distinct Director second approval completes the high-value invoice
def test_highvalue_distinct_director_completes(page, live_server):
    inv_id = _create(page, live_server, "MegaCo3", 600_000)
    _approve(page, inv_id, "alice", "DIRECTOR")
    msg = _approve(page, inv_id, "bob", "DIRECTOR")
    expect(msg).to_contain_text("Invoice approved")
    assert _row_status(page, inv_id) == "APPROVED"
