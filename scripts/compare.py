# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "rich>=13.0.0",
# ]
# ///

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress
from rich.table import Table

MAX_DIFFERENCES_TO_SHOW = 20


@dataclass
class ComparisonResult:
    """Result of comparing two fields in a single record."""

    file_path: str
    record_id: str
    field1_value: Any
    field2_value: Any
    are_equal: bool
    field1_found: bool
    field2_found: bool


@dataclass
class FileAnalysis:
    """Analysis results for a single file."""

    file_path: str
    total_records: int
    equal_count: int
    different_count: int
    missing_fields_count: int
    differences: list[ComparisonResult]
    error: str = None


def find_field_in_nested_dict(data: dict, field_name: str) -> tuple[Any, bool]:
    """
    Recursively find a field in a nested dictionary.

    Args:
        data: The dictionary to search in
        field_name: The field name to find

    Returns:
        Tuple of (value, found) where found is True if the field was found
    """
    if field_name in data:
        return data[field_name], True

    for value in data.values():
        if isinstance(value, dict):
            result, found = find_field_in_nested_dict(value, field_name)
            if found:
                return result, True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result, found = find_field_in_nested_dict(item, field_name)
                    if found:
                        return result, True

    return None, False


def get_record_identifier(record: dict) -> str:
    """
    Get a reasonable identifier for a record.
    Tries common ID fields, falls back to a hash of the record.
    """
    id_fields = [
        "id",
        "compNumeroTreno",
        "numeroTreno",
        "codOrigine",
        "codDestinazione",
    ]

    for field in id_fields:
        value, found = find_field_in_nested_dict(record, field)
        if found and value is not None:
            return str(value)

    # Fallback to hash of the record (first 8 chars)
    return str(hash(str(record)))[:8]


def analyze_single_file(file_path: Path, field1: str, field2: str) -> FileAnalysis:
    """
    Analyze a single JSON file to compare two specified fields.

    Args:
        file_path: Path to the JSON file to analyze
        field1: Name of the first field to compare
        field2: Name of the second field to compare

    Returns:
        FileAnalysis object with the results
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)

        # Handle both single objects and arrays
        records = data if isinstance(data, list) else [data]

        if not records:
            return FileAnalysis(
                file_path=str(file_path),
                total_records=0,
                equal_count=0,
                different_count=0,
                missing_fields_count=0,
                differences=[],
                error="File contains no records",
            )

        differences = []
        equal_count = 0
        different_count = 0
        missing_fields_count = 0

        for record in records:
            if not isinstance(record, dict):
                continue

            value1, found1 = find_field_in_nested_dict(record, field1)
            value2, found2 = find_field_in_nested_dict(record, field2)
            record_id = get_record_identifier(record)

            # Skip if either field is missing
            if not found1 or not found2:
                missing_fields_count += 1
                continue

            are_equal = value1 == value2

            comparison_result = ComparisonResult(
                file_path=str(file_path),
                record_id=record_id,
                field1_value=value1,
                field2_value=value2,
                are_equal=are_equal,
                field1_found=found1,
                field2_found=found2,
            )

            if are_equal:
                equal_count += 1
            else:
                different_count += 1
                differences.append(comparison_result)

        return FileAnalysis(
            file_path=str(file_path),
            total_records=len(records),
            equal_count=equal_count,
            different_count=different_count,
            missing_fields_count=missing_fields_count,
            differences=differences,
        )

    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        return FileAnalysis(
            file_path=str(file_path),
            total_records=0,
            equal_count=0,
            different_count=0,
            missing_fields_count=0,
            differences=[],
            error=str(e),
        )


def print_summary(
    console: Console, results: list[FileAnalysis], field1: str, field2: str
) -> None:
    """Print analysis summary."""
    total_files = len(results)
    total_records = sum(r.total_records for r in results)
    total_equal = sum(r.equal_count for r in results)
    total_different = sum(r.different_count for r in results)
    total_missing = sum(r.missing_fields_count for r in results)
    files_with_errors = [r for r in results if r.error]

    console.print(f"[bold blue]Analysis Summary: {field1} vs {field2}[/bold blue]")
    console.print("=" * 60)
    console.print(f"Files analyzed: {total_files}")
    console.print(f"Total records: {total_records}")
    console.print(f"Records with equal values: {total_equal}")
    console.print(f"Records with different values: {total_different}")
    console.print(f"Records with missing fields: {total_missing}")
    console.print(f"Files with errors: {len(files_with_errors)}")
    console.print()

    comparable_records = total_equal + total_different
    if comparable_records > 0:
        equal_percentage = (total_equal / comparable_records) * 100
        console.print(f"[green]Equal values: {equal_percentage:.2f}%[/green]")
        if total_different > 0:
            different_percentage = (total_different / comparable_records) * 100
            console.print(f"[red]Different values: {different_percentage:.2f}%[/red]")


def print_errors(console: Console, files_with_errors: list[FileAnalysis]) -> None:
    """Print files with errors."""
    if not files_with_errors:
        return

    console.print("[bold red]Files with errors:[/bold red]")
    for result in files_with_errors:
        console.print(f"  • {Path(result.file_path).name}: {result.error}")
    console.print()


def print_differences(
    console: Console,
    files_with_differences: list[FileAnalysis],
    field1: str,
    field2: str,
) -> None:
    """Print files with differences."""
    if not files_with_differences:
        return

    console.print("[bold yellow]Files with differences:[/bold yellow]")

    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Total Records", justify="right")
    table.add_column("Different", justify="right", style="red")
    table.add_column("Missing Fields", justify="right", style="yellow")
    table.add_column("Percentage", justify="right")

    for result in files_with_differences:
        comparable_records = result.equal_count + result.different_count
        percentage = (
            (result.different_count / comparable_records) * 100
            if comparable_records > 0
            else 0
        )
        table.add_row(
            Path(result.file_path).name,
            str(result.total_records),
            str(result.different_count),
            str(result.missing_fields_count),
            f"{percentage:.1f}%",
        )

    console.print(table)
    console.print()

    # Show detailed differences
    console.print("[bold yellow]Sample differences:[/bold yellow]")

    diff_table = Table()
    diff_table.add_column("File", style="cyan")
    diff_table.add_column("Record ID", style="magenta")
    diff_table.add_column(field1, style="green")
    diff_table.add_column(field2, style="red")

    all_differences = []
    for result in files_with_differences:
        all_differences.extend(result.differences)

    # Show first MAX_DIFFERENCES_TO_SHOW differences
    for diff in all_differences[:MAX_DIFFERENCES_TO_SHOW]:
        diff_table.add_row(
            Path(diff.file_path).name,
            diff.record_id,
            str(diff.field1_value),
            str(diff.field2_value),
        )

    console.print(diff_table)

    if len(all_differences) > MAX_DIFFERENCES_TO_SHOW:
        remaining = len(all_differences) - MAX_DIFFERENCES_TO_SHOW
        console.print(f"[dim]... and {remaining} more differences[/dim]")


def print_conclusion(
    console: Console,
    total_different: int,
    files_with_differences: list[FileAnalysis],
    field1: str,
    field2: str,
) -> None:
    """Print final conclusion."""
    console.print()
    if total_different == 0:
        console.print(
            f"[bold green]✅ CONCLUSION: {field1} and {field2} are ALWAYS equal in all files![/bold green]"
        )
    else:
        console.print(
            f"[bold red]❌ CONCLUSION: {field1} and {field2} are NOT always equal![/bold red]"
        )
        console.print(
            f"[red]Found {total_different} cases where they differ across {len(files_with_differences)} files.[/red]"
        )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare two fields in JSON files recursively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s field1 field2                           # Compare in dumps/partenze/
  %(prog)s field1 field2 --dir dumps/arrivi       # Compare in specific directory
  %(prog)s compOrarioPartenzaZero compOrarioPartenza --pattern "*.json"
        """,
    )

    parser.add_argument("field1", help="Name of the first field to compare")
    parser.add_argument("field2", help="Name of the second field to compare")
    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory containing JSON files (default: dumps/partenze/)",
    )
    parser.add_argument(
        "--pattern", default="*.json", help="File pattern to match (default: *.json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Maximum number of worker threads (default: 8)",
    )

    return parser.parse_args()


def main():
    """Main function to analyze JSON files and compare specified fields."""
    args = parse_arguments()
    console = Console()

    # Determine directory to analyze
    if args.dir:
        target_dir = args.dir
    else:
        script_dir = Path(__file__).parent
        target_dir = script_dir.parent / "dumps" / "partenze"

    if not target_dir.exists():
        console.print(f"[red]Error: Directory {target_dir} does not exist[/red]")
        sys.exit(1)

    # Get JSON files matching the pattern
    json_files = list(target_dir.glob(args.pattern))

    if not json_files:
        console.print(
            f"[yellow]No files matching '{args.pattern}' found in {target_dir}[/yellow]"
        )
        sys.exit(0)

    console.print(f"[blue]Found {len(json_files)} JSON files to analyze[/blue]")
    console.print(f"[blue]Comparing {args.field1} vs {args.field2}[/blue]")
    console.print(f"[blue]Directory: {target_dir}[/blue]")
    console.print()

    # Analyze files in parallel
    results: list[FileAnalysis] = []

    with Progress() as progress:
        task = progress.add_task("Analyzing files...", total=len(json_files))

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(
                    analyze_single_file, file_path, args.field1, args.field2
                ): file_path
                for file_path in json_files
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)
                progress.advance(task)

    # Calculate aggregates
    total_different = sum(r.different_count for r in results)
    files_with_errors = [r for r in results if r.error]
    files_with_differences = [r for r in results if r.different_count > 0]

    # Print all sections
    print_summary(console, results, args.field1, args.field2)
    print_errors(console, files_with_errors)
    print_differences(console, files_with_differences, args.field1, args.field2)
    print_conclusion(
        console, total_different, files_with_differences, args.field1, args.field2
    )


if __name__ == "__main__":
    main()
