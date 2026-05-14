import json

import pytest

from main import list_transactions


TXN = {"type": "transactions", "id": "t1", "attributes": {"description": "Coffee"}}
NEXT_URL = "https://api.up.com.au/api/v1/transactions?page[after]=abc123"


def page(items, next_url=None):
    """Build a minimal Up Bank list response."""
    return {"data": items, "links": {"next": next_url, "prev": None}}


# ── Test 1: single page ───────────────────────────────────────────────────────

def test_single_page_returns_data_without_cursor(httpx_mock):
    httpx_mock.add_response(json=page([TXN]))

    result = json.loads(list_transactions())

    assert result["data"] == [TXN]
    assert "next_cursor" not in result


# ── Test 2: two pages, both fit ───────────────────────────────────────────────

def test_two_pages_accumulated_when_under_size_limit(httpx_mock):
    txn2 = {"type": "transactions", "id": "t2", "attributes": {"description": "Lunch"}}
    httpx_mock.add_response(json=page([TXN], next_url=NEXT_URL))
    httpx_mock.add_response(json=page([txn2]))

    result = json.loads(list_transactions())

    assert result["data"] == [TXN, txn2]
    assert "next_cursor" not in result


# ── Test 3: size limit stops at page boundary ─────────────────────────────────

def test_size_limit_stops_at_page_boundary_and_returns_cursor(httpx_mock, monkeypatch):
    monkeypatch.setattr("main._RESPONSE_SIZE_LIMIT", 10)  # tiny limit — page 2 won't fit
    txn2 = {"type": "transactions", "id": "t2", "attributes": {"description": "Lunch"}}

    # Page 1 is fetched and accepted; page 2 is fetched then rejected by the size check.
    httpx_mock.add_response(json=page([TXN], next_url=NEXT_URL))
    httpx_mock.add_response(json=page([txn2]))

    result = json.loads(list_transactions())

    assert result["data"] == [TXN]
    assert result["next_cursor"] == NEXT_URL


# ── Test 4: cursor resumes from its URL ───────────────────────────────────────

def test_cursor_resumes_from_given_url(httpx_mock):
    txn2 = {"type": "transactions", "id": "t2", "attributes": {"description": "Lunch"}}
    httpx_mock.add_response(json=page([txn2]))

    # Filters should be ignored when cursor is provided — cursor encodes the original query.
    result = json.loads(list_transactions(cursor=NEXT_URL, since="2024-01-01", status="HELD"))

    assert result["data"] == [txn2]
    assert "next_cursor" not in result
    # Confirm the cursor URL was used, not the filters
    assert httpx_mock.get_requests()[0].url == NEXT_URL
