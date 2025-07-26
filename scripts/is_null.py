# /// script
# dependencies = [
#     "rich>=13.0.0",
# ]
# ///

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress
from rich.table import Table

MAX_NON_NULL_EXAMPLES = 20
MAX_VALUE_DISPLAY_LENGTH = 50
EXPECTED_ARGS_COUNT = 3


@dataclass
class PropertyResult:
    """Result of checking a property in a single record."""

    file_path: str
    record_index: int
    property_path: str
    value: Any
    is_null: bool


@dataclass
class FileAnalysis:
    """Analysis results for a single file."""

    file_path: str
    total_records: int
    null_count: int
    non_null_count: int
    non_null_examples: list[PropertyResult]
    error: str = None


def find_nested_property(
    obj: Any, property_name: str, current_path: str = ""
) -> list[tuple[str, Any]]:
    """
    Recursively find all occurrences of a property in a nested object.

    Args:
        obj: The object to search in
        property_name: The property name to find
        current_path: Current path in the object hierarchy

    Returns:
        List of tuples containing (full_path, value) for each occurrence
    """
    results = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{current_path}.{key}" if current_path else key

            if key == property_name:
                results.append((new_path, value))

            # Recursively search in nested objects
            if isinstance(value, (dict, list)):
                results.extend(find_nested_property(value, property_name, new_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{current_path}[{i}]" if current_path else f"[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(find_nested_property(item, property_name, new_path))

    return results


def analyze_single_file(file_path: Path, property_name: str) -> FileAnalysis:
    """
    Analyze a single JSON file to check if a property is null.

    Args:
        file_path: Path to the JSON file to analyze
        property_name: Name of the property to check

    Returns:
        FileAnalysis object with the results
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)

        non_null_examples = []
        null_count = 0
        non_null_count = 0
        total_records = 0

        # Handle both single objects and arrays
        items_to_check = data if isinstance(data, list) else [data]

        for record_index, record in enumerate(items_to_check):
            total_records += 1

            # Find all occurrences of the property in this record
            property_occurrences = find_nested_property(record, property_name)

            if not property_occurrences:
                # Property not found in this record - treat as missing/null
                null_count += 1
            else:
                # Check each occurrence
                record_has_non_null = False
                for prop_path, value in property_occurrences:
                    if value is not None:
                        record_has_non_null = True
                        if len(non_null_examples) < MAX_NON_NULL_EXAMPLES:
                            non_null_examples.append(
                                PropertyResult(
                                    file_path=str(file_path),
                                    record_index=record_index,
                                    property_path=prop_path,
                                    value=value,
                                    is_null=False,
                                )
                            )

                if record_has_non_null:
                    non_null_count += 1
                else:
                    null_count += 1

        return FileAnalysis(
            file_path=str(file_path),
            total_records=total_records,
            null_count=null_count,
            non_null_count=non_null_count,
            non_null_examples=non_null_examples,
        )

    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        return FileAnalysis(
            file_path=str(file_path),
            total_records=0,
            null_count=0,
            non_null_count=0,
            non_null_examples=[],
            error=str(e),
        )


def print_summary(
    console: Console, results: list[FileAnalysis], property_name: str
) -> None:
    """Print analysis summary."""
    total_files = len(results)
    total_records = sum(r.total_records for r in results)
    total_null = sum(r.null_count for r in results)
    total_non_null = sum(r.non_null_count for r in results)
    files_with_errors = [r for r in results if r.error]

    console.print(
        f"[bold blue]Analysis Summary for property '{property_name}'[/bold blue]"
    )
    console.print("=" * 60)
    console.print(f"Files analyzed: {total_files}")
    console.print(f"Total records: {total_records}")
    console.print(f"Records where property is null/missing: {total_null}")
    console.print(f"Records where property is not null: {total_non_null}")
    console.print(f"Files with errors: {len(files_with_errors)}")
    console.print()

    if total_records > 0:
        null_percentage = (total_null / total_records) * 100
        console.print(f"[yellow]Null/missing: {null_percentage:.2f}%[/yellow]")
        if total_non_null > 0:
            non_null_percentage = (total_non_null / total_records) * 100
            console.print(f"[green]Not null: {non_null_percentage:.2f}%[/green]")


def print_errors(console: Console, files_with_errors: list[FileAnalysis]) -> None:
    """Print files with errors."""
    if not files_with_errors:
        return

    console.print("[bold red]Files with errors:[/bold red]")
    for result in files_with_errors:
        console.print(f"  • {Path(result.file_path).name}: {result.error}")
    console.print()


def print_non_null_examples(
    console: Console, files_with_non_null: list[FileAnalysis]
) -> None:
    """Print files with non-null values."""
    if not files_with_non_null:
        return

    console.print("[bold green]Files with non-null values:[/bold green]")

    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Total Records", justify="right")
    table.add_column("Non-null", justify="right", style="green")
    table.add_column("Percentage", justify="right")

    for result in files_with_non_null:
        percentage = (
            (result.non_null_count / result.total_records) * 100
            if result.total_records > 0
            else 0
        )
        table.add_row(
            Path(result.file_path).name,
            str(result.total_records),
            str(result.non_null_count),
            f"{percentage:.1f}%",
        )

    console.print(table)
    console.print()

    # Show sample non-null values
    console.print("[bold green]Sample non-null values:[/bold green]")

    value_table = Table()
    value_table.add_column("File", style="cyan")
    value_table.add_column("Record Index", justify="right", style="magenta")
    value_table.add_column("Property Path", style="blue")
    value_table.add_column("Value", style="green")

    all_examples = []
    for result in files_with_non_null:
        all_examples.extend(result.non_null_examples)

    # Show first MAX_NON_NULL_EXAMPLES examples
    for example in all_examples[:MAX_NON_NULL_EXAMPLES]:
        value_str = str(example.value)
        if len(value_str) > MAX_VALUE_DISPLAY_LENGTH:
            value_str = value_str[:47] + "..."

        value_table.add_row(
            Path(example.file_path).name,
            str(example.record_index),
            example.property_path,
            value_str,
        )

    console.print(value_table)

    if len(all_examples) > MAX_NON_NULL_EXAMPLES:
        remaining = len(all_examples) - MAX_NON_NULL_EXAMPLES
        console.print(f"[dim]... and {remaining} more non-null examples[/dim]")


def print_conclusion(console: Console, total_non_null: int, property_name: str) -> None:
    """Print final conclusion."""
    console.print()
    if total_non_null == 0:
        console.print(
            f"[bold green]✅ CONCLUSION: Property '{property_name}' is NULL (or missing) in ALL records across all files![/bold green]"
        )
    else:
        console.print(
            f"[bold yellow]⚠️  CONCLUSION: Property '{property_name}' is NOT always null![/bold yellow]"
        )
        console.print(
            f"[yellow]Found {total_non_null} records where it has non-null values.[/yellow]"
        )


def main():
    """Main function to analyze all JSON files."""
    if len(sys.argv) != EXPECTED_ARGS_COUNT:
        console = Console()
        console.print(
            "[red]Usage: python script.py <property_name> <directory_path>[/red]"
        )
        console.print(
            "[yellow]Example: python script.py compOrarioPartenzaZero dumps/partenze[/yellow]"
        )
        sys.exit(1)

    property_name = sys.argv[1]
    directory_path = Path(sys.argv[2])

    console = Console()

    if not directory_path.exists():
        console.print(f"[red]Error: Directory {directory_path} does not exist[/red]")
        sys.exit(1)

    if not directory_path.is_dir():
        console.print(f"[red]Error: {directory_path} is not a directory[/red]")
        sys.exit(1)

    # Get all JSON files
    json_files = list(directory_path.glob("*.json"))

    if not json_files:
        console.print(f"[yellow]No JSON files found in {directory_path}[/yellow]")
        sys.exit(0)

    console.print(f"[blue]Found {len(json_files)} JSON files to analyze[/blue]")
    console.print(
        f"[blue]Checking if property '{property_name}' is null in all records[/blue]"
    )
    console.print()

    # Analyze files in parallel
    results: list[FileAnalysis] = []

    with Progress() as progress:
        task = progress.add_task("Analyzing files...", total=len(json_files))

        with ThreadPoolExecutor(max_workers=8) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(
                    analyze_single_file, file_path, property_name
                ): file_path
                for file_path in json_files
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)
                progress.advance(task)

    # Calculate aggregates
    total_non_null = sum(r.non_null_count for r in results)
    files_with_errors = [r for r in results if r.error]
    files_with_non_null = [r for r in results if r.non_null_count > 0]

    # Print all sections
    print_summary(console, results, property_name)
    print_errors(console, files_with_errors)
    print_non_null_examples(console, files_with_non_null)
    print_conclusion(console, total_non_null, property_name)


if __name__ == "__main__":
    main()
