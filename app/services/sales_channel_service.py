SALES_CHANNEL_PRESENTATION = (
    ("online_store", "Online Store"),
    ("point_of_sale", "Point of Sale"),
    ("shop", "Shop"),
    ("draft_orders", "Draft Orders"),
    ("facebook_instagram", "Facebook & Instagram"),
    ("other_app_specific_channels", "Other/app-specific channels"),
)


def categorize_sales_channel(source_name: str) -> str:
    """Map a Shopify sourceName to a stable merchant-facing category ID."""
    normalized = source_name.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"web", "online_store", "shopify_online_store"}:
        return "online_store"
    if normalized in {"pos", "shopify_pos"}:
        return "point_of_sale"
    if normalized in {"shop", "shop_app"}:
        return "shop"
    if normalized in {"shopify_draft_order", "draft_order", "draft_orders"}:
        return "draft_orders"
    if any(token in normalized for token in ("facebook", "instagram", "meta")):
        return "facebook_instagram"
    return "other_app_specific_channels"


def group_sales_channels(
    source_names: tuple[str, ...],
) -> list[tuple[str, str, list[str]]]:
    """Group exact PostgreSQL sources without inventing unavailable options."""
    grouped = {category_id: [] for category_id, _name in SALES_CHANNEL_PRESENTATION}
    for source_name in source_names:
        grouped[categorize_sales_channel(source_name)].append(source_name)

    return [
        (category_id, name, grouped[category_id])
        for category_id, name in SALES_CHANNEL_PRESENTATION
        if grouped[category_id]
    ]
