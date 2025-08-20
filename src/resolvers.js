/**
 * Station and train resolution functions
 */

import { api } from "./api.js";

const MAX_RESULTS_TO_SHOW = 10;

/**
 * Parse CSV with the specified delimiter
 *
 * @param {string} csvText The CSV text to parse
 * @param {string} delimiter The delimiter used in the CSV (default is ",")
 * @returns {Array<Array<string>>} The parsed CSV as an array of rows and columns
 */
function parseCSV(csvText, delimiter = ",") {
	return csvText
		.trim()
		.split("\n")
		.map((line) => line.split(delimiter));
}

/**
 * Resolve station input to station code
 *
 * If the input is a station name, it searches for the corresponding code.
 * If it's a code, it returns it directly.
 *
 * @param {string} stationInput The station code or name to resolve
 * @returns {Promise<string>} A promise that resolves to the station code
 * @throws {Error} If no matching station is found or if the selection is invalid
 */
export async function resolveStationCode(stationInput) {
	// Check if input is already a station code
	if (/^S\d{5}$/i.test(stationInput)) {
		return stationInput.toUpperCase();
	}

	// Search for station by name
	const res = await api.get(`autocompletaStazione/${stationInput}`).text();
	const stations = parseCSV(res, "|");

	if (stations.length === 0 || stations[0].length === 0) {
		throw new Error(`No stations found matching '${stationInput}'.`);
	}

	// If there is only one station, return its code
	if (stations.length === 1) return stations[0][1];

	// If there are multiple stations, show options
	console.log(`Multiple stations found matching '${stationInput}':`);
	for (let i = 0; i < Math.min(stations.length, MAX_RESULTS_TO_SHOW); i++) {
		const [stationName, stationCode] = stations[i];
		console.log(`  ${i + 1}. ${stationName} (${stationCode})`);
	}

	if (stations.length > MAX_RESULTS_TO_SHOW) {
		const remaining = stations.length - MAX_RESULTS_TO_SHOW;
		console.log(`  ...and ${remaining} more results.`);
	}

	const input = prompt("Please choose a station number (or 0 to cancel)");
	const choice = Number(input);

	if (choice === 0 || choice > stations.length) {
		throw new Error("Selection cancelled or invalid.");
	}

	// Return the code of the selected station
	return stations[choice - 1][1];
}

/**
 * Associate train number with departure station code and departure date
 *
 * A train is identified by the triple <trainNumber, departureStationCode,
 * departureDate>. This function finds the possible departure station codes
 * and departure dates for a given train number.
 *
 * @param {string} trainNumber The train number to resolve
 * @returns {Promise<[string, Temporal.PlainDate]>} A promise that resolves to a tuple containing the departure station code and the departure date associated with the train number
 * @throws {Error} If no matching train is found
 */
export async function resolveTrainDetails(trainNumber) {
	// Search for possible train matches
	const res = await api
		.get(`cercaNumeroTrenoTrenoAutocomplete/${trainNumber}`)
		.text();
	const trains = parseCSV(res, "|");

	if (trains.length === 0 || trains[0].length === 0) {
		throw new Error(`No trains found with number ${trainNumber}.`);
	}

	// If there is only one train with the given number, return its details
	if (trains.length === 1) {
		const [humanReadablePart, machineReadablePart] = trains[0];
		const stationName = humanReadablePart.split(" - ")[1];
		const stationCode = machineReadablePart.split("-")[1];
		const departureDateMs = Number(machineReadablePart.split("-")[2]);
		const departureDate = Temporal.Instant.fromEpochMilliseconds(
			departureDateMs,
		)
			.toZonedDateTimeISO("Europe/Rome")
			.toPlainDate();

		console.info(
			`Using train: ${trainNumber} departing from ${stationName} (${stationCode}) on ${departureDate.toString()}.`,
		);

		return [stationCode, departureDate];
	}

	// If multiple trains share the same number, show options
	console.log(`Multiple trains found with number ${trainNumber}:`);
	for (let i = 0; i < Math.min(trains.length, MAX_RESULTS_TO_SHOW); i++) {
		const [humanReadablePart, machineReadablePart] = trains[i];
		const stationName = humanReadablePart.split(" - ")[1];
		const stationCode = machineReadablePart.split("-")[1];
		const departureDateMs = Number(machineReadablePart.split("-")[2]);
		const departureDate = Temporal.Instant.fromEpochMilliseconds(
			departureDateMs,
		)
			.toZonedDateTimeISO("Europe/Rome")
			.toPlainDate();

		console.log(
			`  ${i + 1}. Train ${trainNumber} departing from ${stationName} (${stationCode}) on ${departureDate.toString()}.`,
		);
	}

	if (trains.length > MAX_RESULTS_TO_SHOW) {
		const remaining = trains.length - MAX_RESULTS_TO_SHOW;
		console.log(`  ...and ${remaining} more results.`);
	}

	const input = prompt("Please choose a train number (or 0 to cancel)");
	const choice = Number(input);

	if (choice === 0 || choice > trains.length) {
		throw new Error("Selection cancelled or invalid.");
	}

	const [humanReadablePart, machineReadablePart] = trains[choice - 1];
	const stationName = humanReadablePart.split(" - ")[1];
	const stationCode = machineReadablePart.split("-")[1];
	const departureDateMs = Number(machineReadablePart.split("-")[2]);
	const departureDate = Temporal.Instant.fromEpochMilliseconds(departureDateMs)
		.toZonedDateTimeISO("Europe/Rome")
		.toPlainDate();

	console.info(
		`Selected: Train ${trainNumber} departing from ${stationName} (${stationCode}) on ${departureDate.toString()}.`,
	);

	// Return the details of the selected train
	return [stationCode, departureDate];
}
