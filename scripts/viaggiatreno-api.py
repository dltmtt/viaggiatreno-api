#!/usr/bin/env python3
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
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)

    try:
        data = fetch_autocompleta_endpoint(endpoint_name)

        # Save to file
        filename = f"{output_dir}/{endpoint_name}.csv"
        with Path(filename).open("w", encoding="utf-8") as f:
            f.write(data)

        print(f"✓ Saved {endpoint_name} data to {filename}")

        # Count lines for feedback
        line_count = len([line for line in data.split("\n") if line.strip()])
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

        # Print or save based on output option
        json_output = json.dumps(all_stations, indent=2, ensure_ascii=False)
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"✓ Saved {len(all_stations)} stations to {output}")
        else:
            print(json_output)
    elif region is not None:
        if not (0 <= region <= MAX_REGION):
            print(f"Error: Region must be between 0 and {MAX_REGION}")
            return

        _, stations = fetch_region(region)
        print(json.dumps(stations, indent=2, ensure_ascii=False))
    else:
        print(f"Error: Specify a region number (0-{MAX_REGION}) or use --all")
        return


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

        # Print or save based on output option
        json_output = json.dumps(all_stations, indent=2, ensure_ascii=False)
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"✓ Saved {len(all_stations)} stations to {output}")
        else:
            print(json_output)
    elif prefix:
        # Single prefix search - print to screen or save to file
        try:
            response = get_json("cercaStazione", prefix)
            json_output = json.dumps(response, indent=2, ensure_ascii=False)
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(json_output)
                print(f"✓ Saved cerca-stazione results to {output}")
            else:
                print(json_output)
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")
        return


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
    output = ctx.obj["output"]
    if download_all:
        data = fetch_autocompleta_endpoint("autocompletaStazione")
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(data)
            line_count = len([line for line in data.split("\n") if line.strip()])
            print(f"✓ Saved {line_count} stations to {output}")
        else:
            print(data)
    elif prefix:
        # Single prefix search - print to screen or save to file
        try:
            response = get_text("autocompletaStazione", prefix)
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(response)
                print(f"✓ Saved autocompleta-stazione results to {output}")
            else:
                print(response)
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")
        return


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
    output = ctx.obj["output"]
    if download_all:
        data = fetch_autocompleta_endpoint("autocompletaStazioneImpostaViaggio")
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(data)
            line_count = len([line for line in data.split("\n") if line.strip()])
            print(f"✓ Saved {line_count} stations to {output}")
        else:
            print(data)
    elif prefix:
        # Single prefix search - print to screen or save to file
        try:
            response = get_text("autocompletaStazioneImpostaViaggio", prefix)
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(response)
                print(
                    f"✓ Saved autocompleta-stazione-imposta-viaggio results to {output}"
                )
            else:
                print(response)
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")
        return


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
    output = ctx.obj["output"]
    if download_all:
        data = fetch_autocompleta_endpoint("autocompletaStazioneNTS")
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(data)
            line_count = len([line for line in data.split("\n") if line.strip()])
            print(f"✓ Saved {line_count} stations to {output}")
        else:
            print(data)
    elif prefix:
        # Single prefix search - print to screen or save to file
        try:
            response = get_text("autocompletaStazioneNTS", prefix)
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(response)
                print(f"✓ Saved autocompleta-stazione-nts results to {output}")
            else:
                print(response)
        except requests.RequestException as e:
            print(f"Error fetching data for prefix '{prefix}': {e}")
    else:
        print("Error: Specify a prefix or use --all")
        return


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
        table_data = "Codice\tRegione\n"
        table_data += "------\t" + "-" * 30 + "\n"
        for code in sorted(REGIONS.keys()):
            table_data += f"{code}\t{REGIONS[code]}\n"

        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(table_data)
            print(f"✓ Saved region table to {output}")
        else:
            print(table_data.strip())
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
                json_output = json.dumps(result, indent=2, ensure_ascii=False)
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(json_output)
                print(f"✓ Saved region info to {output}")
            else:
                print(f"Station: {station_code}")
                print(f"Region: {region_code} ({region_name})")

        except ValueError:
            # Response is not a number, show raw response
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                with Path(output).open("w", encoding="utf-8") as f:
                    f.write(response)
                print(f"✓ Saved raw response to {output}")
            else:
                print(f"Raw response: {response}")

    except requests.RequestException as e:
        print(f"Error fetching region for station {station}: {e}")
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
    output = ctx.obj["output"]
    try:
        # Resolve station code
        station_code = resolve_station_code(station)

        # Format datetime for API
        formatted_datetime = format_datetime_for_api(datetime_str)

        # Make API call
        response = get_json("partenze", station_code, formatted_datetime)

        # Format response as JSON
        json_output = json.dumps(response, indent=2, ensure_ascii=False)

        # Print or save based on output option
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"✓ Saved departures to {output}")
        else:
            print(json_output)

    except requests.RequestException as e:
        print(f"Error fetching departures for station {station}: {e}")
    except ValueError as e:
        print(f"Error parsing datetime: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


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
    output = ctx.obj["output"]
    try:
        # Resolve station code
        station_code = resolve_station_code(station)

        # Format datetime for API
        formatted_datetime = format_datetime_for_api(datetime_str)

        # Make API call
        response = get_json("arrivi", station_code, formatted_datetime)

        # Format response as JSON
        json_output = json.dumps(response, indent=2, ensure_ascii=False)

        # Print or save based on output option
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"✓ Saved arrivals to {output}")
        else:
            print(json_output)

    except requests.RequestException as e:
        print(f"Error fetching arrivals for station {station}: {e}")
    except ValueError as e:
        print(f"Error parsing datetime: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


@cli.command("cerca-numero-treno-treno-autocomplete")
@click.argument("numero_treno", type=int)
@click.pass_context
def cerca_numero_treno_treno_autocomplete(ctx, numero_treno):
    """Get autocomplete suggestions for a train number"""
    output = ctx.obj["output"]
    try:
        # Make API call
        response = get_text("cercaNumeroTrenoTrenoAutocomplete", str(numero_treno))

        # The response should be plain text
        output_text = response

        # Print or save based on output option
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"✓ Saved train number autocomplete results to {output}")
        else:
            print(output_text)

    except requests.RequestException as e:
        print(f"Error fetching autocomplete for train number {numero_treno}: {e}")


@cli.command("cerca-numero-treno")
@click.argument("numero_treno", type=int)
@click.pass_context
def cerca_numero_treno(ctx, numero_treno):
    """Get detailed information for a train number"""
    output = ctx.obj["output"]
    try:
        # Make API call
        response = get_json("cercaNumeroTreno", str(numero_treno))

        # Format the JSON response
        output_text = json.dumps(response, indent=2, ensure_ascii=False)

        # Print or save based on output option
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"✓ Saved train number details to {output}")
        else:
            print(output_text)

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
    output = ctx.obj["output"]
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
                # Resolve user-provided station to code
                departure_station = resolve_station_code(departure_station)

            if not date_str:
                # Use the millisDataPartenza from the API response
                millis = train_info["millisDataPartenza"]
                date_str = train_info["dataPartenza"]
                print(f"Using departure date: {date_str}")
            else:
                # Convert user-provided date to milliseconds
                user_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=ZoneInfo("UTC")
                )
                # Convert to milliseconds (start of day in UTC)
                millis = str(int(user_date.timestamp() * 1000))
        else:
            # Resolve user-provided station to code
            departure_station = resolve_station_code(departure_station)

            # Convert user-provided date to milliseconds
            user_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=ZoneInfo("UTC")
            )
            # Convert to milliseconds (start of day in UTC)
            millis = str(int(user_date.timestamp() * 1000))

        # Make API call to andamentoTreno
        print(
            f"Fetching train status for train {numero_treno} departing from {departure_station} on {date_str}..."
        )
        response = get_json(
            "andamentoTreno", departure_station, str(numero_treno), str(millis)
        )

        # Format response as JSON
        json_output = json.dumps(response, indent=2, ensure_ascii=False)

        # Print or save based on output option
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with Path(output).open("w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"✓ Saved train status to {output}")
        else:
            print(json_output)

    except requests.RequestException as e:
        print(f"Error fetching train status for train {numero_treno}: {e}")
    except ValueError as e:
        print(f"Error parsing date: {e}")
    except KeyError as e:
        print(f"Error: Missing field in train info response: {e}")
    except click.ClickException:
        raise  # Re-raise click exceptions (like station resolution errors)


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
@click.pass_context
def sample_stations(ctx, samples, read_from):
    """Sample random stations and fetch their departures and arrivals.

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

    if len(stations) < samples:
        print(f"Warning: Only {len(stations)} stations available, sampling all of them")
        samples = len(stations)

    # Sample random stations
    sampled_stations = random.sample(stations, samples)
    print(
        f"Sampling {samples} random stations from {len(stations)} available stations..."
    )

    # Prepare tasks for both partenze and arrivi
    tasks = []
    for station in sampled_stations:
        tasks.append((station["code"], station["name"], "partenze", formatted_datetime))
        tasks.append((station["code"], station["name"], "arrivi", formatted_datetime))

    # Fetch data in parallel
    successful_fetches = 0
    failed_fetches = 0
    skipped_empty = 0

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
                    skipped_empty += 1
                    print(f"⚠ Skipped {data_type} for {name} ({code}): empty data")
                    continue

                # Create filename: {STATION_CODE}_{ISO_DATETIME}_{TYPE}.json
                filename = f"{code}_{iso_datetime}_{data_type}.json"

                # Choose output directory
                if data_type == "partenze":
                    output_path = partenze_dir / filename
                else:
                    output_path = arrivi_dir / filename

                # Save data
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(result["data"], f, indent=2, ensure_ascii=False)

                successful_fetches += 1
                print(f"✓ Saved {data_type} for {name} ({code}) to {output_path}")
            else:
                failed_fetches += 1
                print(
                    f"✗ Failed to fetch {data_type} for {name} ({code}): {result['error']}"
                )

    print("\n✅ Completed sampling:")
    print(f"  • Successful fetches: {successful_fetches}")
    print(f"  • Failed fetches: {failed_fetches}")
    print(f"  • Skipped empty data: {skipped_empty}")
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


if __name__ == "__main__":
    cli()
