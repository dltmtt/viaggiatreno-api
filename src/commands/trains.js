/**
 * Train search and status commands
 */

import { api } from "../api.js";

/**
 * Search for train numbers using autocomplete functionality
 *
 * @param {string|number} trainNumber - The train number to search for
 */
export async function cercaNumeroTrenoTrenoAutocomplete(trainNumber) {
	const res = await api
		.get(`cercaNumeroTrenoTrenoAutocomplete/${trainNumber}`)
		.text();
	if (!res) {
		console.warn(`No results found for train number ${trainNumber}.`);
		return;
	}

	console.log(res.trim());
}

/**
 * Search for detailed train information by train number
 *
 * @param {string|number} trainNumber - The train number to search for
 */
export async function cercaNumeroTreno(trainNumber) {
	const res = await api.get(`cercaNumeroTreno/${trainNumber}`).json();
	if (!res) {
		console.warn(`No results found for train number ${trainNumber}.`);
		return;
	}

	console.log(JSON.stringify(res, null, 2));
}
