/**
 * Station listing and search commands
 */

import { api, queue } from "../api.js";
import { resolveStationCode } from "../utils.js";
import { REGIONS } from "./regions.js";

/**
 * List stations by region or all stations
 *
 * @param {number} region - The region number (0-22) to get stations for
 * @param {boolean} all - If true, fetches stations from all regions
 */
export async function elencoStazioni(region, all) {
	if (all) {
		const tasks = Object.keys(REGIONS).map(
			(region) => () => api.get(`elencoStazioni/${region}`).json(),
		);

		const results = await queue.addAll(tasks);
		const stations = results.flat().filter(Boolean);
		stations.sort((a, b) => {
			const nameA =
				a.localita?.nomeLungo ||
				a.localita?.label ||
				a.codiceStazione ||
				a.key ||
				"";
			const nameB =
				b.localita?.nomeLungo ||
				b.localita?.label ||
				b.codiceStazione ||
				b.key ||
				"";
			const cmp = nameA.localeCompare(nameB, "it");
			if (cmp !== 0) return cmp;
			const codeA = a.codiceStazione || a.key || "";
			const codeB = b.codiceStazione || b.key || "";
			return codeA.localeCompare(codeB, "it");
		});
		return stations;
	}

	if (region === 0 || region) {
		const stations = await api.get(`elencoStazioni/${region}`).json();
		return stations;
	}
}

/**
 * Search stations by name prefix or get all stations alphabetically
 *
 * @param {string} prefix - The station name prefix to search for
 * @param {boolean} all - If true, fetches all stations (A-Z)
 */
export async function cercaStazione(prefix, all) {
	if (all) {
		const alphabet = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];
		const tasks = alphabet.map(
			(letter) => () => api.get(`cercaStazione/${letter}`).json(),
		);

		const results = await queue.addAll(tasks);
		const stations = results.flat().filter(Boolean);
		stations.sort((a, b) => {
			const nameA = a.nomeLungo || a.label || a.nomeBreve || "";
			const nameB = b.nomeLungo || b.label || b.nomeBreve || "";
			const cmp = nameA.localeCompare(nameB, "it");
			if (cmp !== 0) return cmp;
			const idA = a.id || "";
			const idB = b.id || "";
			return idA.localeCompare(idB, "it");
		});
		return stations;
	}

	if (prefix) {
		const stations = await api.get(`cercaStazione/${prefix}`).json();

		if (!stations || stations.length === 0) {
			console.warn(`No stations found matching prefix '${prefix}'.`);
			return;
		}

		return stations;
	}
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
	const lines = results
		.flatMap((result) => result.split("\n"))
		.filter((line) => line.trim() !== "");

	lines.sort((a, b) => {
		const nameA = a.split("|")[0];
		const nameB = b.split("|")[0];
		const cmp = nameA.localeCompare(nameB, "it");
		if (cmp !== 0) return cmp;
		return a.localeCompare(b, "it");
	});

	return lines.join("\n");
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
 */
export async function autocompleteStation(endpointName, prefix, all) {
	if (all) {
		const stations = await fetchAllFromEndpoint(endpointName);
		return stations;
	}

	if (prefix) {
		const stations = await api.get(`${endpointName}/${prefix}`).text();

		if (!stations) {
			console.warn(`No stations found matching prefix '${prefix}'.`);
			return;
		}

		return stations.trim();
	}
}

/**
 * Get detailed station information including region-specific details
 *
 * @param {string} station - The station name or code to get details for
 * @param {number|string} region - The region code (optional, will be resolved if not provided)
 * @returns {Promise<void>} Logs the detailed station information as JSON
 */
export async function dettaglioStazione(station, region) {
	const stationCode = await resolveStationCode(station);

	// Get region code if not provided
	if (!region && region !== 0) {
		region = await api.get(`regione/${stationCode}`).text();
	}

	if (region === "") {
		console.warn(
			`Region code not available for station ${stationCode}. Calling dettaglioStazione with region -1.`,
		);
		region = -1;
	}

	const res = await api
		.get(`dettaglioStazione/${stationCode}/${region}`)
		.json();
	if (!res) {
		console.warn(
			`No details found for station ${stationCode}. Either the station does not exist or there are no details available.`,
		);
		return;
	}

	return res;
}
