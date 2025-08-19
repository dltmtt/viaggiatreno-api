/**
 * Basic API information commands
 */

import { api } from "../api.js";

/**
 * Get API statistics and status information
 *
 * @returns {Promise<void>} Logs the API statistics as JSON
 */
export async function statistiche() {
	const nowMs = Temporal.Now.instant().epochMilliseconds;
	const res = await api.get(`statistiche/${nowMs}`).json();
	console.log(JSON.stringify(res, null, 2));
}
