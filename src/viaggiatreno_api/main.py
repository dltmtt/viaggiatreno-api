"""ViaggiaTreno API command-line utilities.

This script provides tools for querying train and station data from the ViaggiaTreno API, including station search, train status, and data export features.
"""

import asyncio
import atexit
import csv
import json
import string
import textwrap
import time
from datetime import date, datetime
from http import HTTPStatus
from io import StringIO
from itertools import chain
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

import aiohttp
import click

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


class UnreachableCodeReachedError(RuntimeError):
    """Exception raised when unreachable code is executed."""

    def __init__(self) -> None:
        """Initialize the UnreachableCodeReachedError exception."""
        super().__init__("Unreachable code reached. This is unexpected.")


class API:
    """Class for making API calls to the ViaggiaTreno service with exponential backoff on 403 errors."""

    BASE_URI = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"

    lock = asyncio.Lock()
    backoff_until = 0.0  # Monotonic time
    session: aiohttp.ClientSession | None = None

    MAX_CONCURRENT_REQUESTS = 16

    MAX_RETRIES = 6
    INITIAL_BACKOFF = 4.0
    BACKOFF_FACTOR = 2.0

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp session."""
        if cls.session is None or cls.session.closed:
            cls.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return cls.session

    @classmethod
    async def close_session(cls) -> None:
        """Close the shared aiohttp session."""
        if cls.session is not None and not cls.session.closed:
            await cls.session.close()
            cls.session = None

    @classmethod
    def cleanup_session_sync(cls) -> None:
        """Clean up session synchronously for atexit."""
        asyncio.run(cls.close_session())

    @classmethod
    async def get(cls, endpoint: str, *args: str | int) -> dict | list | str:
        """Make API call returning JSON or text based on content headers with exponential backoff on 403."""
        url = f"{cls.BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"
        session = await cls.get_session()

        for attempt in range(1, cls.MAX_RETRIES + 1):
            # Wait if currently under global backoff
            async with cls.lock:
                wait_time = cls.backoff_until - time.monotonic()
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            async with session.get(url) as r:
                if r.status == HTTPStatus.FORBIDDEN and attempt < cls.MAX_RETRIES:
                    delay = cls.INITIAL_BACKOFF * (cls.BACKOFF_FACTOR**attempt)

                    async with cls.lock:
                        now = time.monotonic()
                        if cls.backoff_until <= now:
                            cls.backoff_until = now + delay

                    await asyncio.sleep(delay)
                    continue

                r.raise_for_status()

                # Determine response type based on content headers
                content_type = r.headers.get("Content-Type", "").lower()
                if "application/json" in content_type:
                    return await r.json()
                return await r.text()

        # This should never be reached
        raise UnreachableCodeReachedError


# Register cleanup function to run when program exits
atexit.register(API.cleanup_session_sync)


def run_async_command(f: callable) -> callable:
    """Allow async functions to be used as click commands."""

    def wrapper(*args: object, **kwargs: object) -> object:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """ViaggiaTreno API tools."""


async def resolve_station_code(station_input: str) -> str:
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

    # If not a code, search for station by name
    response = await API.get("autocompletaStazione", station_input)

    # Parse response as CSV with line format "STATION_NAME|STATION_CODE"
    stations = list(csv.reader(StringIO(response), delimiter="|"))

    if not stations:
        msg = f"No stations found matching '{station_input}'."
        raise click.ClickException(msg)

    # If only one result is found, return it directly
    if len(stations) == 1:
        station_name, station_code = stations[0]
        return station_code

    # If multiple results are found, show options
    click.echo(f"Multiple stations found matching '{station_input}':")
    for i, station in enumerate(stations[:MAX_RESULTS_TO_SHOW], 1):
        station_name, station_code = station
        click.echo(f"  {i}. {station_name} ({station_code})")

    if len(stations) > MAX_RESULTS_TO_SHOW:
        remaining_count = len(stations) - MAX_RESULTS_TO_SHOW
        click.echo(f"  ...and {remaining_count} more results.")

    choice = click.prompt("Please choose a station number (or 0 to cancel)", type=int)
    if choice == 0 or choice > len(stations):
        msg = "Selection cancelled or invalid."
        raise click.ClickException(msg)

    station_name, station_code = stations[choice - 1]

    return station_code


async def resolve_train_details(train_number: int) -> tuple[str, datetime]:
    """Associate train number with departure station code and departure date.

    Uses cercaNumeroTrenoTrenoAutocomplete to handle ambiguous train numbers.

    Args:
        train_number (int): The train number to resolve.

    Returns:
        tuple[str, datetime]: A tuple containing the departure station code and departure date as a datetime object.

    """
    response = await API.get("cercaNumeroTrenoTrenoAutocomplete", train_number)

    # Parse response as CSV with line format "TRAIN_NUMBER - STATION_NAME - DEPARTURE_DATE|TRAIN_NUMBER-STATION_CODE-DEPARTURE_DATE_MS"
    trains = list(csv.reader(StringIO(response), delimiter="|"))

    if not trains:
        msg = f"No trains found with number {train_number}."
        raise click.ClickException(msg)

    # If only one result is found, return it directly
    if len(trains) == 1:
        human_readable_part, machine_readable_part = trains[0]
        station_name = human_readable_part.split(" - ")[1]
        station_code = machine_readable_part.split("-")[1]
        departure_date_ms = machine_readable_part.split("-")[2]
        departure_date = datetime.fromtimestamp(
            int(departure_date_ms) / 1000, tz=ZoneInfo("Europe/Rome")
        )

        click.echo(
            f"Using train: {train_number} departing from {station_name} ({station_code}) on {departure_date.date()}."
        )

        return station_code, departure_date

    # Multiple results found, show options
    click.echo(f"Multiple trains found with number {train_number}:")
    for i, train in enumerate(trains[:MAX_RESULTS_TO_SHOW], 1):
        human_readable_part, machine_readable_part = train
        station_name = human_readable_part.split(" - ")[1]
        station_code = machine_readable_part.split("-")[1]
        departure_date_ms = machine_readable_part.split("-")[2]
        departure_date = datetime.fromtimestamp(
            int(departure_date_ms) / 1000, tz=ZoneInfo("Europe/Rome")
        )

        click.echo(
            f"  {i}. Train {train_number} departing from {station_name} ({station_code}) on {departure_date.date()}."
        )

    if len(trains) > MAX_RESULTS_TO_SHOW:
        remaining_count = len(trains) - MAX_RESULTS_TO_SHOW
        click.echo(f"  ...and {remaining_count} more results.")

    choice = click.prompt("Please choose a train number (or 0 to cancel)", type=int)
    if choice == 0 or choice > len(trains):
        msg = "Selection cancelled or invalid."
        raise click.ClickException(msg)

    human_readable_part, machine_readable_part = trains[choice - 1]
    station_name = human_readable_part.split(" - ")[1]
    station_code = machine_readable_part.split("-")[1]
    departure_date_ms = machine_readable_part.split("-")[2]
    departure_date = datetime.fromtimestamp(
        int(departure_date_ms) / 1000, tz=ZoneInfo("Europe/Rome")
    )

    click.echo(
        f"Selected: Train {train_number} departing from {station_name} ({station_code}) on {departure_date.date()}."
    )
    return station_code, departure_date


@cli.command("statistiche")
@run_async_command
async def statistiche() -> None:
    """Show statistics about the ViaggiaTreno API."""
    now_ms = int(time.time_ns() / 1_000_000)
    response = await API.get("statistiche", now_ms)
    click.echo(json.dumps(response, indent=2, ensure_ascii=False))


@cli.command("elencoStazioni")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Return the results of elencoStazioni called with each region merged into a single JSON.",
)
@click.argument("region", type=click.IntRange(0, len(REGIONS) - 1), required=False)
@run_async_command
async def elenco_stazioni(region: int | None, *, download_all: bool) -> None:
    """Get all stations from a given region or from all regions."""
    if download_all:
        tasks = [API.get("elencoStazioni", region) for region in REGIONS]
        results = await asyncio.gather(*tasks)

        stations = list(chain.from_iterable(filter(None, results)))
        click.echo(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    if region is not None:
        stations = await API.get("elencoStazioni", region)
        click.echo(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    msg = f"Specify a region number (0-{len(REGIONS) - 1}) or use -a/--all to fetch stations from all regions."
    raise click.ClickException(msg)


@cli.command("cercaStazione")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Return the results of cercaStazione called with each letter from A to Z merged into a single JSON.",
)
@click.argument("prefix", type=str, required=False)
@run_async_command
async def cerca_stazione(prefix: str | None, *, download_all: bool) -> None:
    """Search for stations with a specific prefix or download all stations using the cercaStazione endpoint."""
    if download_all:
        tasks = [API.get("cercaStazione", letter) for letter in string.ascii_uppercase]
        results = await asyncio.gather(*tasks)

        stations = list(chain.from_iterable(filter(None, results)))
        click.echo(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    if prefix:
        stations = await API.get("cercaStazione", prefix)

        if not stations:
            msg = f"No stations found matching prefix '{prefix}'."
            raise click.ClickException(msg)

        click.echo(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    msg = "Specify a prefix or use -a/--all to fetch all stations."
    raise click.ClickException(msg)


async def autocompleta_stazione_handler(
    endpoint_name: str, prefix: str | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the specified autocompleta* endpoint."""
    if download_all:
        tasks = [API.get(endpoint_name, letter) for letter in string.ascii_uppercase]
        results = await asyncio.gather(*tasks)

        stations = "\n".join(filter(None, map(str.strip, results)))
        click.echo(stations.strip())
        return

    if prefix:
        stations = await API.get(endpoint_name, prefix)

        if not stations:
            msg = f"No stations found matching prefix '{prefix}'."
            raise click.ClickException(msg)

        click.echo(stations)
        return

    msg = "Specify a prefix or use -a/--all to fetch all stations."
    raise click.ClickException(msg)


@cli.command("autocompletaStazione")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Return the results of autocompletaStazione called with each letter from A to Z merged into a single CSV.",
)
@click.argument("prefix", type=str, required=False)
@run_async_command
async def autocompleta_stazione(prefix: str | None, *, download_all: bool) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazione endpoint."""
    await autocompleta_stazione_handler(
        "autocompletaStazione", prefix, download_all=download_all
    )


@cli.command("autocompletaStazioneImpostaViaggio")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Return the results of autocompletaStazione called with each letter from A to Z merged into a single CSV.",
)
@click.argument("prefix", type=str, required=False)
@run_async_command
async def autocompleta_stazione_imposta_viaggio(
    prefix: str | None, *, download_all: bool
) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazioneImpostaViaggio endpoint."""
    await autocompleta_stazione_handler(
        "autocompletaStazioneImpostaViaggio", prefix, download_all=download_all
    )


@cli.command("autocompletaStazioneNTS")
@click.option(
    "-a",
    "--all",
    "download_all",
    is_flag=True,
    help="Return the results of autocompletaStazioneNTS called with each letter from A to Z merged into a single CSV.",
)
@click.argument("prefix", type=str, required=False)
@run_async_command
async def autocompleta_stazione_nts(prefix: str | None, *, download_all: bool) -> None:
    """Search for stations with a specific prefix or download all stations using the autocompletaStazioneNTS endpoint."""
    await autocompleta_stazione_handler(
        "autocompletaStazioneNTS", prefix, download_all=download_all
    )


@cli.command("regione")
@click.argument("station", type=str, required=False)
@click.option(
    "--table",
    is_flag=True,
    help="Show table of region codes and names.",
)
@run_async_command
async def regione(station: str | None, *, table: bool) -> None:
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
        click.echo(table_data)
        return

    if not station:
        msg = "Specify a station or use --table to show region codes."
        raise click.ClickException(msg)

    station_code = await resolve_station_code(station)
    region = await API.get("regione", station_code)

    if not region:
        click.echo(f"Region code not available for station {station_code}.")
        return

    click.echo(
        f"Region for station {station_code}: {region} ({REGIONS.get(region, 'Unknown Region')})."
    )


@cli.command("dettaglioStazione")
@click.argument("station", type=str)
@click.option(
    "--region",
    type=click.IntRange(0, len(REGIONS) - 1),
    help="Region code. If not provided, it will be retrieved using the regione endpoint.",
)
@run_async_command
async def dettaglio_stazione(station: str, region: int | None) -> None:
    """Get detailed station information.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    """
    station_code = await resolve_station_code(station)

    # Get region code if not provided
    if region is None:
        region = await API.get("regione", station_code)

    if region == "":
        click.echo(
            f"Region code not available for station {station_code}. Calling dettaglioStazione with region -1."
        )
        region = -1

    response = await API.get("dettaglioStazione", station_code, region)
    if not response:
        click.echo(
            f"No details found for station {station_code}. Either the station does not exist or there are no details available."
        )
        return

    click.echo(json.dumps(response, indent=2, ensure_ascii=False))


@cli.command("cercaNumeroTrenoTrenoAutocomplete")
@click.argument("train_number", type=int)
@run_async_command
async def cerca_numero_treno_treno_autocomplete(train_number: int) -> None:
    """Get autocomplete suggestions for a train number."""
    response = await API.get("cercaNumeroTrenoTrenoAutocomplete", train_number)
    if not response:
        click.echo(f"No results found for train number {train_number}.")
        return

    click.echo(response.strip())


@cli.command("cercaNumeroTreno")
@click.argument("train_number", type=int)
@run_async_command
async def cerca_numero_treno(train_number: int) -> None:
    """Get detailed information for a train number."""
    response = await API.get("cercaNumeroTreno", train_number)
    if not response:
        click.echo(f"No results found for train number {train_number}.")
        return

    click.echo(json.dumps(response, indent=2, ensure_ascii=False))


async def partenze_arrivi_all(
    endpoint: str, read_from: TextIO, search_datetime: datetime, output: Path | None
) -> list[dict] | None:
    """Fetch departures or arrivals for all stations in the provided file."""
    if not output:
        output = Path("dumps")

    output = output / endpoint

    click.echo(f"Loading station data from {click.format_filename(read_from.name)}...")

    stations = list(csv.reader(read_from, delimiter="|"))

    click.echo(f"Processing all {len(stations)} stations for {endpoint}...")

    formatted_datetime = search_datetime.strftime("%a %b %-d %Y %H:%M:%S")
    stats = {"saved": 0, "empty": 0}
    all_trains = []

    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(API.MAX_CONCURRENT_REQUESTS)

    async def fetch_station_data(
        station_code: str,
    ) -> tuple[str, list[dict] | None]:
        async with semaphore:
            return station_code, await API.get(
                endpoint, station_code, formatted_datetime
            )

    tasks = [fetch_station_data(station[1]) for station in stations]

    with click.progressbar(length=len(tasks)) as bar:
        for coro in asyncio.as_completed(tasks):
            station_code, trains = await coro
            bar.update(1)

            if not trains:
                stats["empty"] += 1
                continue

            human_readable_date = search_datetime.replace(microsecond=0).isoformat()
            filename = f"{station_code}_{human_readable_date}_{endpoint}.json"
            output_path = output / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(trains, f, indent=2, ensure_ascii=False)

            all_trains.extend(trains)
            stats["saved"] += 1

    summary = textwrap.dedent(f"""
    ✅ Completed processing all stations for {endpoint}:
        - {stats["saved"]} results saved.
        - {stats["empty"]} empty results not saved.
    Results saved in {output}.
    """)
    click.echo(summary)
    return all_trains


async def partenze_arrivi(  # noqa: PLR0913
    endpoint: str,
    station: str | None,
    search_datetime: datetime | None,
    read_from: TextIO,
    output: Path | None,
    *,
    fetch_all: bool,
) -> list[dict] | None:
    """Get departures or arrivals from a station at a specific date and time.

    If no datetime was provided, default to current date and time.
    station can be either a station name (e.g., 'Roma Termini') or a station code (e.g., S08409).
    If fetch_all is True, fetch data for all stations in the stations file specified by read_from.

    Args:
        endpoint (str): The API endpoint to call ('partenze' or 'arrivi').
        station (str): The station name or code.
        search_datetime (datetime | None): The date and time to search for.
        read_from (TextIO): The file containing station data.
        output (Path | None): The directory to save output files. If None, print to console if fetch_all is False, otherwise save to the default default directory.
        fetch_all (bool): Whether to fetch data for all stations.

    Returns:
        list[dict] | None: A list of train data dictionaries or None if no data found.

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

        return await partenze_arrivi_all(endpoint, read_from, search_datetime, output)

    if not station:
        msg = "STATION argument is required when not using -a/--all."
        raise click.ClickException(msg)

    if output:
        click.echo("Warning: Output option ignored when not using -a/--all.", err=True)

    station_code = await resolve_station_code(station)
    formatted_datetime = search_datetime.strftime("%a %b %-d %Y %H:%M:%S")
    response = await API.get(endpoint, station_code, formatted_datetime)

    if not response:
        click.echo("No results found.")
        return None

    click.echo(json.dumps(response, indent=2, ensure_ascii=False))
    return response


@cli.command("partenze")
@click.argument("station", type=str, required=False)
@click.option(
    "--datetime",
    "search_datetime",
    type=click.DateTime(["%Y-%m-%dT%H:%M:%S", "%H:%M"]),
    help="Date and time to search for (default: now).",
)
@click.option(
    "-a",
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch departures for all stations.",
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
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    default="dumps",
    help="Directory to save output files (default: dumps). Only used with -a/--all.",
)
@run_async_command
async def partenze(
    station: str | None,
    search_datetime: datetime | None,
    read_from: TextIO,
    output: Path | None,
    *,
    fetch_all: bool,
) -> None:
    """Get departures from a station at a specific date and time.

    If no datetime was provided, default to current date and time.
    STATION can be either a station name (e.g., 'Roma Termini') or a station code (e.g., S08409).
    Use -a/--all to fetch departures for all stations in the stations file specified by read_from.
    """
    await partenze_arrivi(
        "partenze", station, search_datetime, read_from, output, fetch_all=fetch_all
    )


@cli.command("arrivi")
@click.argument("station", type=str, required=False)
@click.option(
    "--datetime",
    "search_datetime",
    type=click.DateTime(["%Y-%m-%dT%H:%M:%S", "%H:%M"]),
    help="Date and time to search for (default: now).",
)
@click.option(
    "-a",
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch arrivals for all stations.",
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
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    default="dumps",
    help="Directory to save output files (default: dumps). Only used with -a/--all.",
)
@run_async_command
async def arrivi(
    station: str | None,
    search_datetime: datetime | None,
    read_from: TextIO,
    output: Path | None,
    *,
    fetch_all: bool,
) -> None:
    """Get arrivals at a station at a specific date and time.

    If no datetime was provided, default to current date and time.
    STATION can be either a station name (e.g., 'Roma Termini') or a station code (e.g., S08409).
    Use -a/--all to fetch arrivals for all stations in the stations file specified by read_from.
    """
    await partenze_arrivi(
        "arrivi", station, search_datetime, read_from, output, fetch_all=fetch_all
    )


async def andamento_treno_bulk(trains: set[tuple[int, str, int]], output: Path) -> None:
    """Process andamentoTreno for a set of trains in bulk."""
    click.echo(f"Processing andamentoTreno for {len(trains)} unique trains...")

    output_path = output / "andamentoTreno"
    stats = {"saved": 0, "empty": 0}
    now = datetime.now(tz=ZoneInfo("Europe/Rome")).isoformat()

    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(API.MAX_CONCURRENT_REQUESTS)

    async def fetch_train_data(
        train: tuple[int, str, int],
    ) -> tuple[tuple[int, str, int], dict | None]:
        async with semaphore:
            result = await API.get(
                "andamentoTreno",
                train[1],  # station_code
                train[0],  # train_number
                train[2],  # departure_date_ms
            )
            return train, result

    tasks = [fetch_train_data(train) for train in trains]

    with click.progressbar(length=len(tasks)) as bar:
        for coro in asyncio.as_completed(tasks):
            train, result = await coro
            bar.update(1)

            if not result:
                stats["empty"] += 1
                continue

            human_readable_date = (
                datetime.fromtimestamp(train[2] / 1000, tz=ZoneInfo("Europe/Rome"))
                .date()
                .isoformat()
            )
            filename = (
                f"{train[0]}_{train[1]}_{human_readable_date}_{now}_andamentoTreno.json"
            )
            file_path = output_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            stats["saved"] += 1

    summary = textwrap.dedent(f"""
    ✅ Completed processing all trains for andamentoTreno:
        - {stats["saved"]} results saved.
        - {stats["empty"]} empty results not saved.
    Results saved in {output_path}.
    """)
    click.echo(summary)


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
    "departure_date",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Train departure date. If not provided, it will be retrieved using cercaNumeroTrenoTrenoAutocomplete.",
)
@click.argument("train_number", type=int)
@run_async_command
async def andamento_treno(
    departure_station: str | None, train_number: int, departure_date: datetime | None
) -> None:
    """Get detailed train status and journey information."""
    if not departure_station or not departure_date:
        departure_station, departure_date = await resolve_train_details(train_number)
    else:
        departure_station = await resolve_station_code(departure_station)

    departure_date_ms = int(departure_date.timestamp() * 1000)
    response = await API.get(
        "andamentoTreno", departure_station, train_number, departure_date_ms
    )

    if not response:
        click.echo(
            f"No results found for train {train_number} departing from {departure_station} on {departure_date.date()}."
        )
        return

    click.echo(json.dumps(response, indent=2, ensure_ascii=False))


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
    type=click.File("r"),
    default="dumps/autocompletaStazione.csv",
    help="Path to stations CSV file (default: dumps/autocompletaStazione.csv).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    default="dumps",
    help="Output directory for all data (default: dumps).",
)
@run_async_command
async def dynamic_dump(
    search_datetime: datetime | None,
    read_from: TextIO,
    output: Path | None,
) -> None:
    """Comprehensive data dump: fetch partenze, arrivi, and andamentoTreno for all stations.

    Fetch departures and arrivals for all stations from the API, then extract train information to fetch detailed train status data via andamentoTreno.
    """
    now = datetime.now(tz=ZoneInfo("Europe/Rome"))

    # If no datetime was provided, default to current date and time
    if search_datetime is None:
        search_datetime = now

    # If no date was provided, default to today's date
    if search_datetime.date() == date(1900, 1, 1):
        today = now.date()
        search_datetime = search_datetime.replace(
            year=today.year, month=today.month, day=today.day
        )

    click.echo("Fetching departures for all stations...")
    departures = await partenze_arrivi(
        "partenze", None, search_datetime, read_from, output, fetch_all=True
    )

    # Reset file pointer to the beginning
    read_from.seek(0)

    click.echo("Fetching arrivals for all stations...")
    arrivals = await partenze_arrivi(
        "arrivi", None, search_datetime, read_from, output, fetch_all=True
    )

    # Extract train information from collected data
    trains = {
        (
            int(train["numeroTreno"]),
            str(train["codOrigine"]),
            int(train["dataPartenzaTreno"]),
        )
        for train in departures + arrivals
        if train["numeroTreno"] and train["codOrigine"] and train["dataPartenzaTreno"]
    }

    click.echo("Fetching detailed train status for all unique trains...")
    await andamento_treno_bulk(trains, output)

    click.echo("🎉 Dynamic dump completed successfully!")


if __name__ == "__main__":
    cli()
