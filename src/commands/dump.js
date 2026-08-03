/**
 * Dump command for comprehensive data collection
 */

import { join } from "node:path";
import { partenzeArriviAll } from "./schedules.js";
import {
	autocompleteStation,
	cercaStazione,
	elencoStazioni,
} from "./stations.js";
import { andamentoTrenoBulk } from "./trains.js";

/**
 * Dynamic dump process that collects comprehensive train and station data
 * This function fetches departures, arrivals, and train status for all stations
 *
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search for train data
 * @param {string} output - Output directory for saving results
 */
export async function dynamicDump(dateTime, output) {
	console.info("Fetching departures for all stations...");
	const departures = await partenzeArriviAll("partenze", dateTime, output);

	console.info("Fetching arrivals for all stations...");
	const arrivals = await partenzeArriviAll("arrivi", dateTime, output);

	// Extract train information
	const trains = new Set();
	for (const train of [...departures, ...arrivals]) {
		if (train.numeroTreno && train.codOrigine && train.dataPartenzaTreno) {
			trains.add(
				`${train.numeroTreno},${train.codOrigine},${train.dataPartenzaTreno}`,
			);
		}
	}

	console.info("Fetching detailed train status for all unique trains...");
	await andamentoTrenoBulk(
		Array.from(trains).map((t) => t.split(",")),
		output,
	);

	console.info("🎉 Dynamic dump completed successfully!");
}

/**
 * Static dump process that collects all station-related static data
 * This function fetches all data for autocompletaStazione, autocompletaStazioneImpostaViaggio,
 * autocompletaStazioneNTS, cercaStazione and elencoStazioni endpoints
 *
 * @param {string} output - Output directory for saving results
 */
export async function staticDump(output) {
	console.info("Starting static dump for all station-related endpoints...");

	// autocompletaStazione with --all (returns CSV text)
	console.info("Fetching autocompletaStazione data...");
	const autocompletaStazioneResult = await autocompleteStation(
		"autocompletaStazione",
		null,
		true,
	);
	Bun.write(
		join(output, "autocompletaStazione.csv"),
		autocompletaStazioneResult,
	);

	// autocompletaStazioneImpostaViaggio with --all (returns CSV text)
	console.info("Fetching autocompletaStazioneImpostaViaggio data...");
	const autocompletaStazioneImpostaViaggioResult = await autocompleteStation(
		"autocompletaStazioneImpostaViaggio",
		null,
		true,
	);
	Bun.write(
		join(output, "autocompletaStazioneImpostaViaggio.csv"),
		autocompletaStazioneImpostaViaggioResult,
	);

	// autocompletaStazioneNTS with --all (returns CSV text)
	console.info("Fetching autocompletaStazioneNTS data...");
	const autocompletaStazioneNTSResult = await autocompleteStation(
		"autocompletaStazioneNTS",
		null,
		true,
	);
	Bun.write(
		join(output, "autocompletaStazioneNTS.csv"),
		autocompletaStazioneNTSResult,
	);

	// cercaStazione with --all (returns JSON)
	console.info("Fetching cercaStazione data...");
	const cercaStazioneResult = await cercaStazione(null, true);
	Bun.write(
		join(output, "cercaStazione.json"),
		JSON.stringify(cercaStazioneResult, null, 2),
	);

	// elencoStazioni with --all (returns JSON)
	console.info("Fetching elencoStazioni data...");
	const elencoStazioniResult = await elencoStazioni(null, true);
	Bun.write(
		join(output, "elencoStazioni.json"),
		JSON.stringify(elencoStazioniResult, null, 2),
	);

	console.info("🎉 Static dump completed successfully!");
}

/**
 * Main dump command that handles both dynamic and static options
 *
 * @param {boolean} isDynamic - If true, performs dynamic dump
 * @param {boolean} isStatic - If true, performs static dump
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search (for dynamic dump)
 * @param {string} output - Output directory for saving results
 */
export async function dump(isDynamic, isStatic, dateTime, output) {
	if (isDynamic) await dynamicDump(dateTime, output);
	if (isStatic) await staticDump(output);
}
