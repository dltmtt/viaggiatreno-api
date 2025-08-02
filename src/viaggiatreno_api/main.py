"""ViaggiaTreno API command-line utilities.

This script provides tools for querying train and station data from the ViaggiaTreno API, including station search, train status, and data export features.
"""

import csv
import json
import string
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from functools import partial
from http import HTTPStatus
from io import StringIO
from itertools import chain
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

import click
import requests

BASE_URI = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"
MIN_CSV_COLUMNS = 2
STATION_CODE_LENGTH = 6
MAX_RESULTS_TO_SHOW = 10

# Rate limiting and retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF_DELAY = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_DELAY = 60.0  # seconds

# Region code to name mapping
REGIONS = {
    0: "Italia",
    1: "Lombardia",
    2: "Liguria",
    3: "Piemonte",
    4: "Valle d'Aosta",
    5: "Lazio",
    6: "Umbria",
    7: "Molise",
    8: "Emilia Romagna",
    9: "Trentino-Alto Adige",
    10: "Friuli-Venezia Giulia",
    11: "Marche",
    12: "Veneto",
    13: "Toscana",
    14: "Sicilia",
    15: "Basilicata",
    16: "Puglia",
    17: "Calabria",
    18: "Campania",
    19: "Abruzzo",
    20: "Sardegna",
    21: "Provincia autonoma di Trento",
    22: "Provincia autonoma di Bolzano",
}


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """ViaggiaTreno API tools."""


class UnreachableCodeReachedError(RuntimeError):
    """Exception raised when unreachable code is executed."""

    def __init__(self) -> None:
        """Initialize the UnreachableCodeReachedError exception."""
        super().__init__("Unreachable code reached")


def api_request(endpoint: str, *args: str) -> dict | list | str:
    """Make API call returning JSON or text based on content headers with exponential backoff on 403."""
    url = f"{BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == HTTPStatus.FORBIDDEN and attempt < MAX_RETRIES:
                delay = min(
                    INITIAL_BACKOFF_DELAY * (BACKOFF_MULTIPLIER**attempt),
                    MAX_BACKOFF_DELAY,
                )
                click.echo(
                    f"Temporarily banned, retrying in {delay:.1f}s... "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(delay)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            # Retry only if it's the last attempt or not a 403
            if attempt == MAX_RETRIES or (
                hasattr(e.response, "status_code")
                and e.response.status_code != HTTPStatus.FORBIDDEN
            ):
                raise

        # Determine response type based on content headers
        content_type = r.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            return r.json()
        return r.text

    # This should never be reached
    raise UnreachableCodeReachedError


def resolve_station_code(station_input: str) -> str:
    """Resolve station input to station code.

    If input looks like a station code (S#####), return as-is.
    Otherwise, search for station by name.
    """
    # Check if input is already a station code
    if (
        station_input.upper().startswith("S")
        and len(station_input) == STATION_CODE_LENGTH
        and station_input[1:].isdigit()
    ):
        return station_input.upper()

    # Search for station by name
    try:
        response = api_request("autocompletaStazione", station_input)
    except requests.RequestException as e:
        msg = f"Error searching for station '{station_input}': {e}"
        raise click.ClickException(msg) from e
    else:
        # Parse response data
        stations = list(csv.reader(StringIO(response), delimiter="|"))

        if not stations:
            msg = f"No stations found matching '{station_input}'"
            raise click.ClickException(msg)

        # If only one result, use it
        if len(stations) == 1:
            station_name, station_code = stations[0][0], stations[0][1]
            click.echo(f"Using station: {station_name} ({station_code})")
            return station_code

        # Multiple results - show options
        click.echo(f"Multiple stations found matching '{station_input}':")
        for i, row in enumerate(stations[:MAX_RESULTS_TO_SHOW], 1):
            station_name, station_code = row[0], row[1]
            click.echo(f"  {i}. {station_name} ({station_code})")

        if len(stations) > MAX_RESULTS_TO_SHOW:
            remaining_count = len(stations) - MAX_RESULTS_TO_SHOW
            click.echo(f"  ... and {remaining_count} more results")

        # Ask user to choose
        choice = click.prompt(
            "Please choose a station number (or 0 to cancel)", type=int
        )
        if choice == 0 or choice > len(stations):
            msg = "Selection cancelled or invalid"
            raise click.ClickException(msg)

        station_name, station_code = stations[choice - 1][0], stations[choice - 1][1]
        click.echo(f"Selected: {station_name} ({station_code})")
        return station_code


def output_data(
    data: list | dict | None,
    output: str | TextIO | None,
    success_message: str = "Data saved",
) -> None:
    """Output data either to console or file, unless it's empty."""
    if (
        data is None
        or (isinstance(data, (list, dict)) and len(data) == 0)
        or (isinstance(data, str) and not data.strip())
    ):
        if output:
            if isinstance(output, str):
                click.echo(
                    f"⚠ Skipping empty data - not writing to {click.format_filename(output)}"
                )
            else:
                click.echo(
                    f"⚠ Skipping empty data - not writing to {click.format_filename(output.name)}"
                )
        else:
            click.echo("⚠ No data to display")
        return

    if isinstance(data, (dict, list)):
        formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        formatted_data = str(data)

    if output:
        if isinstance(output, str):
            # Handle legacy string path case (used in bulk operations)
            output_file = Path(output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(formatted_data, encoding="utf-8")
            click.echo(f"✓ {success_message} to {click.format_filename(output)}")
        else:
            # Handle click.File() object
            output.write(formatted_data)
            click.echo(f"✓ {success_message} to {click.format_filename(output.name)}")
    else:
        click.echo(formatted_data)


@cli.command("elencoStazioni")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all regions.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("region", type=click.IntRange(0, len(REGIONS) - 1), required=False)
def elenco_stazioni(
    region: int | None, output: TextIO | None, *, download_all: bool
) -> None:
    """Get all stations from a given region or from all regions."""
    if download_all:
        with ThreadPoolExecutor(max_workers=len(REGIONS)) as executor:
            fetch_stations_by_region = partial(api_request, "elencoStazioni")
            results = list(executor.map(fetch_stations_by_region, REGIONS))

        stations = list(chain.from_iterable(filter(None, results)))
        output_data(
            stations, output, f"Saved {len(stations)} stations from all regions"
        )
    elif region is not None:
        stations = api_request("elencoStazioni", str(region))
        output_data(
            stations,
            output,
            f"Saved {len(stations)} stations for region {region} ({REGIONS[region]})",
        )
    else:
        click.echo(
            f"Error: Specify a region number (0-{len(REGIONS) - 1}) or use -a/--all"
        )


@cli.command("cercaStazione")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("prefix", type=str, required=False)
def cerca_stazione(
    prefix: str | None, output: TextIO | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the cercaStazione endpoint."""
    if download_all:
        with ThreadPoolExecutor(max_workers=len(string.ascii_uppercase)) as executor:
            fetch_stations_by_letter = partial(api_request, "cercaStazione")
            results = list(
                executor.map(fetch_stations_by_letter, string.ascii_uppercase)
            )

        stations = list(chain.from_iterable(filter(None, results)))
        output_data(stations, output, f"Saved {len(stations)} results")
    elif prefix:
        stations = api_request("cercaStazione", prefix)
        output_data(stations, output, f"Saved {len(stations)} results")
    else:
        click.echo("Error: Specify a prefix or use -a/--all")


def autocompleta_stazione_handler(
    endpoint_name: str,
    output: TextIO | None,
    prefix: str | None,
    *,
    download_all: bool,
) -> None:
    """Search for stations with a specific prefix or download all stations using the specified autocompleta* endpoint."""
    if download_all:
        with ThreadPoolExecutor(max_workers=len(string.ascii_uppercase)) as executor:
            fetch_stations_by_letter = partial(api_request, endpoint_name)
            results = list(
                executor.map(fetch_stations_by_letter, string.ascii_uppercase)
            )

        stations = "\n".join(filter(None, map(str.strip, results)))
        count = stations.count("\n") + 1

        output_data(stations, output, f"Saved {count} results")
    elif prefix:
        stations = api_request(endpoint_name, prefix).strip()
        count = stations.count("\n") + 1 if stations else 0

        output_data(stations, output, f"Saved {count} results")
    else:
        click.echo("Error: Specify a prefix or use -a/--all")


@cli.command("autocompletaStazione")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("prefix", type=str, required=False)
def autocompleta_stazione(
    prefix: str | None, output: TextIO | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazione endpoint."""
    autocompleta_stazione_handler(
        "autocompletaStazione", output, prefix, download_all=download_all
    )


@cli.command("autocompletaStazioneImpostaViaggio")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("prefix", type=str, required=False)
def autocompleta_stazione_imposta_viaggio(
    prefix: str | None, output: TextIO | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazioneImpostaViaggio endpoint."""
    autocompleta_stazione_handler(
        "autocompletaStazioneImpostaViaggio",
        output,
        prefix,
        download_all=download_all,
    )


@cli.command("autocompletaStazioneNTS")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("prefix", type=str, required=False)
def autocompleta_stazione_nts(
    prefix: str | None, output: TextIO | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazioneNTS endpoint."""
    autocompleta_stazione_handler(
        "autocompletaStazioneNTS", output, prefix, download_all=download_all
    )


@cli.command("regione")
@click.argument("station", type=str, required=False)
@click.option(
    "--table",
    is_flag=True,
    help="Show table of region codes and names.",
)
def regione(station: str | None, *, table: bool) -> None:
    """Get the region code for a station or show the region code table.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    Use --table to show the correspondence between region codes and names.
    """
    if table:
        # Show the table of region codes and names
        table_data = (
            f"Codice\tRegione\n------\t{'-' * max(map(len, REGIONS.values()))}\n"
        )
        table_data += "\n".join(f"{code:>6}\t{name}" for code, name in REGIONS.items())

        output_data(table_data.strip(), None, "Saved region table")
        return

    if not station:
        click.echo(
            "Error: Specify a station or use --table to show region codes", err=True
        )
        return

    try:
        station_code = resolve_station_code(station)
        region = api_request("regione", station_code).strip()

        try:
            region = int(region)
        except ValueError:
            region = -1
            click.echo(f"Cannot retrieve region code for station {station_code}")

        output_data(region, None, f"Saved region code for station {station_code}")
    except requests.RequestException as e:
        click.echo(f"Error fetching region for station {station}: {e}", err=True)
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


@cli.command("dettaglioStazione")
@click.argument("station", type=str)
@click.option(
    "--region",
    type=click.IntRange(0, len(REGIONS) - 1),
    help=f"Region code (0-{len(REGIONS) - 1}). If not provided, it will be retrieved using the regione endpoint.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
def dettaglio_stazione(station: str, region: int | None, output: TextIO | None) -> None:
    """Get detailed station information.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    """
    station_code = resolve_station_code(station)

    # Get region code if not provided
    if region is None:
        click.echo(f"Getting region code for station {station_code}...")
        try:
            region = api_request("regione", station_code).strip()

            try:
                region = int(region)
            except ValueError:
                region = -1
                click.echo(
                    f"Cannot automatically retrieve region code for station {station_code}"
                )

            region_name = REGIONS.get(region, "Unknown Region")
            click.echo(f"Using region: {region} ({region_name})")
        except requests.RequestException as e:
            click.echo(f"Error fetching region for station {station}: {e}", err=True)
            return

    try:
        response = api_request("dettaglioStazione", station_code, str(region))
        output_data(response, output, "Saved station details")
    except requests.RequestException as e:
        click.echo(f"Error fetching station details for {station}: {e}", err=True)


def partenze_arrivi_handler(
    endpoint: str, station: str, search_datetime: datetime, output: str | None
) -> None:
    """Handle fetching station schedule data (partenze or arrivi)."""
    try:
        station_code = resolve_station_code(station)

        formatted_datetime = search_datetime.strftime("%a %b %-d %Y %H:%M:%S")

        response = api_request(endpoint, station_code, formatted_datetime)
        output_data(response, output, f"Saved {endpoint}")
    except requests.RequestException as e:
        click.echo(f"Error fetching {endpoint} for station {station}: {e}", err=True)
    except ValueError as e:
        click.echo(f"Error parsing datetime: {e}", err=True)
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


def partenze_arrivi_all_handler(
    endpoint: str, search_datetime: datetime, read_from: TextIO, output: str | None
) -> None:
    """Handle fetching station schedule data (partenze or arrivi) for all stations."""
    click.echo(f"Loading station data from {click.format_filename(read_from.name)}...")

    stations = list(
        csv.DictReader(read_from, delimiter="|", fieldnames=["name", "code"])
    )

    click.echo(f"Processing all {len(stations)} stations for {endpoint}...")

    stats = {"successful": 0, "failed": 0}

    with ThreadPoolExecutor() as executor:
        formatted_datetime = search_datetime.strftime("%a %b %-d %Y %H:%M:%S")

        # Map used to keep track of futures and their corresponding station info
        futures = {
            executor.submit(
                api_request,
                endpoint,
                station["code"],
                formatted_datetime,
            ): station
            for station in stations
        }

        for future in as_completed(futures):
            station_code, station_name = (
                futures[future]["code"],
                futures[future]["name"],
            )

            try:
                result = future.result()

                filename = f"{station_code}_{search_datetime.replace(microsecond=0).isoformat()}_{endpoint}.json"
                output_dir = Path(output or "dumps") / endpoint
                output_path = output_dir / filename

                output_data(
                    result,
                    str(output_path),
                    f"Saved {endpoint} for {station_name} ({station_code})",
                )

                stats["successful"] += 1
            except requests.RequestException as e:
                stats["failed"] += 1
                click.echo(
                    f"✗ Failed to fetch {endpoint} for {station_name} ({station_code}): {e}"
                )

    summary = textwrap.dedent(f"""
    ✅ Completed processing all stations for {endpoint}:
       • Successful fetches: {stats["successful"]}
       • Failed fetches: {stats["failed"]}
       • Skipped empty data: {len(stations) - stats["successful"] - stats["failed"]}
       • Results saved in {output_dir}
    """)
    click.echo(summary)


@cli.command("partenze")
@click.argument("station", type=str, required=False)
@click.option(
    "--datetime",
    "search_datetime",
    type=click.DateTime(["%Y-%m-%dT%H:%M:%S", "%H:%M"]),
    help="Date and time to search for (defaults to current date and time). Example: 2024-06-02T20:00:00.",
)
@click.option(
    "-a",
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch departures for all stations from the stations file.",
)
@click.option(
    "-r",
    "--read-from",
    type=click.File("r"),
    default="dumps/autocompletaStazione.csv",
    help="Path to stations file (default: dumps/autocompletaStazione.csv). Only used with -a/--all.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Save output to file, or directory when using --all (default: dumps).",
)
def partenze(
    station: str,
    search_datetime: datetime | None,
    read_from: TextIO,
    output: str | None,
    *,
    fetch_all: bool,
) -> None:
    """Get departures from a station at a specific date and time.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    Use -a/--all to fetch departures for all stations in the stations file.
    """
    # If no datetime was provided, default to current date and time
    if search_datetime is None:
        search_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))

    # If no date was provided, default to today's date
    if search_datetime.date() == date(1900, 1, 1):
        today = datetime.now(tz=ZoneInfo("Europe/Rome")).date()
        search_datetime = search_datetime.replace(
            year=today.year, month=today.month, day=today.day
        )

    if fetch_all:
        if station:
            click.echo("Warning: STATION argument ignored when using --all", err=True)
        partenze_arrivi_all_handler("partenze", search_datetime, read_from, output)
    else:
        if not station:
            click.echo(
                "Error: STATION argument is required when not using --all", err=True
            )
            return
        partenze_arrivi_handler("partenze", station, search_datetime, output)


@cli.command("arrivi")
@click.argument("station", type=str, required=False)
@click.option(
    "--datetime",
    "search_datetime",
    type=click.DateTime(["%Y-%m-%dT%H:%M:%S", "%H:%M"]),
    help="Date and time to search for (defaults to current date and time).",
)
@click.option(
    "-a",
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch arrivals for all stations from the stations file.",
)
@click.option(
    "-r",
    "--read-from",
    type=click.File("r"),
    default="dumps/autocompletaStazione.csv",
    help="Path to stations file (default: dumps/autocompletaStazione.csv). Only used with --all.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Save output to file, or directory when using --all (default: dumps).",
)
def arrivi(
    station: str,
    search_datetime: datetime | None,
    read_from: TextIO,
    output: str | None,
    *,
    fetch_all: bool,
) -> None:
    """Get arrivals at a station at a specific date and time.

    STATION can be either a station name (e.g., 'Roma Termini') or a station code (e.g., S05000).
    Use -a/--all to fetch arrivals for all stations in the stations file.
    """
    # If no datetime was provided, default to current date and time
    if search_datetime is None:
        search_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))

    # If no date was provided, default to today's date
    if search_datetime.date() == date(1900, 1, 1):
        today = datetime.now(tz=ZoneInfo("Europe/Rome")).date()
        search_datetime = search_datetime.replace(
            year=today.year, month=today.month, day=today.day
        )

    if fetch_all:
        if station:
            click.echo(
                "Warning: STATION argument ignored when using -a/--all", err=True
            )
        partenze_arrivi_all_handler("arrivi", search_datetime, read_from, output)
    else:
        if not station:
            click.echo(
                "Error: STATION argument is required when not using -a/--all", err=True
            )
            return
        partenze_arrivi_handler("arrivi", station, search_datetime, output)


@cli.command("cercaNumeroTrenoTrenoAutocomplete")
@click.argument("numero_treno", type=int)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
def cerca_numero_treno_treno_autocomplete(
    numero_treno: int, output: TextIO | None
) -> None:
    """Get autocomplete suggestions for a train number."""
    try:
        response = api_request("cercaNumeroTrenoTrenoAutocomplete", str(numero_treno))
        output_data(response, output, "Saved train number autocomplete results")
    except requests.RequestException as e:
        click.echo(
            f"Error fetching autocomplete for train number {numero_treno}: {e}",
            err=True,
        )


@cli.command("cercaNumeroTreno")
@click.argument("numero_treno", type=int)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
def cerca_numero_treno(numero_treno: int, output: TextIO | None) -> None:
    """Get detailed information for a train number."""
    try:
        response = api_request("cercaNumeroTreno", str(numero_treno))
        output_data(response, output, "Saved train number details")
    except requests.RequestException as e:
        click.echo(
            f"Error fetching details for train number {numero_treno}: {e}", err=True
        )


@cli.command("andamentoTreno")
@click.option(
    "-s",
    "--departure-station",
    type=str,
    help="Departure station name or code in format S##### (e.g., 'Milano Centrale' or S01700). If not provided, it will be retrieved using cercaNumeroTreno.",
)
@click.option(
    "--date",
    "search_date",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Train departure date (e.g., 2025-07-22). If not provided, it will be retrieved using cercaNumeroTreno.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("numero_treno", type=int)
def andamento_treno(
    departure_station: str | None,
    search_date: datetime | None,
    numero_treno: int,
    output: TextIO | None,
) -> None:
    """Get detailed train status and journey information."""
    try:
        # If station or date not provided, get them from cercaNumeroTreno
        if not departure_station or not search_date:
            click.echo(f"Fetching train details for train {numero_treno}...")
            train_info = api_request("cercaNumeroTreno", str(numero_treno))

            if not departure_station:
                departure_station = train_info["codLocOrig"]
                click.echo(
                    f"Using departure station: {departure_station} ({train_info['descLocOrig']})"
                )
            else:
                departure_station = resolve_station_code(departure_station)

            if not search_date:
                millis = train_info["millisDataPartenza"]
                search_date = train_info["dataPartenza"]
                click.echo(f"Using departure date: {search_date}")
            else:
                user_date = search_date.replace(tzinfo=ZoneInfo("UTC"))
                millis = str(int(user_date.timestamp() * 1000))
        else:
            departure_station = resolve_station_code(departure_station)
            user_date = search_date.replace(tzinfo=ZoneInfo("UTC"))
            millis = str(int(user_date.timestamp() * 1000))

        click.echo(
            f"Fetching train status for train {numero_treno} departing from {departure_station} on {search_date}..."
        )
        response = api_request(
            "andamentoTreno", departure_station, str(numero_treno), str(millis)
        )
        output_data(response, output, "Saved train status")

    except requests.RequestException as e:
        click.echo(
            f"Error fetching train status for train {numero_treno}: {e}", err=True
        )
    except ValueError as e:
        click.echo(f"Error parsing date: {e}", err=True)
    except KeyError as e:
        click.echo(f"Error: Missing field in train info response: {e}", err=True)
    except click.ClickException:
        raise  # Re-raise click exceptions


if __name__ == "__main__":
    cli()
