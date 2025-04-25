__version__ = "0.2.0"

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import click
import inquirer
from prettytable import PrettyTable

from api import wrapper as api
from api.models import StopType, TrainProgress, TrainStop

if TYPE_CHECKING:
    from api.models import Arrival, BaseStation, Departure, TrainInfo

logger = logging.getLogger(__name__)


class Train:
    """A train is identified by the triple (number, origin_station_id, departure_date)."""

    def __init__(
        self,
        number: int,
        origin_station_id: str,
        departure_date: date,
        detailed_info: TrainProgress,
    ) -> None:
        self.number: int = number
        self.origin_station_id: str = origin_station_id
        self.departure_date: date = departure_date

        self.last_update_station: str | None = detailed_info.last_update_station
        self.last_update_time: datetime | None = detailed_info.last_update_time

        self.category: str = detailed_info.category
        self.number_changes: list[dict[str, int | str]] = (
            detailed_info.train_number_changes
        )

        self.stops: list[Station] = [
            Station(
                s.station_id,
                s.name,
                detailed_info.stops,
                self,
            )
            for s in detailed_info.stops
        ]
        self.origin: Station = self.stops[0]
        self.destination: Station = self.stops[-1]
        self.departure_time: datetime = detailed_info.departure_time
        self.arrival_time: datetime = detailed_info.arrival_time
        self.delay: int = detailed_info.delay

    @classmethod
    def create(
        cls,
        number: int,
        origin_station_id: str,
        departure_date: date,
    ) -> "Train | None":
        try:
            detailed_info = api.get_train_progress(
                origin_station_id,
                number,
                departure_date,
            )
        except api.HTTPException:
            logger.exception("Error while fetching train progress")
            return None

        return cls(number, origin_station_id, departure_date, detailed_info)

    def __str__(self) -> str:
        numbers = str(self.number)
        if self.number_changes:
            numbers += "/"
            numbers += "/".join(str(c["new_train_number"]) for c in self.number_changes)

        if self.category:
            return f"{self.category} {numbers}"
        return f"{numbers}"

    def __repr__(self) -> str:
        return f"Train({self.number}, {self.origin_station_id}, {self.departure_date})"

    def get_formatted_delay(self) -> str:
        if self.origin.departed:
            if self.delay > 0:
                return click.style(f"+{self.delay}", fg="red")
            if self.delay < 0:
                return click.style(str(self.delay), fg="green")
            return "In orario"

        if self.origin.actual_departure_track is not None:
            return "Pronto"

        return "Non partito"

    def show_progress(self) -> None:
        click.echo(f"Treno {self} · {self.get_formatted_delay()}")
        click.echo(f"{self.departure_time.strftime('%H:%M')} {self.origin.name}")
        click.echo(f"{self.arrival_time.strftime('%H:%M')} {self.destination.name}")

        if self.last_update_station is not None and self.last_update_time is not None:
            last_update_time = self.last_update_time.strftime("%H:%M")
            click.secho(
                f"Ultimo aggiornamento alle {last_update_time} a {self.last_update_station}",
                dim=True,
            )

            trip_duration = (self.arrival_time - self.departure_time).total_seconds()
            last_arrival_time = next(
                (
                    stop.actual_arrival_time
                    for stop in reversed(self.stops)
                    if stop.actual_arrival_time
                ),
                self.departure_time,
            )
            elapsed_time = (last_arrival_time - self.departure_time).total_seconds()
            progress_percentage = (elapsed_time / trip_duration) * 100

            with click.progressbar(
                label="Progresso",
                length=100,
                show_percent=True,
                fill_char="█",
                empty_char="░",
                width=40,
            ) as bar:
                bar.update(progress_percentage)

        else:
            click.secho("Nessun aggiornamento disponibile.", dim=True)

        for stop in self.stops:
            track = stop.get_formatted_track()

            if track:
                click.echo(f"\n{stop.name} · {track}")
            else:
                click.echo(f"\n{stop.name}")

            if stop.type == StopType.CANCELLED:
                click.echo("Fermata cancellata.")
                continue

            if stop.type in (StopType.ARRIVAL, StopType.INTERMEDIATE):
                click.echo(
                    f"Arr.:\t{stop.scheduled_arrival_time.strftime('%H:%M')}"
                    f"\t{stop.get_formatted_time(self.delay, check_departures=False)}",
                )
            if stop.type in (StopType.DEPARTURE, StopType.INTERMEDIATE):
                click.echo(
                    f"Dep.:\t{stop.scheduled_departure_time.strftime('%H:%M')}"
                    f"\t{stop.get_formatted_time(self.delay, check_departures=True)}",
                )


class Station:
    """Represents a station, possibly intended as a stop for a specific train."""

    def __init__(
        self,
        station_id: str,
        name: str,
        stops: list[TrainStop] | None = None,
        train: Train | None = None,
    ) -> None:
        self.station_id: str = station_id
        self.name: str = name

        if stops is None or train is None:
            return

        self.train = train

        stop = next((s for s in stops if s.station_id == self.station_id), None)
        if stop is None:
            return

        self.actual_departure_track: str | None = stop.actual_departure_track
        self.scheduled_departure_track: str | None = stop.scheduled_departure_track
        self.actual_arrival_track: str | None = stop.actual_arrival_track
        self.scheduled_arrival_track: str | None = stop.scheduled_arrival_track
        self.arrived: bool = stop.arrived
        self.departed: bool = stop.departed
        self.type: str = stop.type
        self.actual_departure_time: datetime | None = stop.actual_departure_time
        self.scheduled_departure_time: datetime | None = stop.scheduled_departure_time
        self.actual_arrival_time: datetime | None = stop.actual_arrival_time
        self.scheduled_arrival_time: datetime | None = stop.scheduled_arrival_time

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Station({self.station_id}, {self.name})"

    def show_timetable(
        self,
        timetable_datetime: datetime | None = None,
        limit: int = 10,
        *,
        is_departure: bool = True,
    ) -> None:
        if timetable_datetime is None:
            timetable_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))
        click.secho(
            f"{'Partenze da' if is_departure else 'Arrivi a'} {self.name}",
            bold=True,
        )

        table = PrettyTable()

        if is_departure:
            trains: list[Departure] = api.get_departures(
                self.station_id,
                timetable_datetime,
                limit,
            )
            if not trains:
                click.echo("Nessun treno in partenza nei prossimi 90 minuti.")
                return
            table.field_names = [
                "Treno",
                "Destinazione",
                "Partenza",
                "Ritardo",
                "Binario",
            ]
        else:
            trains: list[Arrival] = api.get_arrivals(
                self.station_id,
                timetable_datetime,
                limit,
            )
            if not trains:
                click.echo("Nessun treno in arrivo nei prossimi 90 minuti.")
                return
            table.field_names = ["Treno", "Origine", "Arrivo", "Ritardo", "Binario"]

        with ThreadPoolExecutor(max_workers=len(trains)) as executor:
            futures = [
                executor.submit(
                    self.process_train,
                    Train.create(
                        train.number,
                        train.origin_station_id,
                        train.departure_date,
                    ),
                    check_departures=is_departure,
                )
                for train in trains
            ]

            for future in futures:
                row = future.result()
                table.add_row(row)

        click.echo(table)

    def process_train(self, train: Train, *, check_departures: bool) -> list:
        station = next(
            (s for s in train.stops if s.station_id == self.station_id),
            None,
        )

        if station is None:
            msg = "Non-real-time updates not implemented yet"
            raise NotImplementedError(msg)

        if check_departures:
            station_name = train.destination.name
            scheduled_time = station.scheduled_departure_time.strftime("%H:%M")
        else:
            station_name = train.origin.name
            scheduled_time = station.scheduled_arrival_time.strftime("%H:%M")

        return [
            train,
            station_name,
            scheduled_time,
            train.get_formatted_delay(),
            station.get_formatted_track() or "N/A",
        ]

    def get_formatted_track(self) -> str:
        track = self.actual_departure_track or self.actual_arrival_track
        scheduled_track = self.scheduled_departure_track or self.scheduled_arrival_track

        if track:
            if track == scheduled_track:
                track = click.style(track, fg="blue")
            elif scheduled_track:
                track = click.style(track, fg="magenta")
            else:
                track = click.style(track, fg="cyan")
        else:
            track = scheduled_track

        if (self.arrived or self.train.origin.actual_departure_time) and (
            self.departed or self.train.destination.actual_arrival_time
        ):
            track = click.style(track, dim=True)
        elif self.arrived and not self.departed:
            track = click.style(track, bold=True)

        return track

    def get_formatted_time(
        self,
        delay: int,
        *,
        check_departures: bool,
    ) -> str | None:
        actual_time = (
            self.actual_departure_time if check_departures else self.actual_arrival_time
        )
        scheduled_time = (
            self.scheduled_departure_time
            if check_departures
            else self.scheduled_arrival_time
        )

        if actual_time:
            if actual_time > scheduled_time + timedelta(seconds=30):
                formatted_time = click.style(actual_time.strftime("%H:%M"), fg="red")
            else:
                formatted_time = click.style(actual_time.strftime("%H:%M"), fg="green")
        elif delay > 0:
            formatted_time = click.style(
                (scheduled_time + timedelta(minutes=delay)).strftime("%H:%M"),
                fg="yellow",
            )
        else:
            formatted_time = scheduled_time.strftime("%H:%M")

        return formatted_time


def show_stats() -> None:
    stats = api.get_stats()
    click.secho(f"Treni in circolazione da mezzanotte: {stats.trains_since_midnight}")
    click.secho(f"Treni in circolazione ora: {stats.trains_running}")
    click.secho(f"Ultimo aggiornamento: {stats.last_update.strftime('%T')}", dim=True)


def choose_station(query: str) -> Station | None:
    try:
        stations: list[BaseStation] = api.get_matching_stations(query)
    except api.HTTPException:
        logger.exception("Error while fetching stations")
        return None

    if len(stations) == 1:
        return Station(stations[0].station_id, stations[0].name)

    chosen_station = inquirer.list_input(
        message="Seleziona la stazione",
        choices=[(s.name, s) for s in stations],
    )

    return Station(chosen_station.station_id, chosen_station.name)


def choose_train(train_number: int) -> Train | None:
    try:
        train_info: list[TrainInfo] = api.get_trains_with_number(train_number)
    except api.HTTPException:
        logger.exception("Error while fetching train info")
        return None

    if len(train_info) == 1:
        return Train.create(
            train_info[0].number,
            train_info[0].origin_station_id,
            train_info[0].departure_date,
        )

    chosen_train = inquirer.list_input(
        message="Seleziona il treno",
        choices=[(f"{t.origin} - {t.departure_date}", t) for t in train_info],
    )

    return Train.create(
        chosen_train.number,
        chosen_train.origin_station_id,
        chosen_train.departure_date,
    )


@click.command(
    help="Access real-time train schedules, delays, stops, tracks, and more with ease!",
    epilog=(
        "Departures and arrivals show trains from/to the selected station "
        "in a range from 15 minutes before to 90 minutes after the selected time."
    ),
)
@click.help_option("-h", "--help")
@click.version_option(version=__version__)
@click.option(
    "-d",
    "--departures",
    help="Show departures from STATION",
    type=click.STRING,
    metavar="STATION",
)
@click.option(
    "-a",
    "--arrivals",
    help="Show arrivals to STATION",
    type=click.STRING,
    metavar="STATION",
)
@click.option(
    "-n",
    "--number",
    help="Show information about train TRAIN_NUMBER",
    type=click.INT,
    metavar="TRAIN_NUMBER",
)
@click.option(
    "-l",
    "--limit",
    help="Limit the number of results",
    type=click.INT,
    default=10,
    show_default=True,
    metavar="N",
)
@click.option(
    "--date",
    help="Date to use for the search",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=datetime.now(tz=ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d"),
    show_default="today",
)
@click.option(
    "--time",
    help="Time to use for the search",
    type=click.DateTime(formats=["%H", "%H:%M"]),
    default=datetime.now(tz=ZoneInfo("Europe/Rome")).strftime("%H:%M"),
    show_default="now",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Show statistics about trains",
)
@click.option(
    "--log-level",
    help="Set the logging level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        case_sensitive=False,
    ),
    default="INFO",
    show_default=True,
)
def main(  # noqa: PLR0913
    departures: str,
    arrivals: str,
    number: int,
    limit: int,
    date: str,
    time: str,
    log_level: str,
    *,
    stats: bool,
) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper()))

    if stats:
        show_stats()

    search_datetime: datetime = datetime.combine(date.date(), time.time())

    if departures:
        if (queried_station := choose_station(departures)) is None:
            sys.exit(1)
        queried_station.show_timetable(search_datetime, limit, is_departure=True)

    if arrivals:
        if (queried_station := choose_station(arrivals)) is None:
            sys.exit(1)
        queried_station.show_timetable(search_datetime, limit, is_departure=False)

    if number:
        if (queried_train := choose_train(number)) is None:
            sys.exit(1)
        queried_train.show_progress()
