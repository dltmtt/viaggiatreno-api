/**
 * Train status and journey tracking commands
 */

import { join } from "node:path";
import { api, queue } from "../api.js";
import { resolveStationCode, resolveTrainDetails } from "../resolvers.js";
import { ProgressBar, saveJsonToFile } from "../utils.js";

/**
 * Get real-time status and journey information for a specific train
 *
 * @param {string|number} trainNumber - The train number to track
 * @param {string} departureStation - The departure station code or name (optional)
 * @param {Date} departureDate - The departure date (optional)
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

	const departureDateMs = departureDate.getTime();
	const res = await api
		.get(`andamentoTreno/${departureStation}/${trainNumber}/${departureDateMs}`)
		.json();

	if (!res) {
		console.warn(
			`No results found for train ${trainNumber} departing from ${departureStation} on ${departureDate.toDateString()}.`,
		);
		return;
	}

	console.log(JSON.stringify(res, null, 2));
}

/**
 * Bulk processing of andamentoTreno data for multiple trains
 *
 * @param {Array<Array>} trains - Array of train data [trainNumber, stationCode, departureDateMs]
 * @param {string} output - Output directory path for saving results
 */
export async function andamentoTrenoBulk(trains, output) {
	console.info(
		`Processing andamentoTreno for ${trains.length} unique trains...`,
	);

	const outputPath = join(output, "andamentoTreno");
	const stats = { saved: 0, empty: 0 };
	const now = new Date().toISOString();

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

		const humanReadableDate = new Date(Number(departureDateMs))
			.toISOString()
			.split("T")[0];
		const filename = `${trainNumber}_${stationCode}_${humanReadableDate}_${now}_andamentoTreno.json`;
		const filePath = join(outputPath, filename);

		saveJsonToFile(result, filePath);
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
