/**
 * Train search and status commands
 */

import { join } from "node:path";
import { api, queue } from "../api.js";
import {
	ProgressBar,
	resolveStationCode,
	resolveTrainDetails,
} from "../utils.js";

/**
 * Search for train numbers using autocomplete functionality
 *
 * @param {number} trainNumber - The train number to search for
 */
export async function cercaNumeroTrenoTrenoAutocomplete(trainNumber) {
	const res = await api
		.get(`cercaNumeroTrenoTrenoAutocomplete/${trainNumber}`)
		.text();
	if (!res) {
		console.warn(`No results found for train number ${trainNumber}.`);
		return;
	}

	return res.trim();
}

/**
 * Search for detailed train information by train number
 *
 * @param {number} trainNumber - The train number to search for
 */
export async function cercaNumeroTreno(trainNumber) {
	const res = await api.get(`cercaNumeroTreno/${trainNumber}`).json();
	if (!res) {
		console.warn(`No results found for train number ${trainNumber}.`);
		return;
	}

	return res;
}

/**
 * Get real-time status and journey information for a specific train
 *
 * @param {string|number} trainNumber - The train number to track
 * @param {string} departureStation - The departure station code or name (optional)
 * @param {Temporal.PlainDate} departureDate - The departure date (optional)
 */
export async function andamentoTreno(
	trainNumber,
	departureStation,
	departureDate,
) {
	if (!departureStation || !departureDate) {
		[departureStation, departureDate] = await resolveTrainDetails(trainNumber);
	} else {
		departureStation = await resolveStationCode(departureStation);
	}

	const departureDateMs = departureDate
		.toPlainDateTime({ hour: 0, minute: 0, second: 0 })
		.toZonedDateTime("Europe/Rome").epochMilliseconds;
	const res = await api
		.get(`andamentoTreno/${departureStation}/${trainNumber}/${departureDateMs}`)
		.json();

	if (!res) {
		console.warn(
			`No results found for train ${trainNumber} departing from ${departureStation} on ${departureDate.toString()}.`,
		);
		return;
	}

	return res;
}

/**
 * Bulk processing of andamentoTreno data for multiple trains
 *
 * @param {[number, string, Temporal.PlainDate]} trains - Triple containing [trainNumber, stationCode, departureDate]
 * @param {string} output - Output directory path for saving results
 */
export async function andamentoTrenoBulk(trains, output) {
	console.info(
		`Processing andamentoTreno for ${trains.length} unique trains...`,
	);

	const outputPath = join(output, "andamentoTreno");
	const stats = { saved: 0, empty: 0 };
	const now = Temporal.Now.zonedDateTimeISO("Europe/Rome");

	const progressBar = new ProgressBar(trains.length);

	const fetchTrainData = (train) => async () => {
		const [trainNumber, stationCode, departureDateMs] = train;
		const result = await api
			.get(`andamentoTreno/${stationCode}/${trainNumber}/${departureDateMs}`)
			.json();
		progressBar.update();

		if (!result) {
			stats.empty++;
			return;
		}

		const humanReadableDate = Temporal.Instant.fromEpochMilliseconds(
			departureDateMs,
		)
			.toZonedDateTimeISO("Europe/Rome")
			.toPlainDate()
			.toString();
		const filename = `${trainNumber}_${stationCode}_${humanReadableDate}@${now.day}T${now.hour}:${now.minute}_andamentoTreno.json`;
		Bun.write(join(outputPath, filename), JSON.stringify(result, null, 2));
		stats.saved++;
	};

	const tasks = trains.map(fetchTrainData);
	await queue.addAll(tasks);

	console.log("");
	console.info("✅ Completed processing all trains for andamentoTreno:");
	console.info(`    - ${stats.saved} results saved.`);
	console.info(`    - ${stats.empty} empty results not saved.`);
	console.info(`Results saved in ${outputPath}.`);
}
