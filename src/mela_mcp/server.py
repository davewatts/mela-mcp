"""Mela MCP Server - Recipe database and meal scheduling integration."""

import os
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from . import database
from . import calendar
from . import meal_log
from . import reminders

mcp = FastMCP("mela")

CALENDAR_NAME = os.environ.get("MELA_CALENDAR_NAME", "Family")
GROCERY_LIST = os.environ.get("MELA_GROCERY_LIST", "Groceries")


@mcp.tool()
def search_recipes(query: str) -> list[dict]:
    """Search recipes by name or ingredients.

    Args:
        query: Search term to match against recipe title or ingredients

    Returns:
        List of matching recipes with id, title, prep_time, cook_time, total_time
    """
    return database.search_recipes(query)


@mcp.tool()
def get_recipe(recipe_id: int) -> dict | None:
    """Get full details for a specific recipe.

    Args:
        recipe_id: The recipe's ID number

    Returns:
        Full recipe details including title, ingredients, instructions, notes,
        nutrition, yield, times, favorite status, want_to_cook status, and link
    """
    return database.get_recipe(recipe_id)


@mcp.tool()
def set_recipe_nutritional_information(recipe_id: int, nutrition: str) -> dict | None:
    """Set the nutritional information for a recipe.

    Updates the nutritional information record held against an identified recipe.

    Args:
        recipe_id: The recipe's ID number
        nutrition: The nutritional information string to set

    Returns:
        Full updated recipe details or None if recipe not found
    """
    return database.set_recipe_nutritional_information(recipe_id, nutrition)


@mcp.tool()
def list_recipes(filter: str = "all") -> list[dict]:
    """List all recipes with optional filter.

    Args:
        filter: One of "all", "favorites", or "want_to_cook"

    Returns:
        List of recipes with id, title, favorite, want_to_cook
    """
    return database.list_recipes(filter)


@mcp.tool()
def get_scheduled_meals(days: int = 7, past_days: int = 0) -> list[dict]:
    """Get meals scheduled from the calendar, including past and future dates.

    Args:
        days: Number of days to look ahead (default 7)
        past_days: Number of days to look back (default 0). Use this to see
            what was previously scheduled, e.g. past_days=30 to see the last month.

    Returns:
        List of scheduled meals with title, date, time
    """
    return calendar.get_scheduled_meals(CALENDAR_NAME, days, past_days)


@mcp.tool()
def schedule_meal(recipe_name: str, date: str, time: str = "18:00") -> dict:
    """Schedule a meal on the calendar.

    Args:
        recipe_name: Name of the meal/recipe to schedule
        date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
        time: Time in HH:MM 24-hour format (default "18:00" for 6 PM)

    Returns:
        Dict with success status and event details
    """
    recipe_id = None
    recipe_zid = None
    matches = database.search_recipes(recipe_name)
    for m in matches:
        if m["title"].lower() == recipe_name.lower():
            recipe_id = m["id"]
            recipe_zid = database.get_recipe_zid(recipe_id)
            break
    result = calendar.schedule_meal(CALENDAR_NAME, recipe_name, date, time, recipe_zid=recipe_zid)
    if result.get("success"):
        meal_log.log_meal(
            date=date,
            title=recipe_name,
            recipe_id=recipe_id,
            status="planned",
        )
    return result


@mcp.tool()
def log_meal(
    title: str,
    date: str | None = None,
    tags: str | None = None,
    recipe_id: int | None = None,
    portions: int | None = None,
    notes: str | None = None,
) -> dict:
    """Log a meal that was cooked or eaten.

    Args:
        title: Name of the meal
        date: Date in YYYY-MM-DD format (defaults to today)
        tags: Comma-separated tags (e.g. "quick,vegetarian")
        recipe_id: Optional Mela recipe ID to link
        portions: Number of portions made
        notes: Any notes about the meal

    Returns:
        The created meal log entry
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    return meal_log.log_meal(
        date=date,
        title=title,
        recipe_id=recipe_id,
        tags=tags,
        status="cooked",
        portions=portions,
        notes=notes,
    )


@mcp.tool()
def update_meal_log(
    meal_id: int,
    status: str | None = None,
    notes: str | None = None,
    tags: str | None = None,
) -> dict:
    """Update an existing meal log entry.

    Args:
        meal_id: ID of the meal log entry to update
        status: New status (planned/cooked/skipped)
        notes: Updated notes
        tags: Updated comma-separated tags

    Returns:
        The updated meal log entry
    """
    return meal_log.update_meal(meal_id, status=status, notes=notes, tags=tags)


@mcp.tool()
def get_meal_history(
    days: int = 30,
    tags: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Get meal log history.

    Args:
        days: Number of days to look back (default 30)
        tags: Filter by comma-separated tags
        status: Filter by status (planned/cooked/skipped)

    Returns:
        List of meal log entries matching the filters
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    return meal_log.get_meals(
        start_date=start_date,
        end_date=end_date,
        status=status,
        tags=tags,
    )


@mcp.tool()
def review_recent_meals(days: int = 7) -> list[dict]:
    """Review recently planned meals that haven't been marked as cooked or skipped.

    Args:
        days: Number of days to look back (default 7)

    Returns:
        List of unreconciled planned meals
    """
    return meal_log.get_unreconciled(days=days)


@mcp.tool()
def get_meal_suggestions(days_back: int = 90) -> dict:
    """Get meal suggestions based on cooking history.

    Analyzes tag frequency and identifies meals that haven't been cooked recently
    to help with meal planning variety.

    Args:
        days_back: Number of days of history to analyze (default 90)

    Returns:
        Dict with novelty_candidates (stale meals), tag_frequency, and
        frequent_adhoc (meals without a recipe_id cooked 3+ times)
    """
    tag_freq = meal_log.get_tag_frequency(days=days_back)
    stale = meal_log.get_stale_meals(days=days_back, min_gap=30)

    # Find frequent ad-hoc meals (no recipe_id, cooked 3+ times)
    all_meals = meal_log.get_meals(
        start_date=(datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
    )
    adhoc_counts: dict[str, int] = {}
    for m in all_meals:
        if m.get("recipe_id") is None and m.get("status") == "cooked":
            adhoc_counts[m["title"]] = adhoc_counts.get(m["title"], 0) + 1
    frequent_adhoc = [
        {"title": title, "count": count}
        for title, count in sorted(adhoc_counts.items(), key=lambda x: -x[1])
        if count >= 3
    ]

    # Compute over/under-represented tags relative to average
    avg = sum(tag_freq.values()) / len(tag_freq) if tag_freq else 0
    over_tags = {t: c for t, c in tag_freq.items() if c > avg * 1.5} if avg else {}
    under_tags = {t: c for t, c in tag_freq.items() if c < avg * 0.5} if avg else {}

    return {
        "novelty_candidates": stale,
        "tag_frequency": tag_freq,
        "over_represented_tags": over_tags,
        "under_represented_tags": under_tags,
        "frequent_adhoc_meals": frequent_adhoc,
    }


@mcp.tool()
def get_scheduled_ingredients(days: int = 7) -> list[dict]:
    """Get raw ingredients for meals scheduled on the calendar.

    Matches calendar event titles to Mela recipes and returns their
    ingredient lists. Use this to build a grocery list from upcoming meals.

    Args:
        days: Number of days to look ahead (default 7)

    Returns:
        List of dicts per scheduled meal with title, date, ingredients
        (raw text), and matched status (True, "fuzzy", or False).
        Ingredients is None for meals with no matching recipe.
    """
    meals = calendar.get_scheduled_meals(CALENDAR_NAME, days)
    titles = [m["title"] for m in meals]
    if not titles:
        return []

    ingredient_data = database.get_ingredients_for_scheduled_meals(titles)
    ingredient_map = {item["title"]: item for item in ingredient_data}

    results = []
    for meal in meals:
        info = ingredient_map.get(meal["title"], {})
        results.append({
            "title": meal["title"],
            "date": meal["date"],
            "ingredients": info.get("ingredients"),
            "matched": info.get("matched", False),
            "recipe_title": info.get("recipe_title"),
        })
    return results


@mcp.tool()
def add_grocery_items(items: list[str], list_name: str = GROCERY_LIST) -> dict:
    """Add items to the grocery list in Apple Reminders.

    Args:
        items: List of grocery item strings (e.g. ["2 onions", "500g chicken"])
        list_name: Name of the Reminders list (default from MELA_GROCERY_LIST env var)

    Returns:
        Dict with success status and count of items added
    """
    return reminders.add_reminders(items, list_name)


@mcp.tool()
def clear_grocery_list(list_name: str = GROCERY_LIST) -> dict:
    """Clear all incomplete items from the grocery list in Apple Reminders.

    Use this before repopulating with a fresh grocery list.

    Args:
        list_name: Name of the Reminders list (default from MELA_GROCERY_LIST env var)

    Returns:
        Dict with success status and count of items removed
    """
    return reminders.clear_reminders(list_name)


@mcp.tool()
def get_grocery_list(list_name: str = GROCERY_LIST) -> dict:
    """Get the current grocery list from Apple Reminders.

    Returns all incomplete (unchecked) items from the list.

    Args:
        list_name: Name of the Reminders list (default from MELA_GROCERY_LIST env var)

    Returns:
        Dict with success status and list of item names
    """
    return reminders.get_reminders(list_name)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
