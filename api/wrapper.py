import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import utils
from api.models import (
    Arrival,
    BaseStation,
    Departure,
    Stats,
    TrainInfo,
    TrainProgress,
    TrainStop,
)

description = """
This is a wrapper around the ViaggiaTreno API that provides endpoints to retrieve information about trains and stations.
The ViaggiaTreno API is not officially documented, so the endpoints and their parameters are based on reverse-engineering the [ViaggiaTreno website](http://www.viaggiatreno.it/).
"""
tags_metadata = [
    {
        "name": "stations",
        "description": "Get information about train stations, including departures and arrivals.",
    },
    {
        "name": "trains",
        "description": "Get information about trains, including their progress and stops.",
    },
    {
        "name": "other",
    },
]
__version__ = "0.1.0"

app = FastAPI(
    title="ViaggiaTreno API Wrapper",
    description=description,
    summary="An API wrapper for ViaggiaTreno, the official Trenitalia API.",
    version=__version__,
    contact={
        "name": "Matteo Delton",
        "email": "deltonmatteo@gmail.com",
    },
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

BASE_URI = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"


def get(endpoint: str, *args: str) -> dict | str:
    url = f"{BASE_URI}/{endpoint}/{'/'.join(str(arg) for arg in args)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    return r.json() if "json" in r.headers["Content-Type"] else r.text


@app.get(
    "/stations/search/{query}",
    tags=["stations"],
)
def get_matching_stations(query: str, limit: int = 10) -> list[BaseStation]:
    """Get stations that match a query."""
    stations = utils.load_stations_csv()

    return [
        BaseStation(name=station["long_name"], station_id=station["station_id"])
        for station in stations
        if query.lower() in station["long_name"].lower()
    ][:limit]


@app.get(
    "/stations/{station_id}/departures",
    tags=["stations"],
)
def get_departures(
    station_id: str,
    search_datetime: datetime | None = None,
    limit: int = 10,
) -> list[Departure]:
    """Get the departures from a station at a certain time."""
    if search_datetime is None:
        search_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))

    r = get("partenze", station_id, search_datetime.strftime("%a %b %d %Y %H:%M:%S"))

    return [
        Departure(
            category=d["categoriaDescrizione"].strip(),
            number=int(d["numeroTreno"]),
            origin_station_id=d["codOrigine"],
            destination=d["destinazione"],
            departure_date=utils.to_date(d["dataPartenzaTreno"]),
            departure_time=utils.to_datetime(d["orarioPartenza"]),
            departed_from_origin=not d["nonPartito"],
            scheduled_track=d.get("binarioProgrammatoPartenzaDescrizione"),
            actual_track=d.get("binarioEffettivoPartenzaDescrizione"),
            delay=int(d["ritardo"]),
            warning=d.get("subTitle"),
        )
        for d in r[:limit]
    ]


@app.get(
    "/stations/{station_id}/arrivals",
    tags=["stations"],
)
def get_arrivals(
    station_id: str,
    search_datetime: datetime | None = None,
    limit: int = 10,
) -> list[Arrival]:
    """Get the arrivals to a station at a certain time."""
    if search_datetime is None:
        search_datetime = datetime.now(tz=ZoneInfo("Europe/Rome"))

    r = get("arrivi", station_id, search_datetime.strftime("%a %b %d %Y %H:%M:%S"))

    return [
        Arrival(
            category=a["categoriaDescrizione"].strip(),
            number=int(a["numeroTreno"]),
            origin_station_id=a["codOrigine"],
            origin=a["origine"],
            departure_date=utils.to_date(a["dataPartenzaTreno"]),
            arrival_time=utils.to_datetime(a["orarioArrivo"]),
            departed_from_origin=not a["nonPartito"],
            scheduled_track=a["binarioProgrammatoArrivoDescrizione"],
            actual_track=a["binarioEffettivoArrivoDescrizione"],
            delay=int(a["ritardo"]),
            warning=a["subTitle"],
        )
        for a in r[:limit]
    ]


@app.get("/trains/{train_number}", tags=["trains"])
def get_trains_with_number(train_number: int) -> list[TrainInfo]:
    r = get("cercaNumeroTrenoTrenoAutocomplete", train_number)

    if not r:
        raise HTTPException(
            status_code=204,
            detail="No trains with the given number could be found",
        )

    # Example responses (note the different formats, hence the complex parsing):
    # 35299 - MILANO CENTRALE - 16/11/24|35299-S01700-1731711600000
    # 2033 - TORINO PORTA NUOVA|2033-S00219-1731711600000
    return [
        TrainInfo(
            number=int(train_info.split()[0]),
            departure_date=utils.to_date(int(train_info.split("|")[1].split("-")[2])),
            origin_station_id=train_info.split("|")[1].split("-")[1],
            origin=train_info.split("|")[0].split(" - ")[1],
        )
        for train_info in r.splitlines()
    ]


@app.get("/trains", tags=["trains"])
def get_train_progress(
    origin_station_id: str,
    train_number: int,
    departure_date: date,
) -> TrainProgress:
    """Get the progress of a train, including its stops and delays."""
    departure_date_timestamp: int = int(
        datetime.combine(departure_date, time.min).timestamp() * 1000,
    )
    r = get(
        "andamentoTreno",
        origin_station_id,
        train_number,
        departure_date_timestamp,
    )

    if not r:
        raise HTTPException(
            status_code=204,
            detail="No train with the given number and departure date could be found",
        )

    return TrainProgress(
        last_update_time=utils.to_datetime(r["oraUltimoRilevamento"]),
        last_update_station=r["stazioneUltimoRilevamento"]
        if r["stazioneUltimoRilevamento"] != "--"
        else None,
        category=r["categoria"],
        number=int(r["numeroTreno"]),
        train_number_changes=[
            {"new_train_number": int(c["nuovoNumeroTreno"]), "station": c["stazione"]}
            for c in r["cambiNumero"]
        ],
        departure_date=utils.to_date(r["dataPartenzaTreno"]),
        origin_station_id=r["idOrigine"],
        origin=r["origine"],
        departure_time=utils.to_datetime(r["orarioPartenza"]),
        destination_station_id=r["idDestinazione"],
        destination=r["destinazione"],
        arrival_time=utils.to_datetime(r["orarioArrivo"]),
        delay=int(r["ritardo"] or 0),
        warning=r["subTitle"],
        delay_reason=r["motivoRitardoPrevalente"],
        stops=[
            TrainStop(
                station_id=s["id"],
                name=s["stazione"],
                type=utils.map_stop_type(s["tipoFermata"]),
                scheduled_departure_time=utils.to_datetime(s["partenza_teorica"]),
                actual_departure_time=utils.to_datetime(s["partenzaReale"]),
                departed=utils.to_datetime(s["partenzaReale"]) is not None,
                scheduled_arrival_time=utils.to_datetime(s["arrivo_teorico"]),
                actual_arrival_time=utils.to_datetime(s["arrivoReale"]),
                arrived=utils.to_datetime(s["arrivoReale"]) is not None,
                scheduled_departure_track=s["binarioProgrammatoPartenzaDescrizione"],
                actual_departure_track=s["binarioEffettivoPartenzaDescrizione"],
                scheduled_arrival_track=s["binarioProgrammatoArrivoDescrizione"],
                actual_arrival_track=s["binarioEffettivoArrivoDescrizione"],
            )
            for s in r["fermate"]
        ],
    )


@app.get("/stats", tags=["other"])
def get_stats() -> Stats:
    """Get statistics about today's circulating trains."""
    timestamp = int(datetime.now(tz=ZoneInfo("Europe/Rome")).timestamp() * 1000)
    r = get("statistiche", timestamp)

    return Stats(
        trains_since_midnight=r["treniGiorno"],
        trains_running=r["treniCircolanti"],
        last_update=utils.to_datetime(r["ultimoAggiornamento"]),
    )


def dump_stations() -> None:
    """Dump all stations to a CSV file."""

    file_name = "stations.csv"
    stations = []

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(get, "cercaStazione", letter)
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ]
        for future in as_completed(futures):
            stations.extend(future.result())

    # Sort stations by name before writing
    stations.sort(key=lambda x: utils.normalize(x["nomeLungo"]))

    with Path(file_name).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "station_id",
                "long_name",
                "short_name",
            ],
        )
        for station in stations:
            writer.writerow(
                [
                    station["id"],
                    utils.normalize(station["nomeLungo"]),
                    utils.normalize(station["nomeBreve"]),
                ],
            )

    print(f"Stations have been dumped to {file_name}")
