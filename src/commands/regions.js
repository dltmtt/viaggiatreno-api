/**
 * Region-related commands
 */

import { join } from "node:path";
import { api, queue } from "../api.js";
import { resolveStationCode } from "../utils.js";

export const REGIONS = {
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
	16: "Puglie",
	17: "Calabria",
	18: "Campania",
	19: "Abruzzo",
	20: "Sardegna",
	21: "Provincia autonoma di Trento",
	22: "Provincia autonoma di Bolzano",
};

/**
 * Get region information for a station or display region codes table
 *
 * @param {string} station - The station name or code to get region for
 * @param {boolean} table - If true, displays a table of all region codes
 */
export async function regione(station, table) {
	if (table) {
		console.log("Codice\tRegione");
		console.log("------\t-----------------------------");
		for (const [code, name] of Object.entries(REGIONS)) {
			console.log(`${code.padStart(6)}\t${name}`);
		}
		return;
	}

	const stationCode = await resolveStationCode(station);
	const region = await api.get(`regione/${stationCode}`).json();

	if (!region && region !== 0) {
		console.warn(`Region code not available for station ${stationCode}.`);
		return;
	}

	console.log(
		`Region for station ${stationCode}: ${region} (${REGIONS[region] || "Unknown Region"}).`,
	);
}

/**
 * Get weather data for a region or all regions
 *
 * @param {number} region - The region code (0-22)
 * @param {boolean} all - If true, fetches weather data for all regions
 * @param {Temporal.ZonedDateTime} dateTime - Date and time for timestamping output files
 * @param {string} output - Output directory for saving results when all is true
 * @returns {Promise<object>} Weather data object by station code
 */
export async function datimeteo(region, all, dateTime, output) {
	if (all) {
		return datimeteoAll(dateTime, output);
	}

	if (region === 0 || region) {
		const res = await api.get(`datimeteo/${region}`).json();
		return res;
	}
}

/**
 * Fetch weather data for all regions and save to output directory
 *
 * @param {Temporal.ZonedDateTime} dateTime - Date and time for timestamping output files
 * @param {string} output - Output directory for saving results
 * @returns {Promise<object>} Combined weather data for all regions
 */
export async function datimeteoAll(
	dateTime = Temporal.Now.zonedDateTimeISO("Europe/Rome"),
	output = process.cwd(),
) {
	const outputPath = join(output, "datimeteo");

	console.info("Fetching weather data for all regions...");

	const humanReadableDateTime = dateTime.toString({
		smallestUnit: "second",
		timeZoneName: "never",
		offset: "never",
	});

	const allWeatherData = {};

	const tasks = Object.keys(REGIONS).map((regionCode) => async () => {
		const res = await api.get(`datimeteo/${regionCode}`).json();
		if (res && Object.keys(res).length > 0) {
			const filename = `${regionCode}_${humanReadableDateTime}_datimeteo.json`;
			Bun.write(join(outputPath, filename), JSON.stringify(res, null, 2));
			Object.assign(allWeatherData, res);
		}
		return res;
	});

	await queue.addAll(tasks);

	console.info(`✅ Weather data saved to ${outputPath}.`);
	return allWeatherData;
}
