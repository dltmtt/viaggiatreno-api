/**
 * Language dictionary command
 */

import { join } from "node:path";
import { api, queue } from "../api.js";

export const LANGUAGES = ["it", "en", "de", "fr", "sp", "ro", "jp", "zh", "ru"];

/**
 * Get language translation dictionary for a language or all languages
 *
 * @param {string} lang - Language code ("it", "en", "de", "fr", "sp", "ro", "jp", "zh", "ru")
 * @param {boolean} all - If true, fetches translation dictionaries for all languages
 * @param {string} output - Output directory for saving results when all is true
 * @returns {Promise<object>} Translation key-value map
 */
export async function language(
	lang = "it",
	all = false,
	output = process.cwd(),
) {
	if (all) {
		return languageAll(output);
	}

	const res = await api.get(`language/${lang}`).json();
	return res;
}

/**
 * Fetch language dictionaries for all languages and save to output directory
 *
 * @param {string} output - Output directory for saving results
 * @returns {Promise<object>} Object mapping language codes to translation dictionaries
 */
export async function languageAll(output = process.cwd()) {
	const outputPath = join(output, "languages");

	console.info("Fetching language dictionaries for all languages...");

	const allLanguagesData = {};

	const tasks = LANGUAGES.map((lang) => async () => {
		const res = await api.get(`language/${lang}`).json();
		Bun.write(join(outputPath, `${lang}.json`), JSON.stringify(res, null, 2));
		allLanguagesData[lang] = res;
		return res;
	});

	await queue.addAll(tasks);

	console.info(`✅ Language dictionaries saved to ${outputPath}.`);
	return allLanguagesData;
}
