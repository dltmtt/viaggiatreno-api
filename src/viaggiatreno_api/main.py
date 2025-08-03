"""ViaggiaTreno API command-line utilities.

This script provides tools for querying train and station data from the ViaggiaTreno API, including station search, train status, and data export features.
"""

import csv
import json
import string
import textwrap
import threading
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

MAX_RESULTS_TO_SHOW = 10
STATION_CODE_LENGTH = 6
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


class API:
    """Class for making API calls to the ViaggiaTreno service with exponential backoff on 403 errors."""

    _BASE_URI = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"

    _lock = threading.Lock()
    _backoff_until = 0.0  # Monotonic time

    MAX_RETRIES = 6
    INITIAL_BACKOFF = 4.0
    BACKOFF_FACTOR = 2.0

    @classmethod
    def call(cls, endpoint: str, *args: str | int) -> dict | list | str:
        """Make API call returning JSON or text based on content headers with exponential backoff on 403."""
        url = f"{cls._BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"

        for attempt in range(cls.MAX_RETRIES + 1):
            # Wait if currently under global backoff
            with cls._lock:
                wait_time = cls._backoff_until - time.monotonic()
            if wait_time > 0:
                time.sleep(wait_time)

            try:
                r = requests.get(url, timeout=30)
                if r.status_code == HTTPStatus.FORBIDDEN and attempt < cls.MAX_RETRIES:
                    delay = cls.INITIAL_BACKOFF * (cls.BACKOFF_FACTOR**attempt)

                    with cls._lock:
                        now = time.monotonic()
                        if cls._backoff_until <= now:
                            cls._backoff_until = now + delay
                            click.echo(
                                f"Temporarily banned, retrying in {delay:.1f}s... "
                                f"(attempt {attempt + 1}/{cls.MAX_RETRIES})"
                            )
                    time.sleep(delay)
                    continue

                r.raise_for_status()
            except requests.RequestException as e:
                # Retry only if it's the last attempt or not a 403
                if attempt == cls.MAX_RETRIES or (
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
        response = API.call("autocompletaStazione", station_input)
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


def resolve_train_details(train_number: int) -> tuple[str, datetime]:
    """Associate train number with departure station code and departure date.

    Uses cercaNumeroTrenoTrenoAutocomplete to handle ambiguous train numbers.

    Args:
        train_number (int): The train number to resolve.

    Returns:
        tuple[str, datetime]: A tuple containing the departure station code and departure date as a datetime object.

    """
    try:
        response = API.call("cercaNumeroTrenoTrenoAutocomplete", train_number)
    except requests.RequestException as e:
        msg = f"Error searching for train {train_number}: {e}"
        raise click.ClickException(msg) from e

    # Parse response as CSV with pipe delimiter
    # Each line format: "TRAIN_NUMBER - STATION_NAME - DATE|TRAIN_NUMBER-STATION_CODE-UNIX_TIMESTAMP"
    trains = list(csv.reader(StringIO(response), delimiter="|"))

    if not trains:
        msg = f"No trains found with number {train_number}"
        raise click.ClickException(msg)

    # If only one result, use it
    if len(trains) == 1:
        human_readable_part, machine_readable_part = trains[0]
        station_name = human_readable_part.split(" - ")[1]
        _, station_code, unix_timestamp_millis = machine_readable_part.split("-")
        departure_date = datetime.fromtimestamp(
            int(unix_timestamp_millis) / 1000, tz=ZoneInfo("Europe/Rome")
        )

        click.echo(
            f"Using train: {train_number} departing from {station_name} ({station_code}) on {departure_date.date()}"
        )

        return station_code, departure_date

    # Multiple results - show options
    click.echo(f"Multiple trains found with number {train_number}:")
    for i, train in enumerate(trains[:MAX_RESULTS_TO_SHOW], 1):
        human_readable_part, machine_readable_part = train
        station_name = human_readable_part.split(" - ")[1]
        _, station_code, unix_timestamp_millis = machine_readable_part.split("-")
        departure_date = datetime.fromtimestamp(
            int(unix_timestamp_millis) / 1000, tz=ZoneInfo("Europe/Rome")
        )

        click.echo(
            f"  {i}. Train {train_number} from {station_name} ({station_code}) on {departure_date.date()}"
        )

    if len(trains) > MAX_RESULTS_TO_SHOW:
        remaining_count = len(trains) - MAX_RESULTS_TO_SHOW
        click.echo(f"  ... and {remaining_count} more results")

    # Ask user to choose
    choice = click.prompt("Please choose a train number (or 0 to cancel)", type=int)
    if choice == 0 or choice > len(trains):
        msg = "Selection cancelled or invalid"
        raise click.ClickException(msg)

    selected_train = trains[choice - 1]
    human_readable_part, machine_readable_part = selected_train
    station_name = human_readable_part.split(" - ")[1]
    _, station_code, unix_timestamp_millis = machine_readable_part.split("-")
    departure_date = datetime.fromtimestamp(
        int(unix_timestamp_millis) / 1000, tz=ZoneInfo("Europe/Rome")
    )

    click.echo(
        f"Selected: Train {train_number} departing from {station_name} ({station_code}) on {departure_date.date()}"
    )
    return station_code, departure_date


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
            fetch_stations_by_region = partial(API.call, "elencoStazioni")
            results = list(executor.map(fetch_stations_by_region, REGIONS))

        stations = list(chain.from_iterable(filter(None, results)))
        output_data(
            stations, output, f"Saved {len(stations)} stations from all regions"
        )
    elif region is not None:
        stations = API.call("elencoStazioni", region)
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
            fetch_stations_by_letter = partial(API.call, "cercaStazione")
            results = list(
                executor.map(fetch_stations_by_letter, string.ascii_uppercase)
            )

        stations = list(chain.from_iterable(filter(None, results)))
        output_data(stations, output, f"Saved {len(stations)} results")
    elif prefix:
        stations = API.call("cercaStazione", prefix)
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
            fetch_stations_by_letter = partial(API.call, endpoint_name)
            results = list(
                executor.map(fetch_stations_by_letter, string.ascii_uppercase)
            )

        stations = "\n".join(filter(None, map(str.strip, results)))
        count = stations.count("\n") + 1

        output_data(stations, output, f"Saved {count} results")
    elif prefix:
        stations = API.call(endpoint_name, prefix).strip()
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
        region = API.call("regione", station_code).strip()

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
    help="Region code. If not provided, it will be retrieved using the regione endpoint.",
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
            region = API.call("regione", station_code).strip()

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
        response = API.call("dettaglioStazione", station_code, region)
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

        response = API.call(endpoint, station_code, formatted_datetime)
        output_data(response, output, f"Saved {endpoint}")
    except requests.RequestException as e:
        click.echo(f"Error fetching {endpoint} for station {station}: {e}", err=True)
    except ValueError as e:
        click.echo(f"Error parsing datetime: {e}", err=True)
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


def partenze_arrivi_all_handler(
    endpoint: str, search_datetime: datetime, read_from: TextIO, output: str | None
) -> dict[str, list]:
    """Handle fetching station schedule data (partenze or arrivi) for all stations.

    Returns:
        dict[str, list]: A dictionary mapping station codes to their departures or arrivals.

    """
    click.echo(f"Loading station data from {click.format_filename(read_from.name)}...")

    stations = list(
        csv.DictReader(read_from, delimiter="|", fieldnames=["name", "code"])
    )

    click.echo(f"Processing all {len(stations)} stations for {endpoint}...")

    stats = {"successful": 0, "failed": 0, "empty": 0}
    departures_or_arrivals = {}

    with ThreadPoolExecutor() as executor:
        formatted_datetime = search_datetime.strftime("%a %b %-d %Y %H:%M:%S")

        # Map used to keep track of futures and their corresponding station info
        futures = {
            executor.submit(
                API.call,
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

                if not result:
                    stats["empty"] += 1

                output_data(
                    result,
                    str(output_path),
                    f"Saved {endpoint} for {station_name} ({station_code})",
                )

                departures_or_arrivals[station_code] = result

                stats["successful"] += 1
            except requests.RequestException as e:
                stats["failed"] += 1
                click.echo(
                    f"✗ Failed to fetch {endpoint} for {station_name} ({station_code}): {e}"
                )

    summary = textwrap.dedent(f"""
    ✅ Completed processing all stations for {endpoint}:
       • Successful fetches: {stats["successful"]}
         - {stats["successful"]} results saved
         - {stats["empty"]} empty results not saved
       • Failed fetches: {stats["failed"]}
       • Results saved in {output_dir}
    """)
    click.echo(summary)

    return departures_or_arrivals


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
@click.argument("train_number", type=int)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
def cerca_numero_treno_treno_autocomplete(
    train_number: int, output: TextIO | None
) -> None:
    """Get autocomplete suggestions for a train number."""
    try:
        response = API.call("cercaNumeroTrenoTrenoAutocomplete", train_number)
        output_data(response, output, "Saved train number autocomplete results")
    except requests.RequestException as e:
        click.echo(
            f"Error fetching autocomplete for train number {train_number}: {e}",
            err=True,
        )


@cli.command("cercaNumeroTreno")
@click.argument("train_number", type=int)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
def cerca_numero_treno(train_number: int, output: TextIO | None) -> None:
    """Get detailed information for a train number."""
    try:
        response = API.call("cercaNumeroTreno", train_number)
        output_data(response, output, "Saved train number details")
    except requests.RequestException as e:
        click.echo(
            f"Error fetching details for train number {train_number}: {e}", err=True
        )


def extract_trains_from_schedule(
    schedule_data: list[dict],
) -> set[tuple[int, str, int]]:
    """Extract unique train information from partenze/arrivi response data.

    Returns a set of tuples: (train_number, departure_station_code, departure_timestamp_millis)
    """
    trains = set()

    if not isinstance(schedule_data, list):
        return trains

    for train in schedule_data:
        if not isinstance(train, dict):
            continue

        # Extract required fields
        train_number = train.get("numeroTreno")
        departure_station = train.get("codOrigine")
        departure_timestamp_millis = train.get("dataPartenzaTreno")

        if train_number and departure_station and departure_timestamp_millis:
            try:
                trains.add(
                    (
                        int(train_number),
                        str(departure_station),
                        int(departure_timestamp_millis),
                    )
                )
            except (ValueError, TypeError):
                continue

    return trains


def fetch_andamento_treno_bulk(
    trains: set[tuple[int, str, int]], output_dir: str
) -> None:
    """Fetch andamentoTreno data for multiple trains in parallel."""
    if not trains:
        click.echo("No valid trains found to fetch andamentoTreno data")
        return

    click.echo(f"Processing andamentoTreno for {len(trains)} unique trains...")

    output_path = Path(output_dir)
    stats = {"successful": 0, "failed": 0}

    with ThreadPoolExecutor() as executor:
        # Map used to keep track of futures and their corresponding train info
        futures = {
            executor.submit(
                API.call,
                "andamentoTreno",
                departure_station,
                train_number,
                departure_timestamp,
            ): (train_number, departure_station, departure_timestamp)
            for train_number, departure_station, departure_timestamp in trains
        }

        for future in as_completed(futures):
            train_number, departure_station, departure_timestamp = futures[future]

            try:
                result = future.result()

                # Create filename based on train info
                departure_date = datetime.fromtimestamp(
                    departure_timestamp / 1000, tz=ZoneInfo("Europe/Rome")
                ).date()
                filename = f"{train_number}_{departure_station}_{departure_date}_andamentoTreno.json"
                output_file_path = output_path / filename

                output_data(
                    result,
                    str(output_file_path),
                    f"Saved andamentoTreno for train {train_number} from {departure_station}",
                )

                stats["successful"] += 1
            except requests.RequestException as e:
                stats["failed"] += 1
                click.echo(
                    f"✗ Failed to fetch andamentoTreno for train {train_number} from {departure_station}: {e}"
                )

    summary = textwrap.dedent(f"""
    ✅ Completed processing andamentoTreno:
       • Successful fetches: {stats["successful"]}
       • Failed fetches: {stats["failed"]}
       • Results saved in {output_path}
    """)
    click.echo(summary)


def read_schedule_data_from_files(data_dir: Path, endpoint: str) -> dict[str, list]:
    """Read partenze or arrivi data from JSON files in a directory.

    Args:
        data_dir: Directory containing the JSON files
        endpoint: Either "partenze" or "arrivi"

    Returns:
        dict[str, list]: A dictionary mapping station codes to their schedule data.

    """
    schedule_data = {}
    json_files = list(data_dir.glob(f"*_{endpoint}.json"))

    if not json_files:
        click.echo(f"⚠ No {endpoint} JSON files found in {data_dir}")
        return schedule_data

    click.echo(f"Reading {len(json_files)} {endpoint} JSON files from {data_dir}...")

    # Minimum filename parts for format: STATION_CODE_datetime_endpoint.json
    min_filename_parts = 3

    for json_file in json_files:
        try:
            # Extract station code from filename (format: STATION_CODE_datetime_endpoint.json)
            filename_parts = json_file.stem.split("_")
            if len(filename_parts) >= min_filename_parts:
                station_code = filename_parts[0]

                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    schedule_data[station_code] = data

        except (json.JSONDecodeError, OSError) as e:
            click.echo(f"✗ Failed to read {json_file}: {e}")

    click.echo(f"✓ Successfully read {endpoint} data for {len(schedule_data)} stations")
    return schedule_data


def _handle_train_status_only_mode(read_from: str | None, output: str) -> None:
    """Handle the --only-train-status mode of dynamic_dump."""
    data_dir = Path(read_from or "dumps")

    click.echo(f"Starting train status dump (reading from {data_dir})...")

    # Read partenze data from JSON files
    partenze_dir = data_dir / "partenze"
    if partenze_dir.exists():
        partenze_data = read_schedule_data_from_files(partenze_dir, "partenze")
    else:
        click.echo(f"⚠ Partenze directory not found: {partenze_dir}")
        partenze_data = {}

    # Read arrivi data from JSON files
    arrivi_dir = data_dir / "arrivi"
    if arrivi_dir.exists():
        arrivi_data = read_schedule_data_from_files(arrivi_dir, "arrivi")
    else:
        click.echo(f"⚠ Arrivi directory not found: {arrivi_dir}")
        arrivi_data = {}

    # Extract train information from loaded data
    all_trains = set()
    for data in (partenze_data, arrivi_data):
        for schedule_data in data.values():
            all_trains.update(extract_trains_from_schedule(schedule_data))

    # Fetch andamentoTreno for all unique trains
    andamento_output = str(Path(output) / "andamentoTreno")
    fetch_andamento_treno_bulk(all_trains, andamento_output)

    # Final summary for train status only mode
    partenze_loaded = len(partenze_data)
    arrivi_loaded = len(arrivi_data)

    summary = textwrap.dedent(f"""
    🎉 Train status dump completed successfully!

    Partenze:
       • Loaded from JSON files: {partenze_loaded} stations
       • Data read from: {partenze_dir}

    Arrivi:
       • Loaded from JSON files: {arrivi_loaded} stations
       • Data read from: {arrivi_dir}

    AndamentoTreno:
       • Unique trains processed: {len(all_trains)}
       • Results saved in: {andamento_output}
    """)
    click.echo(summary)


def _handle_default_mode(
    read_from: str | None, output: str, search_datetime: datetime
) -> None:
    """Handle the default mode of dynamic_dump."""
    stations_file_path = read_from or "dumps/autocompletaStazione.csv"

    click.echo(
        f"Starting dynamic dump for {search_datetime.strftime('%Y-%m-%d %H:%M:%S')}..."
    )

    # Open the stations file
    try:
        stations_path = Path(stations_file_path)
        with stations_path.open(encoding="utf-8") as stations_file:
            # Fetch partenze for all stations and collect data
            click.echo("Fetching partenze for all stations...")
            partenze_data = partenze_arrivi_all_handler(
                "partenze", search_datetime, stations_file, output
            )

            # Reset file position for second read
            stations_file.seek(0)

            # Fetch arrivi for all stations and collect data
            click.echo("Fetching arrivi for all stations...")
            arrivi_data = partenze_arrivi_all_handler(
                "arrivi", search_datetime, stations_file, output
            )

    except (OSError, FileNotFoundError) as e:
        click.echo(f"Error reading stations file '{stations_file_path}': {e}", err=True)
        return

    # Extract train information from collected data
    all_trains = set()
    for data in (partenze_data or {}, arrivi_data or {}):
        for schedule_data in data.values():
            all_trains.update(extract_trains_from_schedule(schedule_data))

    # Fetch andamentoTreno for all unique trains
    andamento_output = str(Path(output) / "andamentoTreno")
    fetch_andamento_treno_bulk(all_trains, andamento_output)

    # Final summary for default mode
    partenze_successful = len(partenze_data) if partenze_data else 0
    arrivi_successful = len(arrivi_data) if arrivi_data else 0

    summary = textwrap.dedent(f"""
    🎉 Dynamic dump completed successfully!

    Partenze:
       • Successful fetches: {partenze_successful}
       • Results saved in: {Path(output) / "partenze"}

    Arrivi:
       • Successful fetches: {arrivi_successful}
       • Results saved in: {Path(output) / "arrivi"}

    AndamentoTreno:
       • Unique trains processed: {len(all_trains)}
       • Results saved in: {andamento_output}
    """)
    click.echo(summary)


@cli.command("dynamic-dump")
@click.option(
    "--datetime",
    "search_datetime",
    type=click.DateTime(["%Y-%m-%dT%H:%M:%S", "%H:%M"]),
    help="Date and time to search for (defaults to current date and time).",
)
@click.option(
    "-r",
    "--read-from",
    help="With --only-train-status: directory containing partenze/arrivi folders (default: dumps). Otherwise: path to stations CSV file (default: dumps/autocompletaStazione.csv).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Output directory for all data (default: dumps).",
)
@click.option(
    "--only-train-status",
    is_flag=True,
    help="Skip fetching partenze/arrivi and read existing JSON files instead, then fetch only andamentoTreno data.",
)
def dynamic_dump(
    search_datetime: datetime | None,
    read_from: str | None,
    output: str | None,
    *,
    only_train_status: bool,
) -> None:
    """Comprehensive data dump: fetch partenze, arrivi, and andamentoTreno for all stations.

    This command can operate in two modes:
    1. Default mode: Fetch departures and arrivals for all stations from the API, then extract train
       information to fetch detailed train status data via andamentoTreno.
    2. With --only-train-status: Read existing partenze/arrivi JSON files and fetch only andamentoTreno data.
    """
    output = output or "dumps"

    # If no datetime was provided, default to current date and time
    if search_datetime is None:
        search_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))

    # If no date was provided, default to today's date
    if search_datetime.date() == date(1900, 1, 1):
        today = datetime.now(tz=ZoneInfo("Europe/Rome")).date()
        search_datetime = search_datetime.replace(
            year=today.year, month=today.month, day=today.day
        )

    if only_train_status:
        _handle_train_status_only_mode(read_from, output)
    else:
        _handle_default_mode(read_from, output, search_datetime)


@cli.command("andamentoTreno")
@click.option(
    "-s",
    "--departure-station",
    type=str,
    help="Either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700). If not provided, it will be retrieved using cercaNumeroTrenoTrenoAutocomplete.",
    metavar="STATION",
)
@click.option(
    "--date",
    "search_date",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Train departure date. If not provided, it will be retrieved using cercaNumeroTrenoTrenoAutocomplete.",
)
@click.option(
    "-o",
    "--output",
    type=click.File("w"),
    help="Save output to file.",
)
@click.argument("train_number", type=int)
def andamento_treno(
    departure_station: str | None,
    search_date: datetime | None,
    train_number: int,
    output: TextIO | None,
) -> None:
    """Get detailed train status and journey information."""
    try:
        # If station or date not provided, resolve them using cercaNumeroTrenoTrenoAutocomplete
        if not departure_station or not search_date:
            click.echo(f"Resolving train details for train {train_number}...")
            station_code, departure_date = resolve_train_details(train_number)

            if not departure_station:
                departure_station = station_code
            else:
                departure_station = resolve_station_code(departure_station)

            if not search_date:
                search_date = departure_date
        else:
            departure_station = resolve_station_code(departure_station)

        click.echo(
            f"Fetching train status for train {train_number} departing from {departure_station} on {search_date.date()}..."
        )
        response = API.call(
            "andamentoTreno",
            departure_station,
            train_number,
            int(search_date.timestamp() * 1000),
        )
        output_data(response, output, "Saved train status")

    except requests.RequestException as e:
        click.echo(
            f"Error fetching train status for train {train_number}: {e}", err=True
        )
    except ValueError as e:
        click.echo(f"Error parsing date: {e}", err=True)
    except KeyError as e:
        click.echo(f"Error: Missing field in train info response: {e}", err=True)
    except click.ClickException:
        raise  # Re-raise click exceptions


if __name__ == "__main__":
    cli()
