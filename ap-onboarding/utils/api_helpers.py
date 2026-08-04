def raise_for_central_response(response, action, ok_codes=(200,)):
    """Raise RuntimeError if response code is not in ok_codes."""
    code = response.get("code") if isinstance(response, dict) else response["code"]
    if code not in ok_codes:
        msg = response.get("msg") if isinstance(response, dict) else response["msg"]
        raise RuntimeError(f"{action} failed — HTTP {code}: {msg}")


def raise_for_glp_response(response, action):
    """Raise RuntimeError if GLP response code != 200 or status != SUCCEEDED."""
    raise_for_central_response(response, action)
    status = response.get("msg", {}).get("status")
    if status != "SUCCEEDED":
        raise RuntimeError(f"{action} failed — status: {status}")


def name_id_map_from_scope(scope_iter, name_attr="name", id_attr="id"):
    """Build a {name: id} dict from any iterable of scope objects."""
    return {getattr(item, name_attr): getattr(item, id_attr) for item in scope_iter}


def paginate_api(fetch_page, limit):
    """Fetch paginated items by repeatedly calling fetch_page(offset, limit)."""
    offset = 0
    total = None
    all_items = []

    while True:
        page_items, page_total = fetch_page(offset, limit)
        if total is None:
            total = page_total

        if page_items:
            all_items.extend(page_items)

        if not page_items:
            break
        if total is not None and len(all_items) >= total:
            break

        offset += limit

    return all_items
