"""SQLite database access for Mela recipe database."""

import os
import sqlite3
from pathlib import Path

DB_FILENAME = os.environ.get("MELA_DATABASE_FILENAME", "Curcuma.sqlite")
DB_PATH = Path.home() / "Library/Group Containers/66JC38RDUD.recipes.mela/Data" / DB_FILENAME


def get_connection() -> sqlite3.Connection:
    """Get a connection to the Mela database.
    
    Uses the database file specified by the MELA_DATABASE_FILENAME environment
    variable (defaults to "Curcuma.sqlite" if not set).
    
    Raises:
        FileNotFoundError: If the database file is not found at the expected path.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Mela database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def search_recipes(query: str) -> list[dict]:
    """Search recipes by name or ingredients.

    Args:
        query: Search term to match against recipe title or ingredients

    Returns:
        List of matching recipes with id, title, prep_time, cook_time, total_time
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT
                Z_PK as id,
                ZTITLE as title,
                ZPREPTIME as prep_time,
                ZCOOKTIME as cook_time,
                ZTOTALTIME as total_time
            FROM ZRECIPEOBJECT
            WHERE ZTITLE LIKE ? OR ZINGREDIENTS LIKE ?
            ORDER BY ZTITLE
            """,
            (f"%{query}%", f"%{query}%")
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_recipe(recipe_id: int) -> dict | None:
    """Get full recipe details by ID.

    Args:
        recipe_id: The recipe's primary key (Z_PK)

    Returns:
        Full recipe details or None if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT
                Z_PK as id,
                ZTITLE as title,
                ZINGREDIENTS as ingredients,
                ZINSTRUCTIONS as instructions,
                ZNOTES as notes,
                ZNUTRITION as nutrition,
                ZYIELD as yield,
                ZPREPTIME as prep_time,
                ZCOOKTIME as cook_time,
                ZTOTALTIME as total_time,
                ZFAVORITE as favorite,
                ZWANTTOCOOK as want_to_cook,
                ZLINK as link
            FROM ZRECIPEOBJECT
            WHERE Z_PK = ?
            """,
            (recipe_id,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result["favorite"] = bool(result["favorite"])
            result["want_to_cook"] = bool(result["want_to_cook"])
            return result
        return None
    finally:
        conn.close()


def get_recipe_zid(recipe_id: int) -> str | None:
    """Get the ZID (source identifier) for a recipe by its primary key.

    Args:
        recipe_id: The recipe's primary key (Z_PK)

    Returns:
        The ZID string or None if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT ZID FROM ZRECIPEOBJECT WHERE Z_PK = ?",
            (recipe_id,)
        )
        row = cursor.fetchone()
        return row["ZID"] if row else None
    finally:
        conn.close()


def get_ingredients_for_scheduled_meals(meal_titles: list[str]) -> list[dict]:
    """Look up raw ingredients for a list of meal titles.

    Uses case-insensitive exact match on ZTITLE, then LIKE fallback for
    unmatched titles.

    Args:
        meal_titles: List of meal/recipe titles from the calendar

    Returns:
        List of dicts with title, ingredients (raw text or None),
        and matched (True, "fuzzy", or False)
    """
    conn = get_connection()
    try:
        results = []
        for title in meal_titles:
            # Try exact case-insensitive match first
            cursor = conn.execute(
                "SELECT ZTITLE, ZINGREDIENTS FROM ZRECIPEOBJECT WHERE ZTITLE COLLATE NOCASE = ?",
                (title,)
            )
            row = cursor.fetchone()
            if row:
                results.append({
                    "title": title,
                    "ingredients": row["ZINGREDIENTS"],
                    "matched": True,
                })
                continue

            # Fallback: LIKE match
            cursor = conn.execute(
                "SELECT ZTITLE, ZINGREDIENTS FROM ZRECIPEOBJECT WHERE ZTITLE LIKE ? LIMIT 1",
                (f"%{title}%",)
            )
            row = cursor.fetchone()
            if row:
                results.append({
                    "title": title,
                    "recipe_title": row["ZTITLE"],
                    "ingredients": row["ZINGREDIENTS"],
                    "matched": "fuzzy",
                })
                continue

            results.append({
                "title": title,
                "ingredients": None,
                "matched": False,
            })

        return results
    finally:
        conn.close()


def list_recipes(filter: str = "all") -> list[dict]:
    """List all recipes with optional filter.

    Args:
        filter: One of "all", "favorites", or "want_to_cook"

    Returns:
        List of recipes with id, title, favorite, want_to_cook
    """
    conn = get_connection()
    try:
        base_query = """
            SELECT
                Z_PK as id,
                ZTITLE as title,
                ZFAVORITE as favorite,
                ZWANTTOCOOK as want_to_cook
            FROM ZRECIPEOBJECT
        """

        if filter == "favorites":
            query = base_query + " WHERE ZFAVORITE = 1 ORDER BY ZTITLE"
        elif filter == "want_to_cook":
            query = base_query + " WHERE ZWANTTOCOOK = 1 ORDER BY ZTITLE"
        else:
            query = base_query + " ORDER BY ZTITLE"

        cursor = conn.execute(query)
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result["favorite"] = bool(result["favorite"])
            result["want_to_cook"] = bool(result["want_to_cook"])
            results.append(result)
        return results
    finally:
        conn.close()


def set_recipe_nutritional_information(
    recipe_id: int,
    nutrition: str | None = None,
    notes: str | None = None,
    ingredients: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
) -> dict | None:
    """Set recipe information fields.

    Updates and records the nutritional information, notes, ingredients, description,
    and instructions held against an identified recipe. Only non-empty fields are updated.

    Args:
        recipe_id: The recipe's primary key (Z_PK)
        nutrition: The nutritional information string to set (optional)
        notes: The notes string to set (optional)
        ingredients: The ingredients string to set (optional)
        description: The description string to set (optional)
        instructions: The instructions string to set (optional)

    Returns:
        Updated recipe details or None if recipe not found
    """
    conn = get_connection()
    try:
        # First check if recipe exists
        cursor = conn.execute(
            "SELECT Z_PK FROM ZRECIPEOBJECT WHERE Z_PK = ?",
            (recipe_id,)
        )
        if not cursor.fetchone():
            return None

        # Build dynamic UPDATE statement based on provided parameters
        updates = []
        params = []

        if nutrition is not None and nutrition.strip():
            updates.append("ZNUTRITION = ?")
            params.append(nutrition)

        if notes is not None and notes.strip():
            updates.append("ZNOTES = ?")
            params.append(notes)

        if ingredients is not None and ingredients.strip():
            updates.append("ZINGREDIENTS = ?")
            params.append(ingredients)

        if description is not None and description.strip():
            updates.append("ZDESCRIPTION = ?")
            params.append(description)

        if instructions is not None and instructions.strip():
            updates.append("ZINSTRUCTIONS = ?")
            params.append(instructions)

        # Only execute UPDATE if there are fields to update
        if updates:
            params.append(recipe_id)
            update_sql = f"UPDATE ZRECIPEOBJECT SET {', '.join(updates)} WHERE Z_PK = ?"
            conn.execute(update_sql, params)
            conn.commit()

        # Return updated recipe details
        return get_recipe(recipe_id)
    finally:
        conn.close()
