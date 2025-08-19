/**
 * Dump command for comprehensive data collection
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { api, queue } from "../api.js";
import {
	ProgressBar,
	parseCSV,
	saveJsonToFile,
	saveTextToFile,
} from "../utils.js";
import { andamentoTrenoBulk } from "./journey.js";
import {
	autocompleteStation,
	cercaStazione,
	elencoStazioni,
} from "./stations.js";

/**
 * Internal function to fetch departure or arrival data for all stations
 * This is used by the dynamic dump process
 *
 * @param {string} endpoint - The API endpoint to call ('partenze' or 'arrivi')
 * @param {string} readFrom - File path to read station data from
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search
 * @param {string} output - Output directory for saving results
 * @returns {Promise<Array>} Array of all train data collected
 */
async function partenzeArriviAll(endpoint, readFrom, dateTime, output) {
	const outputPath = join(output, endpoint);

	console.info(`Loading station data from ${readFrom}...`);

	const stationData = readFileSync(readFrom, "utf-8");
	const stations = parseCSV(stationData, "|");

	console.info(`Processing all ${stations.length} stations for ${endpoint}...`);

	const formattedDateTime = new Date(dateTime.epochMilliseconds).toUTCString();
	const stats = { saved: 0, empty: 0 };
	const allTrains = [];

	const progressBar = new ProgressBar(stations.length);

	const fetchStationData = (station) => async () => {
		const stationCode = station[1];
		const trains = await api
			.get(`${endpoint}/${stationCode}/${formattedDateTime}`)
			.json();
		progressBar.update();

		if (!trains || trains.length === 0) {
			stats.empty++;
			return [];
		}

		// This is implicitly in Rome timezone
		const humanReadableDateTime = dateTime.toString({
			smallestUnit: "second",
			timeZoneName: "never",
			offset: "never",
		});
		const filename = `${stationCode}_${humanReadableDateTime}_${endpoint}.json`;
		const filePath = join(outputPath, filename);

		saveJsonToFile(trains, filePath);
		allTrains.push(...trains);
		stats.saved++;

		return trains;
	};

	const tasks = stations.map(fetchStationData);
	await queue.addAll(tasks);

	console.info(`\n✅ Completed processing all stations for ${endpoint}:`);
	console.info(`    - ${stats.saved} results saved.`);
	console.info(`    - ${stats.empty} empty results not saved.`);
	console.info(`Results saved in ${outputPath}.`);

	return allTrains;
}

/**
 * Dynamic dump process that collects comprehensive train and station data
 * This function fetches departures, arrivals, and train status for all stations
 *
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search for train data
 * @param {string} readFrom - File path to read station data from
 * @param {string} output - Output directory for saving results
 */
export async function dynamicDump(dateTime, readFrom, output) {
	console.info("Fetching departures for all stations...");
	const departures = await partenzeArriviAll(
		"partenze",
		readFrom,
		dateTime,
		output,
	);

	console.info("Fetching arrivals for all stations...");
	const arrivals = await partenzeArriviAll(
		"arrivi",
		readFrom,
		dateTime,
		output,
	);

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

	// Store original console.log to capture output
	const originalConsoleLog = console.log;
	let capturedOutput = "";

	// Capture console output for each endpoint
	const captureOutput = () => {
		capturedOutput = "";
		console.log = (message) => {
			capturedOutput = message;
		};
	};

	try {
		// autocompletaStazione with --all (returns CSV text)
		console.info("Fetching autocompletaStazione data...");
		captureOutput();
		await autocompleteStation("autocompletaStazione", null, true);
		saveTextToFile(
			capturedOutput.trim(),
			join(output, "autocompletaStazione.csv"),
		);

		// autocompletaStazioneImpostaViaggio with --all (returns CSV text)
		console.info("Fetching autocompletaStazioneImpostaViaggio data...");
		captureOutput();
		await autocompleteStation("autocompletaStazioneImpostaViaggio", null, true);
		saveTextToFile(
			capturedOutput.trim(),
			join(output, "autocompletaStazioneImpostaViaggio.csv"),
		);

		// autocompletaStazioneNTS with --all (returns CSV text)
		console.info("Fetching autocompletaStazioneNTS data...");
		captureOutput();
		await autocompleteStation("autocompletaStazioneNTS", null, true);
		saveTextToFile(
			capturedOutput.trim(),
			join(output, "autocompletaStazioneNTS.csv"),
		);

		// cercaStazione with --all (returns JSON)
		console.info("Fetching cercaStazione data...");
		captureOutput();
		await cercaStazione(null, true);
		saveJsonToFile(
			JSON.parse(capturedOutput),
			join(output, "cercaStazione.json"),
		);

		// elencoStazioni with --all (returns JSON)
		console.info("Fetching elencoStazioni data...");
		captureOutput();
		await elencoStazioni(null, true);
		saveJsonToFile(
			JSON.parse(capturedOutput),
			join(output, "elencoStazioni.json"),
		);
	} finally {
		// Restore original console.log
		console.log = originalConsoleLog;
	}

	console.info("🎉 Static dump completed successfully!");
}

/**
 * Main dump command that handles both dynamic and static options
 *
 * @param {boolean} isDynamic - If true, performs dynamic dump
 * @param {boolean} isStatic - If true, performs static dump
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search (for dynamic dump)
 * @param {string} readFrom - File path to read station data from (for dynamic dump)
 * @param {string} output - Output directory for saving results
 */
export async function dump(isDynamic, isStatic, dateTime, readFrom, output) {
	if (!isDynamic && !isStatic) {
		throw new Error("Either --dynamic or --static option must be specified");
	}

	if (isDynamic) await dynamicDump(dateTime, readFrom, output);
	if (isStatic) await staticDump(output);
}
