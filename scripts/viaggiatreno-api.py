# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "requests",
# ]
# ///

import csv
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import click
import requests

BASE_URI = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"
MAX_REGION = 22
MIN_CSV_COLUMNS = 2

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


def get_json(endpoint: str, *args: str) -> dict | list:
    """Make API call expecting JSON response"""
    url = f"{BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def get_text(endpoint: str, *args: str) -> str:
    """Make API call expecting text response"""
    url = f"{BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


STATION_CODE_LENGTH = 6
MAX_RESULTS_TO_SHOW = 10


def resolve_station_code(station_input: str) -> str:
    """
    Resolve station input to station code.
    If input looks like a station code (S#####), return as-is.
    Otherwise, search for station by name.
    """
    # Check if input is already a station code
    if (
        station_input.upper().startswith("S")
        and len(station_input) == STATION_CODE_LENGTH
    ):
        return station_input.upper()

    # Search for station by name
    try:
        response = get_text("autocompletaStazione", station_input)
    except requests.RequestException as e:
        msg = f"Error searching for station '{station_input}': {e}"
        raise click.ClickException(msg) from e
    else:
        # Parse CSV data with pipe delimiter
        csv_reader = csv.reader(StringIO(response), delimiter="|")
        lines = [row for row in csv_reader if len(row) >= MIN_CSV_COLUMNS]

        if not lines:
            msg = f"No stations found matching '{station_input}'"
            raise click.ClickException(msg)

        # If only one result, use it
        if len(lines) == 1:
            station_name, station_code = lines[0][0], lines[0][1]
            click.echo(f"Using station: {station_name} ({station_code})")
            return station_code

        # Multiple results - show options
        click.echo(f"Multiple stations found matching '{station_input}':")
        for i, row in enumerate(lines[:MAX_RESULTS_TO_SHOW], 1):
            station_name, station_code = row[0], row[1]
            click.echo(f"  {i}. {station_name} ({station_code})")

        if len(lines) > MAX_RESULTS_TO_SHOW:
            remaining_count = len(lines) - MAX_RESULTS_TO_SHOW
            click.echo(f"  ... and {remaining_count} more results")

        # Ask user to choose
        choice = click.prompt(
            "Please choose a station number (or 0 to cancel)", type=int
        )
        if choice == 0 or choice > len(lines):
            msg = "Selection cancelled or invalid"
            raise click.ClickException(msg)

        station_name, station_code = lines[choice - 1][0], lines[choice - 1][1]
        click.echo(f"Selected: {station_name} ({station_code})")
        return station_code


def format_datetime_for_api(iso_string: str) -> str:
    """Convert ISO datetime string to format expected by ViaggiaTreno API"""
    if iso_string is None:
        # Use current datetime in Rome timezone (Europe/Rome)
        dt = datetime.now(tz=ZoneInfo("Europe/Rome"))
    else:
        # Parse ISO string
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))

    # Format as required by the API (similar to Date.toUTCString() format)
    # Example: "Sun Jun 2 2024 20:00:00"
    return dt.strftime("%a %b %-d %Y %H:%M:%S")


def output_data(data, output_path=None, success_message="Data saved"):
    """Helper function to output data either to console or file"""
    if isinstance(data, (dict, list)):
        formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        formatted_data = str(data)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(formatted_data, encoding="utf-8")
        print(f"✓ {success_message} to {output_path}")
    else:
        print(formatted_data)


def fetch_autocompleta_endpoint(endpoint_name) -> str:
    """Fetch data for all letters from a specific autocompleta endpoint"""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def fetch_letter(letter):
        """Fetch data for a single letter"""
        try:
            response = get_text(endpoint_name, letter)

            if not isinstance(response, str):
                print(
                    f"Error: Unexpected response type for {endpoint_name}/{letter}: {type(response)}"
                )
                return letter, ""

        except requests.RequestException as e:
            print(f"Error fetching data from {endpoint_name}/{letter}: {e}")
            return letter, ""
        else:
            return letter, response

    # Fetch all letters in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_letter, letter): letter for letter in letters}

        # Collect results and maintain order
        letter_results = {}
        for future in as_completed(futures):
            letter, response = future.result()
            letter_results[letter] = response

    # Combine results in alphabetical order
    combined_results = []
    for letter in sorted(letter_results.keys()):
        response = letter_results[letter].strip()
        if response:  # Only add non-empty responses
            combined_results.append(response)

    return "\n".join(combined_results)


def dump_single_autocompleta_endpoint(endpoint_name, output_dir="dumps") -> None:
    """Dump data from a single autocompleta endpoint"""
    Path(output_dir).mkdir(exist_ok=True)

    try:
        data = fetch_autocompleta_endpoint(endpoint_name)
        filename = Path(output_dir) / f"{endpoint_name}.csv"

        filename.write_text(data, encoding="utf-8")

        line_count = len([line for line in data.split("\n") if line.strip()])
        print(f"✓ Saved {endpoint_name} data to {filename}")
        print(f"  Found {line_count} stations")

    except (OSError, UnicodeError) as e:
        print(f"✗ Error processing {endpoint_name}: {e}")


@click.group()
@click.option(
    "-o",
    "--output",
    type=str,
    help="Save output to file or directory (behavior depends on command)",
)
@click.pass_context
def cli(ctx, output) -> None:
    """ViaggiaTreno API tools"""
    # Ensure that ctx.obj exists and store the output option
    ctx.ensure_object(dict)
    ctx.obj["output"] = output


@cli.command("elenco-stazioni")
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all regions",
)
@click.argument("region", type=int, required=False)
@click.pass_context
def elenco_stazioni(ctx, download_all, region) -> None:
    """Get stations from elencoStazioni endpoint for a specific region, or use --all to download from all regions"""
    output = ctx.obj["output"]

    def fetch_region(region_num):
        """Fetch stations for a single region"""
        try:
            response = get_json("elencoStazioni", str(region_num))
        except requests.RequestException as e:
            print(f"Error fetching data for region {region_num}: {e}")
            return region_num, []
        else:
            return region_num, response

    if download_all:
        # Download all regions
        all_stations = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(fetch_region, i): i for i in range(MAX_REGION + 1)
            }

            # Collect results and sort by region number
            region_results = {}
            for future in as_completed(futures):
                region_num, stations = future.result()
                if stations:  # Only add if we got data
                    region_results[region_num] = stations

        # Add stations in region order (0, 1, 2, ...)
        for region_num in sorted(region_results.keys()):
            all_stations.extend(region_results[region_num])

        output_data(all_stations, output, f"Saved {len(all_stations)} stations")
    elif region is not None:
        if not (0 <= region <= MAX_REGION):
            print(f"Error: Region must be between 0 and {MAX_REGION}")
            return

        _, stations = fetch_region(region)
        output_data(stations)
    else:
        print(f"Error: Specify a region number (0-{MAX_REGION}) or use --all")


@cli.command("cerca-stazione")
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters",
)
@click.argument("prefix", type=str, required=False)
@click.pass_context
def cerca_stazione(ctx, download_all, prefix):
    """Search for stations with a specific prefix, or use --all to download from all letters"""
    output = ctx.obj["output"]

    if download_all:
        # Download all data
        def fetch_letter(letter):
            """Fetch stations for a single letter"""
            try:
                response = get_json("cercaStazione", letter)
            except requests.RequestException as e:
                print(f"Error fetching data for letter {letter}: {e}")
                return letter, []
            else:
                return letter, response

        all_stations = []
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(fetch_letter, letter): letter for letter in letters
            }

            # Collect results and sort by letter
            letter_results = {}
            for future in as_completed(futures):
                letter, stations = future.result()
                if stations:  # Only add if we got data
                    letter_results[letter] = stations

        # Add stations in alphabetical order (A, B, C, ...)
        for letter in sorted(letter_results.keys()):
            all_stations.extend(letter_results[letter])

        output_data(all_stations, output, f"Saved {len(all_stations)} stations")
    elif prefix:
        # Single prefix search - print to screen or save to file
        try:
            response = get_json("cercaStazione", prefix)
            output_data(response, output, "Saved cerca-stazione results")
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")


def handle_autocompleta_command(endpoint_name, output, download_all, prefix):
    """Generic handler for autocompleta commands"""
    if download_all:
        data = fetch_autocompleta_endpoint(endpoint_name)
        if output:
            line_count = len([line for line in data.split("\n") if line.strip()])
            success_msg = f"Saved {line_count} stations"
        else:
            success_msg = "Data retrieved"
        output_data(data, output, success_msg)
    elif prefix:
        try:
            response = get_text(endpoint_name, prefix)
            output_data(response, output, f"Saved {endpoint_name} results")
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")


@cli.command("autocompleta-stazione")
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters",
)
@click.argument("prefix", type=str, required=False)
@click.pass_context
def autocompleta_stazione(ctx, download_all, prefix):
    """Search for stations with a specific prefix, or use --all to download from all letters"""
    handle_autocompleta_command(
        "autocompletaStazione", ctx.obj["output"], download_all, prefix
    )


@cli.command("autocompleta-stazione-imposta-viaggio")
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters",
)
@click.argument("prefix", type=str, required=False)
@click.pass_context
def autocompleta_stazione_imposta_viaggio(ctx, download_all, prefix):
    """Search for stations with a specific prefix, or use --all to download from all letters"""
    handle_autocompleta_command(
        "autocompletaStazioneImpostaViaggio", ctx.obj["output"], download_all, prefix
    )


@cli.command("autocompleta-stazione-nts")
@click.option(
    "--all",
    "download_all",
    is_flag=True,
    help="Download all stations from all letters",
)
@click.argument("prefix", type=str, required=False)
@click.pass_context
def autocompleta_stazione_nts(ctx, download_all, prefix):
    """Search for stations with a specific prefix, or use --all to download from all letters"""
    handle_autocompleta_command(
        "autocompletaStazioneNTS", ctx.obj["output"], download_all, prefix
    )


def dump_cerca_stazione_all(output_dir="dumps"):
    """Download all cercaStazione data"""

    def fetch_letter(letter):
        """Fetch stations for a single letter"""
        try:
            response = get_json("cercaStazione", letter)
        except requests.RequestException as e:
            print(f"Error fetching data for letter {letter}: {e}")
            return letter, []
        else:
            return letter, response

    all_stations = []
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_letter, letter): letter for letter in letters}

        # Collect results and sort by letter
        letter_results = {}
        for future in as_completed(futures):
            letter, stations = future.result()
            if stations:  # Only add if we got data
                letter_results[letter] = stations

    # Add stations in alphabetical order (A, B, C, ...)
    for letter in sorted(letter_results.keys()):
        all_stations.extend(letter_results[letter])

    # Save to output directory
    Path(output_dir).mkdir(exist_ok=True)
    with Path(f"{output_dir}/cercaStazione.json").open("w", encoding="utf-8") as f:
        json.dump(all_stations, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved cercaStazione data to {output_dir}/cercaStazione.json")
    print(f"  Found {len(all_stations)} stations")


def dump_elenco_stazioni_all(output_dir="dumps"):
    """Download all elencoStazioni data"""

    def fetch_region(region_num):
        """Fetch stations for a single region"""
        try:
            response = get_json("elencoStazioni", str(region_num))
        except requests.RequestException as e:
            print(f"Error fetching data for region {region_num}: {e}")
            return region_num, []
        else:
            return region_num, response

    all_stations = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_region, i): i for i in range(MAX_REGION + 1)}

        # Collect results and sort by region number
        region_results = {}
        for future in as_completed(futures):
            region_num, stations = future.result()
            if stations:  # Only add if we got data
                region_results[region_num] = stations

    # Add stations in region order (0, 1, 2, ...)
    for region_num in sorted(region_results.keys()):
        all_stations.extend(region_results[region_num])

    # Save to output directory
    Path(output_dir).mkdir(exist_ok=True)
    with Path(f"{output_dir}/elencoStazioni.json").open("w", encoding="utf-8") as f:
        json.dump(all_stations, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved elencoStazioni data to {output_dir}/elencoStazioni.json")
    print(f"  Found {len(all_stations)} stations")


def _validate_region_code(region):
    """Validate region code and raise ClickException if invalid."""
    if not (0 <= region <= MAX_REGION):
        msg = f"Region code must be between 0 and {MAX_REGION}"
        raise click.ClickException(msg)


def _parse_region_response(region_response):
    """Parse region response and raise ClickException if invalid."""
    try:
        return int(region_response)
    except ValueError as exc:
        msg = f"Unable to parse region code from response: {region_response}"
        raise click.ClickException(msg) from exc


@cli.command("dettaglio-stazione")
@click.argument("station", type=str)
@click.option(
    "--region",
    type=int,
    help="Region code (0-22). If not provided, will be retrieved using the regione endpoint.",
)
@click.pass_context
def dettaglio_stazione(ctx, station, region):
    """Get detailed station information.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    """
    output = ctx.obj["output"]

    # Resolve station code if needed
    station_code = resolve_station_code(station)

    # Get region code if not provided
    if region is None:
        print(f"Getting region code for station {station_code}...")
        try:
            region_response = get_text("regione", station_code).strip()
            region = _parse_region_response(region_response)
            region_name = REGIONS.get(region, "Unknown Region")
            print(f"Using region: {region} ({region_name})")
        except requests.RequestException as e:
            print(f"Error fetching region for station {station}: {e}")
            return
    else:
        _validate_region_code(region)

    try:
        # Make API call
        response = get_json("dettaglioStazione", station_code, str(region))
        output_data(response, output, "Saved station details")

    except requests.RequestException as e:
        print(f"Error fetching station details for {station}: {e}")


@cli.command("regione")
@click.argument("station", type=str, required=False)
@click.option(
    "--table",
    is_flag=True,
    help="Show table of region codes and names",
)
@click.pass_context
def regione(ctx, station, table):
    """Get the region code for a station or show the region code table.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    Use --table to show the correspondence between region codes and names.
    """
    output = ctx.obj["output"]

    if table:
        # Show the table of region codes and names
        table_data = "Codice\tRegione\n" + "------\t" + "-" * 30 + "\n"
        for code in sorted(REGIONS.keys()):
            table_data += f"{code}\t{REGIONS[code]}\n"

        output_data(table_data.strip(), output, "Saved region table")
        return

    if not station:
        print("Error: Specify a station or use --table to show region codes")
        return

    try:
        # Resolve station code if needed
        station_code = resolve_station_code(station)

        # Make API call
        response = get_text("regione", station_code).strip()

        try:
            region_code = int(response)
            region_name = REGIONS.get(region_code, "Unknown Region")

            # Format output
            if output:
                result = {
                    "stazione": station,
                    "codiceStazione": station_code,
                    "codiceRegione": region_code,
                    "nomeRegione": region_name,
                }
                output_data(result, output, "Saved region info")
            else:
                print(f"Station: {station_code}")
                print(f"Region: {region_code} ({region_name})")

        except ValueError:
            # Response is not a number, show raw response
            output_data(response, output, "Saved raw response")

    except requests.RequestException as e:
        print(f"Error fetching region for station {station}: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


def handle_station_schedule(endpoint, station, datetime_str, output):
    """Generic handler for partenze and arrivi commands"""
    try:
        station_code = resolve_station_code(station)
        formatted_datetime = format_datetime_for_api(datetime_str)
        response = get_json(endpoint, station_code, formatted_datetime)
        output_data(response, output, f"Saved {endpoint}")
    except requests.RequestException as e:
        print(f"Error fetching {endpoint} for station {station}: {e}")
    except ValueError as e:
        print(f"Error parsing datetime: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


@cli.command("partenze")
@click.argument("station", type=str)
@click.option(
    "--datetime",
    "datetime_str",
    type=str,
    help="ISO datetime string (defaults to current time). Example: 2024-06-02T20:00:00",
)
@click.pass_context
def partenze(ctx, station, datetime_str):
    """Get departures from a station at a specific date and time.

    STATION can be either a station name (e.g., 'Milano Centrale') or a station code (e.g., S01700).
    """
    handle_station_schedule("partenze", station, datetime_str, ctx.obj["output"])


@cli.command("arrivi")
@click.argument("station", type=str)
@click.option(
    "--datetime",
    "datetime_str",
    type=str,
    help="ISO datetime string (defaults to current time). Example: 2024-06-02T20:00:00",
)
@click.pass_context
def arrivi(ctx, station, datetime_str):
    """Get arrivals at a station at a specific date and time.

    STATION can be either a station name (e.g., 'Roma Termini') or a station code (e.g., S05000).
    """
    handle_station_schedule("arrivi", station, datetime_str, ctx.obj["output"])


@cli.command("cerca-numero-treno-treno-autocomplete")
@click.argument("numero_treno", type=int)
@click.pass_context
def cerca_numero_treno_treno_autocomplete(ctx, numero_treno):
    """Get autocomplete suggestions for a train number"""
    try:
        response = get_text("cercaNumeroTrenoTrenoAutocomplete", str(numero_treno))
        output_data(
            response, ctx.obj["output"], "Saved train number autocomplete results"
        )
    except requests.RequestException as e:
        print(f"Error fetching autocomplete for train number {numero_treno}: {e}")


@cli.command("cerca-numero-treno")
@click.argument("numero_treno", type=int)
@click.pass_context
def cerca_numero_treno(ctx, numero_treno):
    """Get detailed information for a train number"""
    try:
        response = get_json("cercaNumeroTreno", str(numero_treno))
        output_data(response, ctx.obj["output"], "Saved train number details")
    except requests.RequestException as e:
        print(f"Error fetching details for train number {numero_treno}: {e}")


@cli.command("andamento-treno")
@click.option(
    "-s",
    "--departure-station",
    type=str,
    help="Departure station name or code in format S##### (e.g., 'Milano Centrale' or S01700). If not provided, will be retrieved using cercaNumeroTreno.",
)
@click.option(
    "--date",
    "date_str",
    type=str,
    help="Departure date in YYYY-MM-DD format (e.g., 2025-07-22). If not provided, will be retrieved using cercaNumeroTreno.",
)
@click.argument("numero_treno", type=int)
@click.pass_context
def andamento_treno(ctx, departure_station, date_str, numero_treno):
    """Get detailed train status and journey information."""
    try:
        # If station or date not provided, get them from cercaNumeroTreno
        if not departure_station or not date_str:
            print(f"Fetching train details for train {numero_treno}...")
            train_info = get_json("cercaNumeroTreno", str(numero_treno))

            if not departure_station:
                departure_station = train_info["codLocOrig"]
                print(
                    f"Using departure station: {departure_station} ({train_info['descLocOrig']})"
                )
            else:
                departure_station = resolve_station_code(departure_station)

            if not date_str:
                millis = train_info["millisDataPartenza"]
                date_str = train_info["dataPartenza"]
                print(f"Using departure date: {date_str}")
            else:
                user_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=ZoneInfo("UTC")
                )
                millis = str(int(user_date.timestamp() * 1000))
        else:
            departure_station = resolve_station_code(departure_station)
            user_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=ZoneInfo("UTC")
            )
            millis = str(int(user_date.timestamp() * 1000))

        print(
            f"Fetching train status for train {numero_treno} departing from {departure_station} on {date_str}..."
        )
        response = get_json(
            "andamentoTreno", departure_station, str(numero_treno), str(millis)
        )
        output_data(response, ctx.obj["output"], "Saved train status")

    except requests.RequestException as e:
        print(f"Error fetching train status for train {numero_treno}: {e}")
    except ValueError as e:
        print(f"Error parsing date: {e}")
    except KeyError as e:
        print(f"Error: Missing field in train info response: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions


def get_stations_from_file(stations_file):
    """Get list of stations from a stations file"""
    stations_path = Path(stations_file)
    if not stations_path.exists():
        error_msg = (
            f"Stations file not found: {stations_file}. "
            "Please run 'autocompleta-stazione --all' to create it."
        )
        raise click.ClickException(error_msg)

    stations = []
    with stations_path.open("r", encoding="utf-8") as f:
        csv_reader = csv.reader(f, delimiter="|")
        for row in csv_reader:
            if len(row) >= MIN_CSV_COLUMNS:
                name, code = row[0], row[1]
                stations.append({"name": name, "code": code})

    if not stations:
        error_msg = f"No valid station data found in {stations_file}"
        raise click.ClickException(error_msg)

    return stations


def fetch_station_data(
    station_code: str, station_name: str, data_type: str, formatted_datetime: str
):
    """Fetch partenze or arrivi data for a single station"""
    try:
        if data_type == "partenze":
            response = get_json("partenze", station_code, formatted_datetime)
        elif data_type == "arrivi":
            response = get_json("arrivi", station_code, formatted_datetime)
        else:
            error_msg = f"Invalid data_type: {data_type}"
            raise ValueError(error_msg)
    except requests.RequestException as e:
        return {
            "success": False,
            "station_code": station_code,
            "station_name": station_name,
            "data_type": data_type,
            "error": str(e),
        }
    else:
        return {
            "success": True,
            "station_code": station_code,
            "station_name": station_name,
            "data_type": data_type,
            "data": response,
        }


def _fetch_andamento_treno_data(train_number, train_info_cache):
    """Helper function to fetch andamento treno data"""
    # Use cached train info if available, otherwise fetch it
    if train_info_cache and train_number in train_info_cache:
        train_info = train_info_cache[train_number]
    else:
        train_info = get_json("cercaNumeroTreno", str(train_number))

    if not train_info or not isinstance(train_info, dict):
        return None, "No train info available"

    departure_station = train_info.get("codLocOrig")
    millis = train_info.get("millisDataPartenza")
    if not departure_station or not millis:
        return None, "Missing departure station or time"

    response = get_json(
        "andamentoTreno", departure_station, str(train_number), str(millis)
    )
    return response, None


def _fetch_dettaglio_stazione_data(train_number, train_info_cache):
    """Helper function to fetch dettaglio stazione data"""
    # Use cached train info if available, otherwise fetch it
    if train_info_cache and train_number in train_info_cache:
        train_info = train_info_cache[train_number]
    else:
        train_info = get_json("cercaNumeroTreno", str(train_number))

    if not train_info or not isinstance(train_info, dict):
        return None, "No train info available"

    departure_station = train_info.get("codLocOrig")
    if not departure_station:
        return None, "Missing departure station"

    # Get region for the departure station
    try:
        region_response = get_text("regione", departure_station).strip()
        region = int(region_response)
    except (requests.RequestException, ValueError):
        return None, "Could not get region for departure station"

    response = get_json("dettaglioStazione", departure_station, str(region))
    return response, None


def fetch_train_data(train_number: int, endpoint: str, train_info_cache=None):
    """Fetch data for a single train number from a specific endpoint"""
    try:
        if endpoint == "cercaNumeroTreno":
            response = get_json("cercaNumeroTreno", str(train_number))
        elif endpoint == "cercaNumeroTrenoTrenoAutocomplete":
            response = get_text("cercaNumeroTrenoTrenoAutocomplete", str(train_number))
        elif endpoint == "andamentoTreno":
            response, error = _fetch_andamento_treno_data(
                train_number, train_info_cache
            )
            if error:
                return {
                    "success": False,
                    "train_number": train_number,
                    "endpoint": endpoint,
                    "error": error,
                }
        elif endpoint == "dettaglioStazione":
            response, error = _fetch_dettaglio_stazione_data(
                train_number, train_info_cache
            )
            if error:
                return {
                    "success": False,
                    "train_number": train_number,
                    "endpoint": endpoint,
                    "error": error,
                }
        else:
            return {
                "success": False,
                "train_number": train_number,
                "endpoint": endpoint,
                "error": f"Invalid endpoint: {endpoint}",
            }
    except requests.RequestException as e:
        return {
            "success": False,
            "train_number": train_number,
            "endpoint": endpoint,
            "error": str(e),
        }
    except (KeyError, ValueError, TypeError) as e:
        return {
            "success": False,
            "train_number": train_number,
            "endpoint": endpoint,
            "error": str(e),
        }
    else:
        return {
            "success": True,
            "train_number": train_number,
            "endpoint": endpoint,
            "data": response,
        }


def select_stations_for_sampling(stations, samples, fetch_all):
    """Select stations for sampling based on flags"""
    if fetch_all:
        print(f"Processing all {len(stations)} stations...")
        return stations

    if len(stations) < samples:
        print(f"Warning: Only {len(stations)} stations available, sampling all of them")
        samples = len(stations)

    sampled_stations = random.sample(stations, samples)
    print(
        f"Sampling {samples} random stations from {len(stations)} available stations..."
    )
    return sampled_stations


@cli.command("sample-stations")
@click.option(
    "-n",
    "--samples",
    type=int,
    default=50,
    help="Number of random stations to sample (default: 50)",
)
@click.option(
    "-r",
    "--read-from",
    type=str,
    default="dumps/autocompletaStazione.csv",
    help="Path to stations file (default: dumps/autocompletaStazione.csv)",
)
@click.option(
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch departures and arrivals for all stations",
)
@click.pass_context
def sample_stations(ctx, samples, read_from, fetch_all):
    """Sample random stations and fetch their departures and arrivals, or use --all to fetch from all stations.

    Results are saved to {output}/partenze and {output}/arrivi directories.
    File names follow the format: {STATION_CODE}_{ISO_DATETIME}_{TYPE}.json
    """
    output_dir = ctx.obj["output"] or "dumps"

    # Create output directories
    partenze_dir = Path(output_dir) / "partenze"
    arrivi_dir = Path(output_dir) / "arrivi"
    partenze_dir.mkdir(parents=True, exist_ok=True)
    arrivi_dir.mkdir(parents=True, exist_ok=True)

    # Get current datetime for API and filename
    now = datetime.now(tz=ZoneInfo("Europe/Rome"))
    formatted_datetime = format_datetime_for_api(None)  # Uses current time
    iso_datetime = (
        now.replace(microsecond=0).isoformat().replace(":", "-").replace("+", "_")
    )

    print(f"Loading station data from {read_from}...")
    try:
        stations = get_stations_from_file(read_from)
    except click.ClickException as e:
        print(f"Error: {e}")
        return

    sampled_stations = select_stations_for_sampling(stations, samples, fetch_all)

    # Prepare tasks for both partenze and arrivi
    tasks = []
    for station in sampled_stations:
        tasks.append((station["code"], station["name"], "partenze", formatted_datetime))
        tasks.append((station["code"], station["name"], "arrivi", formatted_datetime))

    # Fetch data in parallel
    stats = {"successful": 0, "failed": 0, "skipped": 0}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                fetch_station_data, code, name, data_type, formatted_datetime
            ): (code, name, data_type)
            for code, name, data_type, formatted_datetime in tasks
        }

        for future in as_completed(futures):
            result = future.result()
            code, name, data_type = futures[future]

            if result["success"]:
                # Skip saving if the data is an empty array
                if result["data"] == []:
                    stats["skipped"] += 1
                    print(f"⚠ Skipped {data_type} for {name} ({code}): empty data")
                    continue

                # Create filename: {STATION_CODE}_{ISO_DATETIME}_{TYPE}.json
                filename = f"{code}_{iso_datetime}_{data_type}.json"
                output_path = (
                    partenze_dir if data_type == "partenze" else arrivi_dir
                ) / filename

                # Save data
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(result["data"], f, indent=2, ensure_ascii=False)

                stats["successful"] += 1
                print(f"✓ Saved {data_type} for {name} ({code}) to {output_path}")
            else:
                stats["failed"] += 1
                print(
                    f"✗ Failed to fetch {data_type} for {name} ({code}): {result['error']}"
                )

    action_type = (
        "all stations" if fetch_all else f"{len(sampled_stations)} sampled stations"
    )
    print(f"\n✅ Completed processing {action_type}:")
    print(f"  • Successful fetches: {stats['successful']}")
    print(f"  • Failed fetches: {stats['failed']}")
    print(f"  • Skipped empty data: {stats['skipped']}")
    print(f"  • Results saved in {partenze_dir} and {arrivi_dir}")


@cli.command("dump-all")
@click.pass_context
def dump_all(ctx):
    """Download all stations from all available endpoints (autocompletaStazione, autocompletaStazioneImpostaViaggio, autocompletaStazioneNTS, cercaStazione, and elencoStazioni)"""
    output_dir = ctx.obj["output"] or "dumps"

    print(f"Starting download from all endpoints to {output_dir}/ directory...")

    print("\n1. Downloading autocompletaStazione data...")
    dump_single_autocompleta_endpoint("autocompletaStazione", output_dir)

    print("\n2. Downloading autocompletaStazioneImpostaViaggio data...")
    dump_single_autocompleta_endpoint("autocompletaStazioneImpostaViaggio", output_dir)

    print("\n3. Downloading autocompletaStazioneNTS data...")
    dump_single_autocompleta_endpoint("autocompletaStazioneNTS", output_dir)

    print("\n4. Downloading cercaStazione data...")
    dump_cerca_stazione_all(output_dir)

    print("\n5. Downloading elencoStazioni data...")
    dump_elenco_stazioni_all(output_dir)

    print(f"\n✅ All endpoints data saved to {output_dir}/ directory")


def save_train_data(result, train_number, endpoint, output_dirs):
    """Save train data to appropriate directory"""
    cerca_numero_dir, autocomplete_dir, andamento_dir, dettaglio_dir = output_dirs

    # Choose output directory and file extension
    dir_map = {
        "cercaNumeroTreno": (cerca_numero_dir, ".json"),
        "cercaNumeroTrenoTrenoAutocomplete": (autocomplete_dir, ".csv"),
        "andamentoTreno": (andamento_dir, ".json"),
        "dettaglioStazione": (dettaglio_dir, ".json"),
    }

    output_dir, ext = dir_map[endpoint]
    output_path = output_dir / f"{train_number}{ext}"

    if ext == ".json":
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result["data"], f, indent=2, ensure_ascii=False)
    else:
        output_path.write_text(result["data"], encoding="utf-8")

    return output_path


def is_train_not_found_error(error_str):
    """Check if error indicates train not found"""
    error_indicators = [
        "404",
        "Not Found",
        "Expecting value: line 1 column 1",
        "No train info available",
        "Missing departure station or time",
    ]
    return any(indicator in error_str for indicator in error_indicators)


def is_empty_data(data):
    """Check if data is empty or null"""
    return (
        data is None
        or (isinstance(data, list) and not data)
        or (isinstance(data, str) and not data.strip())
    )


def process_train_fetch_result(
    result, train_number, endpoint, existing_train_numbers, output_dirs
):
    """Process the result of a train data fetch"""
    if result["success"]:
        # Check if data exists (not empty or null)
        if is_empty_data(result["data"]):
            return {"success": 0, "failed": 0, "skipped": 1}

        # Mark train number as existing
        existing_train_numbers.add(train_number)

        # Save the data
        output_path = save_train_data(result, train_number, endpoint, output_dirs)
        print(f"✓ Saved {endpoint} for train {train_number} to {output_path}")
        return {"success": 1, "failed": 0, "skipped": 0}

    # Handle errors
    if is_train_not_found_error(str(result["error"])):
        return {"success": 0, "failed": 0, "skipped": 1}

    print(f"✗ Failed to fetch {endpoint} for train {train_number}: {result['error']}")
    return {"success": 0, "failed": 1, "skipped": 0}


def setup_train_sampling_directories(output_dir):
    """Setup directories for train sampling"""
    cerca_numero_dir = Path(output_dir) / "cercaNumeroTreno"
    autocomplete_dir = Path(output_dir) / "cercaNumeroTrenoTrenoAutocomplete"
    andamento_dir = Path(output_dir) / "andamentoTreno"
    dettaglio_dir = Path(output_dir) / "dettaglioStazione"

    cerca_numero_dir.mkdir(parents=True, exist_ok=True)
    autocomplete_dir.mkdir(parents=True, exist_ok=True)
    andamento_dir.mkdir(parents=True, exist_ok=True)
    dettaglio_dir.mkdir(parents=True, exist_ok=True)

    return cerca_numero_dir, autocomplete_dir, andamento_dir, dettaglio_dir


def generate_train_sample(samples, fetch_all):
    """Generate train numbers to sample"""
    if fetch_all:
        train_numbers = list(range(1, 100000))
        print("Processing all train numbers from 1 to 99999...")
    else:
        train_numbers = random.sample(range(1, 100000), samples)
        print(f"Sampling {samples} random train numbers from 1 to 99999...")

    return train_numbers


def populate_train_info_cache(train_numbers, output_dirs, existing_train_numbers):
    """Populate cache with train info for efficiency and save cercaNumeroTreno data"""
    train_info_cache = {}
    cerca_numero_dir = output_dirs[0]  # First directory is cercaNumeroTreno
    successful_cerca_calls = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        cerca_futures = {
            executor.submit(
                fetch_train_data, train_number, "cercaNumeroTreno"
            ): train_number
            for train_number in train_numbers
        }

        for future in as_completed(cerca_futures):
            train_number = cerca_futures[future]
            result = future.result()

            if (
                result["success"]
                and isinstance(result["data"], dict)
                and result["data"]
            ):
                train_info_cache[train_number] = result["data"]
                existing_train_numbers.add(train_number)

                # Save cercaNumeroTreno data directly
                output_path = cerca_numero_dir / f"{train_number}.json"
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(result["data"], f, indent=2, ensure_ascii=False)
                print(
                    f"✓ Saved cercaNumeroTreno for train {train_number} to {output_path}"
                )
                successful_cerca_calls += 1

    return train_info_cache, successful_cerca_calls


def manage_train_numbers_file(
    train_numbers_file, new_train_numbers, *, skip_save=False
):
    """Manage the train numbers file with deduplication and appending"""
    if skip_save:
        return

    train_numbers_path = Path(train_numbers_file)
    existing_train_numbers = set()

    # Read existing train numbers if file exists
    if train_numbers_path.exists():
        try:
            content = train_numbers_path.read_text(encoding="utf-8")
            existing_train_numbers = {
                int(line.strip())
                for line in content.splitlines()
                if line.strip().isdigit()
            }
        except (OSError, UnicodeError) as e:
            print(
                f"Warning: Could not read existing train numbers file {train_numbers_file}: {e}"
            )

    # Combine existing and new train numbers (set automatically deduplicates)
    all_train_numbers = existing_train_numbers | new_train_numbers

    # Write back all train numbers in sorted order
    try:
        train_numbers_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(str(num) for num in sorted(all_train_numbers)) + "\n"
        train_numbers_path.write_text(content, encoding="utf-8")

        new_count = len(new_train_numbers - existing_train_numbers)
        if new_count > 0:
            print(f"  • Added {new_count} new train numbers to {train_numbers_file}")
        print(f"  • Total unique train numbers: {len(all_train_numbers)}")
    except (OSError, UnicodeError) as e:
        print(f"Warning: Could not write train numbers file {train_numbers_file}: {e}")


@cli.command("sample-trains")
@click.option(
    "-n",
    "--samples",
    type=int,
    default=50,
    help="Number of random train numbers to sample (default: 50)",
)
@click.option(
    "--all",
    "fetch_all",
    is_flag=True,
    help="Fetch data for all train numbers from 1 to 99999",
)
@click.option(
    "--no-keep-track",
    is_flag=True,
    help="Do not save or update train numbers file",
)
@click.pass_context
def sample_trains(ctx, samples, fetch_all, no_keep_track):
    """Sample random train numbers and fetch their data from cerca-numero-treno, cerca-numero-treno-treno-autocomplete, andamento-treno, and dettaglio-stazione endpoints, or use --all to fetch from all train numbers.

    Results are saved to {output}/cercaNumeroTreno, {output}/cercaNumeroTrenoTrenoAutocomplete, {output}/andamentoTreno, and {output}/dettaglioStazione directories.
    File names follow the format: {TRAIN_NUMBER}.json or {TRAIN_NUMBER}.csv

    Train numbers file:
    - Default: saves to {output}/train_numbers.txt with deduplication and appending
    - --no-keep-track: disable train numbers file completely
    """
    output_dir = ctx.obj["output"] or "dumps"

    # Setup directories
    cerca_numero_dir, autocomplete_dir, andamento_dir, dettaglio_dir = (
        setup_train_sampling_directories(output_dir)
    )
    output_dirs = (cerca_numero_dir, autocomplete_dir, andamento_dir, dettaglio_dir)

    # Generate train numbers to sample
    train_numbers = generate_train_sample(samples, fetch_all)

    # Keep track of existing train numbers and populate cache
    existing_train_numbers = set()
    train_info_cache, successful_cerca_calls = populate_train_info_cache(
        train_numbers, output_dirs, existing_train_numbers
    )

    # Prepare tasks for the remaining three endpoints (cercaNumeroTreno is handled in cache population)
    tasks = []
    for train_number in train_numbers:
        tasks.append((train_number, "cercaNumeroTrenoTrenoAutocomplete"))
        tasks.append((train_number, "andamentoTreno"))
        tasks.append((train_number, "dettaglioStazione"))

    # Fetch data in parallel
    stats = {
        "success": successful_cerca_calls,
        "failed": 0,
        "skipped": 0,
    }  # Start with successful cerca calls

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                fetch_train_data, train_number, endpoint, train_info_cache
            ): (train_number, endpoint)
            for train_number, endpoint in tasks
        }

        for future in as_completed(futures):
            result = future.result()
            train_number, endpoint = futures[future]

            result_stats = process_train_fetch_result(
                result, train_number, endpoint, existing_train_numbers, output_dirs
            )

            # Update overall stats
            for key in stats:
                stats[key] += result_stats[key]

    # Handle train numbers file
    if not no_keep_track:
        # Use output directory for train numbers file
        train_numbers_file = str(Path(output_dir) / "train_numbers.txt")

        # Save train numbers with deduplication and appending
        manage_train_numbers_file(train_numbers_file, existing_train_numbers)
        train_numbers_message = f"  • Train numbers list saved to {train_numbers_file}"
    else:
        train_numbers_message = "  • Train numbers file saving disabled"

    action_type = (
        "all train numbers"
        if fetch_all
        else f"{len(train_numbers)} sampled train numbers"
    )
    print(f"\n✅ Completed processing {action_type}:")
    print(f"  • Successful fetches: {stats['success']}")
    print(f"  • Failed fetches: {stats['failed']}")
    print(f"  • Skipped non-existent trains: {stats['skipped']}")
    print(f"  • Found {len(existing_train_numbers)} existing train numbers")
    print(
        f"  • Results saved in {cerca_numero_dir}, {autocomplete_dir}, {andamento_dir}, and {dettaglio_dir}"
    )
    print(train_numbers_message)


if __name__ == "__main__":
    cli()
