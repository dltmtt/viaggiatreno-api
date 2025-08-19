/**
 * Station listing and search commands
 */

import { api, queue } from "../api.js";
import { REGIONS } from "../config.js";

/**
 * List stations by region or all stations
 *
 * @param {number} region - The region number (0-22) to get stations for
 * @param {boolean} all - If true, fetches stations from all regions
 * @throws {Error} If no region is specified and all is false
 */
export async function elencoStazioni(region, all) {
	if (all) {
		const tasks = Object.keys(REGIONS).map(
			(region) => () => api.get(`elencoStazioni/${region}`).json(),
		);

		const results = await queue.addAll(tasks);
		const stations = results.flat().filter(Boolean);
		console.log(JSON.stringify(stations, null, 2));
		return;
	}

	if (region === 0 || region) {
		const stations = await api.get(`elencoStazioni/${region}`).json();
		console.log(JSON.stringify(stations, null, 2));
		return;
	}

	throw new Error(
		`Specify a region number (0-${Object.keys(REGIONS).length - 1}) or use --all to fetch stations from all regions.`,
	);
}

/**
 * Search stations by name prefix or get all stations alphabetically
 *
 * @param {string} prefix - The station name prefix to search for
 * @param {boolean} all - If true, fetches all stations (A-Z)
 * @throws {Error} If no prefix is provided and all is false, or if no stations are found
 */
export async function cercaStazione(prefix, all) {
	if (all) {
		const alphabet = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
		const tasks = alphabet.map(
			(letter) => () => api.get(`cercaStazione/${letter}`).json(),
		);

		const results = await queue.addAll(tasks);
		const stations = results.flat().filter(Boolean);
		console.log(JSON.stringify(stations, null, 2));
		return;
	}

	if (prefix) {
		const stations = await api.get(`cercaStazione/${prefix}`).json();

		if (!stations || stations.length === 0) {
			throw new Error(`No stations found matching prefix '${prefix}'.`);
		}

		console.log(JSON.stringify(stations, null, 2));
		return;
	}

	throw new Error("Specify a prefix or use --all to fetch all stations.");
}

/**
 * Fetch data from any autocomplete endpoint for all letters A-Z
 *
 * @param {string} endpointName - The API endpoint name to use
 * @returns {Promise<string>} Raw response text from all letters combined
 */
async function fetchAllFromEndpoint(endpointName) {
	const alphabet = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
	const tasks = alphabet.map(
		(letter) => () => api.get(`${endpointName}/${letter}`).text(),
	);

	const results = await queue.addAll(tasks);
	return results
		.filter(Boolean)
		.join("\n")
		.split("\n")
		.filter((line) => line.trim() !== "")
		.join("\n");
}

/**
 * Fetch all station codes from the autocompletaStazione API
 * This function fetches station data for all letters A-Z and parses it into an array
 *
 * @returns {Promise<Array<Array<string>>>} Array of station data [name, code] pairs
 */
export async function fetchAllStationCodes() {
	const stationText = await fetchAllFromEndpoint("autocompletaStazione");

	// Parse the CSV-like format: "STATION_NAME|STATION_CODE"
	const stations = stationText
		.split("\n")
		.map((line) => line.split("|"))
		.filter((parts) => parts.length === 2);

	return stations;
}

/**
 * Autocomplete station search using various API endpoints
 *
 * @param {string} endpointName - The API endpoint name to use for autocomplete
 * @param {string} prefix - The station name prefix to search for
 * @param {boolean} all - If true, fetches all stations (A-Z) using the specified endpoint
 * @throws {Error} If no prefix is provided and all is false, or if no stations are found
 */
export async function autocompleteStation(endpointName, prefix, all) {
	if (all) {
		const stations = await fetchAllFromEndpoint(endpointName);
		console.log(stations);
		return;
	}

	if (prefix) {
		const stations = await api.get(`${endpointName}/${prefix}`).text();

		if (!stations) {
			throw new Error(`No stations found matching prefix '${prefix}'.`);
		}

		console.log(stations);
		return;
	}

	throw new Error("Specify a prefix or use --all to fetch all stations.");
}
