/**
 * Schedule data commands (arrivals and departures)
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { api, queue } from "../api.js";
import { resolveStationCode } from "../resolvers.js";
import { ProgressBar, parseCSV, saveJsonToFile } from "../utils.js";

/**
 * Get departure schedule data for a station
 *
 * @param {string} station - The station name or code
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search for departures
 * @param {boolean} all - If true, get departures for all stations
 * @param {string} readFrom - File path to read station data from (when using --all)
 * @param {string} output - Output directory for saving results
 */
export function partenze(station, dateTime, all, readFrom, output) {
	return scheduleData("partenze", station, dateTime, all, readFrom, output);
}

/**
 * Get arrival schedule data for a station
 *
 * @param {string} station - The station name or code
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search for arrivals
 * @param {boolean} all - If true, get arrivals for all stations
 * @param {string} readFrom - File path to read station data from (when using --all)
 * @param {string} output - Output directory for saving results
 */
export function arrivi(station, dateTime, all, readFrom, output) {
	return scheduleData("arrivi", station, dateTime, all, readFrom, output);
}

/**
 * Generic function to handle both partenze and arrivi schedule data
 *
 * @param {string} endpoint - The API endpoint to call ('partenze' or 'arrivi')
 * @param {string} station - The station name or code
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search
 * @param {boolean} all - If true, get data for all stations
 * @param {string} readFrom - File path to read station data from (when using --all)
 * @param {string} output - Output directory for saving results
 * @throws {Error} If station is not provided when not using --all
 */
export async function scheduleData(
	endpoint,
	station,
	dateTime,
	all,
	readFrom,
	output,
) {
	if (all) {
		return partenzeArriviAll(endpoint, readFrom, dateTime, output);
	}

	if (!station) {
		throw new Error("STATION argument is required when not using --all.");
	}

	const stationCode = await resolveStationCode(station);
	const rfc7231DateTime = new Date(dateTime.epochMilliseconds).toUTCString();
	const res = await api
		.get(`${endpoint}/${stationCode}/${rfc7231DateTime}`)
		.json();

	if (!res || res.length === 0) {
		console.warn("No results found.");
		return null;
	}

	console.log(JSON.stringify(res, null, 2));
	return res;
}

/**
 * Get departure or arrival data for all stations from a CSV file
 *
 * @param {string} endpoint - The API endpoint to call ('partenze' or 'arrivi')
 * @param {string} readFrom - File path to read station data from
 * @param {Temporal.ZonedDateTime} dateTime - The date and time to search
 * @param {string} output - Output directory for saving results
 */
export async function partenzeArriviAll(endpoint, readFrom, dateTime, output) {
	const outputPath = join(output, endpoint);

	console.info(`Loading station data from ${readFrom}...`);

	const stationData = readFileSync(readFrom, "utf-8");
	const stations = parseCSV(stationData, "|");

	console.info(`Processing all ${stations.length} stations for ${endpoint}...`);

	const rfc7231DateTime = new Date(dateTime.epochMilliseconds).toUTCString();
	const stats = { saved: 0, empty: 0 };
	const allTrains = [];

	const progressBar = new ProgressBar(stations.length);

	const fetchStationData = (station) => async () => {
		const stationCode = station[1];
		const trains = await api
			.get(`${endpoint}/${stationCode}/${rfc7231DateTime}`)
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
