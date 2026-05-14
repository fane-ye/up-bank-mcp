"""Up Bank MCP server — exposes the full Up Bank API as MCP tools."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

UP_API_BASE = "https://api.up.com.au/api/v1"
_RESPONSE_SIZE_LIMIT = 900_000  # bytes — stop at page boundaries before hitting MCP's 1MB limit

mcp = FastMCP("up-bank")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _token() -> str:
    token = os.environ.get("UP_PAT")
    if not token:
        raise RuntimeError("UP_PAT environment variable is not set.")
    return token


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


def _get(path: str, params: dict | None = None) -> dict:
    """Single GET request — path can be a full URL (pagination cursor) or a path."""
    # If path is already a full URL (e.g. a links.next cursor), use it directly.
    # Otherwise prefix with the base URL.
    url = path if path.startswith("http") else f"{UP_API_BASE}{path}"
    r = httpx.get(url, params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def _get_paginated(
    path: str, params: dict | None = None, max_results: int = 500
) -> tuple[list[dict], str | None]:
    """Follow links.next cursors, stopping at page boundaries before exceeding _RESPONSE_SIZE_LIMIT.

    Returns (results, next_cursor). next_cursor is non-None when the size limit caused an early stop
    — pass it as the cursor argument on the next call to continue.
    """
    results: list[dict] = []
    current_url: str = path

    # Fetch the first page. Params (filters, page size) are only sent on the first request —
    # subsequent pages use links.next URLs which already have everything baked in.
    data = _get(current_url, params)

    while True:
        page = data.get("data", [])

        # Combine what we have so far with this new page, capped at max_results.
        candidate = (results + page)[:max_results]

        # Size check: would adding this page push the response over the MCP limit?
        # Skip the check on the very first page (results is empty) so we always return something.
        if results and len(json.dumps(candidate, default=str, separators=(',', ':')).encode()) > _RESPONSE_SIZE_LIMIT:
            # This page doesn't fit. Return what we have and hand back the URL for this page
            # as a cursor so the caller can resume from here on the next call.
            return results, current_url

        # Page fits — commit it.
        results = candidate

        # Check whether there is another page to fetch.
        next_url = data.get("links", {}).get("next")

        if not next_url or len(results) >= max_results:
            # No more pages, or we've hit the caller's max_results cap — we're done.
            return results, None

        # Advance to the next page. No params needed — they're encoded in the cursor URL.
        current_url = next_url
        data = _get(current_url)


def _post(path: str, body: dict) -> dict | None:
    r = httpx.post(f"{UP_API_BASE}{path}", json=body, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json() if r.content else None


def _patch(path: str, body: dict) -> None:
    r = httpx.patch(f"{UP_API_BASE}{path}", json=body, headers=_headers(), timeout=15)
    r.raise_for_status()


def _delete(path: str, body: dict | None = None) -> None:
    r = httpx.request(
        "DELETE",
        f"{UP_API_BASE}{path}",
        json=body,
        headers=_headers(),
        timeout=15,
    )
    r.raise_for_status()


def _ok(data: object) -> str:
    # Compact separators remove whitespace between keys/values, keeping responses small.
    return json.dumps(data, default=str, separators=(',', ':'))


def _paginated_ok(results: list[dict], next_cursor: str | None) -> str:
    # Always wrap in {"data": [...]}. Only include next_cursor when there are more pages.
    payload: dict = {"data": results}
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return _ok(payload)


def _list(path: str, params: dict, max_results: int, cursor: str | None) -> str:
    """Fetch a paginated list, resuming from cursor if provided.

    When cursor is supplied it is used as the starting URL (it already encodes all filters),
    so params are skipped. When there is no cursor, path + params are used for the first request.
    """
    start_url = cursor if cursor else path
    start_params = None if cursor else params
    results, next_cursor = _get_paginated(start_url, start_params, max_results)
    return _paginated_ok(results, next_cursor)


def _transaction_params(
    since: str | None,
    until: str | None,
    status: str | None,
    category: str | None,
    tag: str | None,
) -> dict:
    # Build the Up Bank API filter params for transaction list endpoints.
    # Only include a key when the caller provided a value — omitting it means "no filter".
    params: dict = {"page[size]": 100}
    if since:
        params["filter[since]"] = since
    if until:
        params["filter[until]"] = until
    if status:
        params["filter[status]"] = status
    if category:
        params["filter[category]"] = category
    if tag:
        params["filter[tag]"] = tag
    return params


# ── Utility ───────────────────────────────────────────────────────────────────

@mcp.tool()
def ping() -> str:
    """Verify that the Up Bank API token is valid and the API is reachable."""
    return _ok(_get("/util/ping"))


# ── Accounts ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_accounts(
    account_type: Optional[str] = None,
    ownership_type: Optional[str] = None,
    max_results: int = 500,
    cursor: Optional[str] = None,
) -> str:
    """List all Up Bank accounts for the authenticated user.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored.

    Args:
        account_type: Filter by account type — SAVER, TRANSACTIONAL, or HOME_LOAN.
        ownership_type: Filter by ownership — INDIVIDUAL or JOINT.
        max_results: Maximum number of accounts to return (default 500).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    params: dict = {"page[size]": 100}
    if account_type:
        params["filter[accountType]"] = account_type
    if ownership_type:
        params["filter[ownershipType]"] = ownership_type
    return _list("/accounts", params, max_results, cursor)


@mcp.tool()
def get_account(account_id: str) -> str:
    """Retrieve a single Up Bank account by its ID.

    Args:
        account_id: The unique identifier for the account.
    """
    return _ok(_get(f"/accounts/{account_id}"))


# ── Transactions ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_transactions(
    since: Optional[str] = None,
    until: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    max_results: int = 100,
    cursor: Optional[str] = None,
) -> str:
    """List transactions across all accounts.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored; the cursor already encodes the
    original filters and position.

    Args:
        since: ISO-8601 datetime to filter from, e.g. '2024-01-01T00:00:00+10:00'.
        until: ISO-8601 datetime to filter up to.
        status: Filter by status — HELD or SETTLED.
        category: Category slug to filter by, e.g. 'groceries', 'restaurants-and-cafes'.
        tag: Tag label to filter by.
        max_results: Maximum transactions to return (default 100, raise for large exports).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list("/transactions", _transaction_params(since, until, status, category, tag), max_results, cursor)


@mcp.tool()
def get_transaction(transaction_id: str) -> str:
    """Retrieve a single transaction by its ID.

    Args:
        transaction_id: The unique identifier for the transaction.
    """
    return _ok(_get(f"/transactions/{transaction_id}"))


@mcp.tool()
def list_account_transactions(
    account_id: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    max_results: int = 100,
    cursor: Optional[str] = None,
) -> str:
    """List transactions for a specific Up Bank account.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored; the cursor already encodes the
    original filters and position.

    Args:
        account_id: The unique identifier for the account.
        since: ISO-8601 datetime to filter from.
        until: ISO-8601 datetime to filter up to.
        status: Filter by status — HELD or SETTLED.
        category: Category slug to filter by.
        tag: Tag label to filter by.
        max_results: Maximum transactions to return (default 100).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list(f"/accounts/{account_id}/transactions", _transaction_params(since, until, status, category, tag), max_results, cursor)


# ── Categories ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_categories(parent_category_id: Optional[str] = None) -> str:
    """List all spending categories. Not paginated — returns the full list.

    Args:
        parent_category_id: If provided, return only children of this category
            (e.g. 'good-life', 'home', 'transport').
    """
    params: dict = {}
    if parent_category_id:
        params["filter[parent]"] = parent_category_id
    return _ok(_get("/categories", params))


@mcp.tool()
def get_category(category_id: str) -> str:
    """Retrieve a single category and its parent/child relationships.

    Args:
        category_id: The unique identifier for the category (e.g. 'groceries').
    """
    return _ok(_get(f"/categories/{category_id}"))


@mcp.tool()
def update_transaction_category(
    transaction_id: str,
    category_id: Optional[str] = None,
) -> str:
    """Set or clear the category on a transaction.

    Args:
        transaction_id: The unique identifier for the transaction.
        category_id: The category ID to assign, or None/omit to remove the category.
    """
    body = {
        "data": {"type": "categories", "id": category_id} if category_id else None
    }
    _patch(f"/transactions/{transaction_id}/relationships/category", body)
    return json.dumps({"success": True, "transaction_id": transaction_id, "category_id": category_id})


# ── Tags ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_tags(
    max_results: int = 500,
    cursor: Optional[str] = None,
) -> str:
    """List all tags used across transactions.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored.

    Args:
        max_results: Maximum number of tags to return (default 500).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list("/tags", {"page[size]": 100}, max_results, cursor)


@mcp.tool()
def add_tags_to_transaction(transaction_id: str, tag_labels: list[str]) -> str:
    """Add one or more tags to a transaction. Tags are created if they don't exist.

    Args:
        transaction_id: The unique identifier for the transaction.
        tag_labels: List of tag labels to add (e.g. ['Holiday', 'Work']).
    """
    body = {"data": [{"type": "tags", "id": label} for label in tag_labels]}
    _post(f"/transactions/{transaction_id}/relationships/tags", body)
    return json.dumps({"success": True, "transaction_id": transaction_id, "tags_added": tag_labels})


@mcp.tool()
def remove_tags_from_transaction(transaction_id: str, tag_labels: list[str]) -> str:
    """Remove one or more tags from a transaction.

    Args:
        transaction_id: The unique identifier for the transaction.
        tag_labels: List of tag labels to remove.
    """
    body = {"data": [{"type": "tags", "id": label} for label in tag_labels]}
    _delete(f"/transactions/{transaction_id}/relationships/tags", body)
    return json.dumps({"success": True, "transaction_id": transaction_id, "tags_removed": tag_labels})


# ── Attachments ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_attachments(
    max_results: int = 200,
    cursor: Optional[str] = None,
) -> str:
    """List all receipt/file attachments across transactions.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored.

    Args:
        max_results: Maximum number of attachments to return (default 200).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list("/attachments", {"page[size]": 100}, max_results, cursor)


@mcp.tool()
def get_attachment(attachment_id: str) -> str:
    """Retrieve a single attachment including its temporary download URL.

    Args:
        attachment_id: The unique identifier for the attachment.
    """
    return _ok(_get(f"/attachments/{attachment_id}"))


# ── Webhooks ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_webhooks(
    max_results: int = 100,
    cursor: Optional[str] = None,
) -> str:
    """List all configured webhooks.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored.

    Args:
        max_results: Maximum number of webhooks to return (default 100).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list("/webhooks", {"page[size]": 100}, max_results, cursor)


@mcp.tool()
def get_webhook(webhook_id: str) -> str:
    """Retrieve a single webhook by its ID.

    Args:
        webhook_id: The unique identifier for the webhook.
    """
    return _ok(_get(f"/webhooks/{webhook_id}"))


@mcp.tool()
def create_webhook(url: str, description: Optional[str] = None) -> str:
    """Create a new webhook to receive transaction events.

    Args:
        url: The HTTPS URL to POST events to (max 300 characters).
        description: Optional description for the webhook (max 64 characters).
    """
    attrs: dict = {"url": url}
    if description:
        attrs["description"] = description
    return _ok(_post("/webhooks", {"data": {"attributes": attrs}}))


@mcp.tool()
def delete_webhook(webhook_id: str) -> str:
    """Delete a webhook.

    Args:
        webhook_id: The unique identifier for the webhook to delete.
    """
    _delete(f"/webhooks/{webhook_id}")
    return json.dumps({"success": True, "webhook_id": webhook_id})


@mcp.tool()
def ping_webhook(webhook_id: str) -> str:
    """Send a test PING event to a webhook URL to verify delivery.

    Args:
        webhook_id: The unique identifier for the webhook to ping.
    """
    return _ok(_post(f"/webhooks/{webhook_id}/ping", {}))


@mcp.tool()
def list_webhook_delivery_logs(
    webhook_id: str,
    max_results: int = 100,
    cursor: Optional[str] = None,
) -> str:
    """List delivery log entries for a webhook showing success/failure history.

    Returns {"data": [...]}. If results were cut short by the response size limit, next_cursor is
    also included — call this tool again with cursor=<next_cursor> to fetch the next page.
    When cursor is supplied all other arguments are ignored.

    Args:
        webhook_id: The unique identifier for the webhook.
        max_results: Maximum number of log entries to return (default 100).
        cursor: Opaque pagination cursor from next_cursor in a previous response.
    """
    return _list(f"/webhooks/{webhook_id}/logs", {"page[size]": 100}, max_results, cursor)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
