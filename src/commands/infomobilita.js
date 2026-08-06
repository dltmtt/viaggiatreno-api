/**
 * Infomobility news commands
 */

import { api } from "../api.js";

/**
 * Get full infomobility RSS news HTML
 *
 * @param {boolean} isInfoLavori - If true, returns planned works; if false, general service news
 * @returns {Promise<string>} HTML fragment containing full news accordion
 */
export async function infomobilitaRSS(isInfoLavori = false) {
	const res = await api.get(`infomobilitaRSS/${Boolean(isInfoLavori)}`).text();
	return res;
}

/**
 * Get infomobility RSS summary box HTML (titles only)
 *
 * @param {boolean} isInfoLavori - If true, returns planned works titles; if false, general service news titles
 * @returns {Promise<string>} HTML fragment containing news titles list
 */
export async function infomobilitaRSSBox(isInfoLavori = false) {
	const res = await api
		.get(`infomobilitaRSSBox/${Boolean(isInfoLavori)}`)
		.text();
	return res;
}

/**
 * Get infomobility news ticker HTML
 *
 * @returns {Promise<string>} HTML fragment containing news ticker list
 */
export async function infomobilitaTicker() {
	const res = await api.get("infomobilitaTicker").text();
	return res;
}
