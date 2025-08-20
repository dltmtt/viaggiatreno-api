/**
 * Region-related commands
 */

import { api } from "../api.js";
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
