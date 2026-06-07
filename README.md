# Mela MCP Server

MCP server for Mela recipe database and meal scheduling via Apple Calendar.

## Features

- **Recipe Access**: Search, list, and get full details from your Mela recipe database
- **Meal Scheduling**: Schedule meals on your Apple Calendar
- **Grocery Lists**: Build grocery lists from scheduled meals and manage them in Apple Reminders

## Installation

```bash
cd mela-mcp
uv sync
```

## Usage

### With Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mela": {
      "command": "uv",
      "args": ["--directory", "<PATH-TO-THIS-REPO>", "run", "mela-mcp"],
      "env": {
        "MELA_CALENDAR_NAME": "Family",
        "MELA_GROCERY_LIST": "Groceries",
        "MELA_DATABASE_FILENAME": "Curcuma.sqlite"
      }
    }
  }
}
```

## Configuration

- `MELA_CALENDAR_NAME`: Calendar name for meal scheduling (default: "Family")
- `MELA_GROCERY_LIST`: Apple Reminders list name for grocery items (default: "Groceries")
- `MELA_DATABASE_FILENAME`: Database filename to use from the Mela data directory (default: "Curcuma.sqlite")

## Tools

- `search_recipes(query)`: Search recipes by name or ingredients
- `get_recipe(recipe_id)`: Get full recipe details
- `list_recipes(filter)`: List recipes (all/favorites/want_to_cook)
- `get_scheduled_meals(days)`: Get upcoming scheduled meals
- `schedule_meal(recipe_name, date, time)`: Schedule a meal
- `get_scheduled_ingredients(days)`: Get raw ingredients for upcoming scheduled meals
- `add_grocery_items(items, list_name)`: Add items to Apple Reminders grocery list
- `clear_grocery_list(list_name)`: Clear incomplete items from grocery list
- `get_grocery_list(list_name)`: Get current incomplete grocery list items
