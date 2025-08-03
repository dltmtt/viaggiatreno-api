# ViaggiaTreno API - Copilot Instructions

## Project Architecture

This is a documentation project with a CLI wrapper around the ViaggiaTreno API (Italian train information service). The project consists of:

- **Single module architecture**: All CLI commands live in `src/viaggiatreno_api/main.py` (O(1k) lines)
- **API wrapper pattern**: Central `API` class handles all HTTP requests with exponential backoff for 403 errors
- **Click-based CLI**: Each ViaggiaTreno endpoint maps to a `@cli.command()` with smart parameter resolution
- **JSON Schema validation**: Response schemas in `schemas/` directory for API documentation
- **Data dumps**: `dumps/` contains example API responses for testing and development

## Critical Developer Workflows

### Running the CLI
```bash
# Primary execution method
uv run vt-api <command> [args]

# Examples with smart parameter resolution
uv run vt-api partenze "Milano Centrale"  # Station name auto-resolved to code
uv run vt-api andamentoTreno 9685         # Auto-finds departure station/date
uv run vt-api partenze --all -o dumps/    # Bulk operations with threading
```

### API Rate Limiting & Error Handling
The `API` class implements sophisticated retry logic for 403 (temporarily banned) responses:
- Exponential backoff: 4s, 8s, 16s, 32s, 64s, 128s
- Thread-safe global backoff state using `threading.Lock`
- Automatic content-type detection (JSON vs text responses)

## Project-Specific Patterns

### Station Code Resolution
- Station inputs accept both names ("Milano Centrale") and codes ("S01700")
- `resolve_station_code()` provides interactive disambiguation for multiple matches
- Station codes follow format: S + 5 digits (e.g., "S01700")

### Train Detail Resolution
A train is uniquely identified by the triple of train number, departure station code, and departure date.
- `resolve_train_details()` handles ambiguous train numbers using `cercaNumeroTrenoTrenoAutocomplete`
- Returns tuple of (station_code, departure_datetime) for `andamentoTreno` calls
- Handles multiple trains with same number via interactive selection

### Bulk Operations Pattern
- Commands support `--all` flag for processing all stations/letters
- Uses `ThreadPoolExecutor` for parallel API calls (see `partenze_arrivi_all_handler`)
- Smart output handling: individual files for `--all`, single file/stdout otherwise
- Progress tracking with success/failure/empty statistics

### Data Output Handling
- `output_data()` function centralizes JSON formatting and file writing
- Skips empty responses automatically with warning messages
- Supports both Click.File objects and string paths
- UTF-8 encoding with proper indentation for JSON

## Integration Points

### ViaggiaTreno API Specifics
- Base URI: `http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno`
- Mixed response formats: JSON for structured data, CSV/text for search endpoints
- Date format: one of "Mon Aug 3 2025 14:30:00", "2025-08-03T14:30:00", or 1754224200000, depending on the endpoint
- Italian timezone handling with `ZoneInfo("Europe/Rome")`

### Key API Endpoints Pattern
1. **Station Discovery**: `autocompletaStazione` → pipe-delimited CSV
2. **Schedule Data**: `partenze`/`arrivi` → JSON arrays
3. **Train Tracking**: `andamentoTreno` → complex nested JSON (see schema)
4. **Region Mapping**: Hardcoded `REGIONS` dict (0-22) for Italian regions

## Development Practices

- **Error handling**: Use `click.ClickException` for user-facing errors
- **Datetime handling**: Always use Europe/Rome timezone, support both ISO and short formats
- **CSV parsing**: Use `csv.reader(StringIO(response), delimiter="|")` for pipe-delimited responses
- **Threading**: Use `ThreadPoolExecutor` for bulk operations, never parallel retry logic
- **File operations**: Use `pathlib.Path` for all path manipulations
- **JSON validation**: Reference schemas in `schemas/` directory for response structure

## General Guidelines
- Use parallelism when appropriate (bulk operations, not individual requests).
- Use `uv run` to run Python scripts.
- Use `pathlib` for path manipulations.
- Use `click`-specific functions and exceptions.
- Do not try to run `--help` every time - deduce behavior from the code.
