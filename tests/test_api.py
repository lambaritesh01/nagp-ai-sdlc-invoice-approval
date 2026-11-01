"""API-level tests via FastAPI TestClient (isolated temp DB per test)."""

from __future__ import annotations


def _create(client, vendor="Acme", amount=1000):
    r = client.post("/api/invoices", json={"vendor": vendor, "amount": amount})
    assert r.status_code == 201, r.text
    return r.json()


def _approve(client, invoice_id, approver, role):
    return client.post(f"/api/invoices/{invoice_id}/approvals",
                       json={"approver": approver, "role": role})


# --- Creation & validation -------------------------------------------------
def test_create_and_get_invoice(client):
    inv = _create(client, "Acme", 1000)
    assert inv["status"] == "PENDING"
    r = client.get(f"/api/invoices/{inv['id']}")
    assert r.status_code == 200
    assert r.json()["vendor"] == "Acme"


def test_list_invoices(client):
    _create(client, "A", 10)
    _create(client, "B", 20)
    r = client.get("/api/invoices")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_create_rejects_zero_and_negative_amount(client):
    assert client.post("/api/invoices", json={"vendor": "X", "amount": 0}).status_code == 422
    assert client.post("/api/invoices", json={"vendor": "X", "amount": -5}).status_code == 422


def test_get_missing_invoice_404(client):
    assert client.get("/api/invoices/999").status_code == 404


def test_approve_missing_invoice_404(client):
    assert _approve(client, 999, "alice", "MANAGER").status_code == 404


# --- Single-approval boundaries (API) -------------------------------------
def test_manager_boundary_api(client):
    ok = _create(client, "m", 50_000)
    assert _approve(client, ok["id"], "alice", "MANAGER").status_code == 200
    over = _create(client, "m", 50_001)
    r = _approve(client, over["id"], "alice", "MANAGER")
    assert r.status_code == 409
    assert r.json()["detail"]["outcome"] == "rejected"


def test_director_boundary_api(client):
    ok = _create(client, "d", 500_000)
    r = _approve(client, ok["id"], "dana", "DIRECTOR")
    assert r.status_code == 200
    assert r.json()["outcome"] == "approved"
    assert r.json()["invoice"]["status"] == "APPROVED"


def test_invalid_role_api_rejected(client):
    inv = _create(client, "x", 100)
    r = _approve(client, inv["id"], "alice", "CEO")
    assert r.status_code == 409
    assert "invalid role" in r.json()["detail"]["message"]


# --- High-value dual approval (API) ---------------------------------------
def test_highvalue_happy_path_two_directors(client):
    inv = _create(client, "big", 600_000)
    r1 = _approve(client, inv["id"], "alice", "DIRECTOR")
    assert r1.status_code == 200
    assert r1.json()["outcome"] == "pending_second_approval"
    assert r1.json()["invoice"]["status"] == "PENDING_SECOND_APPROVAL"
    r2 = _approve(client, inv["id"], "bob", "DIRECTOR")
    assert r2.status_code == 200
    assert r2.json()["outcome"] == "approved"
    assert r2.json()["invoice"]["status"] == "APPROVED"
    assert len(r2.json()["invoice"]["approvals"]) == 2


def test_highvalue_same_approver_twice_rejected(client):
    inv = _create(client, "big", 600_000)
    assert _approve(client, inv["id"], "alice", "DIRECTOR").status_code == 200
    r = _approve(client, inv["id"], "alice", "DIRECTOR")
    assert r.status_code == 409
    assert "different" in r.json()["detail"]["message"]


def test_highvalue_second_manager_rejected(client):
    inv = _create(client, "big", 600_000)
    assert _approve(client, inv["id"], "alice", "DIRECTOR").status_code == 200
    r = _approve(client, inv["id"], "bob", "MANAGER")
    assert r.status_code == 409
    assert "DIRECTOR" in r.json()["detail"]["message"]


# --- Rejection must not mutate state --------------------------------------
def test_state_unchanged_after_rejection(client):
    inv = _create(client, "m", 50_001)
    before = client.get(f"/api/invoices/{inv['id']}").json()
    r = _approve(client, inv["id"], "alice", "MANAGER")
    assert r.status_code == 409
    after = client.get(f"/api/invoices/{inv['id']}").json()
    assert after == before  # status and (empty) approval history unchanged
    assert after["status"] == "PENDING"
    assert after["approvals"] == []


def test_already_approved_further_attempt_rejected(client):
    inv = _create(client, "m", 1000)
    assert _approve(client, inv["id"], "alice", "MANAGER").status_code == 200
    r = _approve(client, inv["id"], "bob", "DIRECTOR")
    assert r.status_code == 409
    assert "already" in r.json()["detail"]["message"]


def test_duplicate_finalization_blocked(client):
    # Completing a high-value invoice, then a third attempt is rejected and
    # does not add history.
    inv = _create(client, "big", 600_000)
    _approve(client, inv["id"], "alice", "DIRECTOR")
    _approve(client, inv["id"], "bob", "DIRECTOR")
    r = _approve(client, inv["id"], "carol", "DIRECTOR")
    assert r.status_code == 409
    final = client.get(f"/api/invoices/{inv['id']}").json()
    assert final["status"] == "APPROVED"
    assert len(final["approvals"]) == 2
