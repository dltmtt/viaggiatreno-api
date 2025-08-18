/**
 * Utility functions for the ViaggiaTreno API
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

/**
 * Parse CSV with the specified delimiter
 *
 * @param {string} csvText The CSV text to parse
 * @param {string} delimiter The delimiter used in the CSV (default is ",")
 * @returns {Array<Array<string>>} The parsed CSV as an array of rows and columns
 */
export function parseCSV(csvText, delimiter = ",") {
	return csvText
		.trim()
		.split("\n")
		.map((line) => line.split(delimiter));
}

/**
 * Validate mutually exclusive arguments
 * @param {any} arg1 First argument
 * @param {any} arg2 Second argument
 * @param {string} name1 Name of first argument
 * @param {string} name2 Name of second argument
 * @throws {Error} If both arguments are provided
 */
export function validateMutuallyExclusive(arg1, arg2, name1, name2) {
	if (arg1 && arg2) {
		throw new Error(`Cannot specify both ${name1} and ${name2}`);
	}
}

/**
 * Save JSON data to file
 *
 * @param {any} data The data to save
 * @param {string} filePath The path to the file where the data should be saved
 */
export function saveJsonToFile(data, filePath) {
	try {
		mkdirSync(dirname(filePath), { recursive: true });
		writeFileSync(filePath, JSON.stringify(data, null, 2));
	} catch (error) {
		console.error(`Error saving file ${filePath}:`, error.message);
	}
}

/**
 * Save text data to file
 *
 * @param {string} data The text data to save
 * @param {string} filePath The path to the file where the data should be saved
 */
export function saveTextToFile(data, filePath) {
	try {
		mkdirSync(dirname(filePath), { recursive: true });
		writeFileSync(filePath, data);
	} catch (error) {
		console.error(`Error saving file ${filePath}:`, error.message);
	}
}

/**
 * Progress bar class for displaying progress in long-running operations
 *
 * @example
 * const progressBar = new ProgressBar(100);
 * for (let i = 0; i < 100; i++) {
 *   // do some work
 *   progressBar.update();
 * }
 */
export class ProgressBar {
	/**
	 * Create a new progress bar
	 *
	 * @param {number} total - The total number of items to process
	 */
	constructor(total) {
		this.total = total;
		this.current = 0;
	}

	/**
	 * Update the progress bar
	 *
	 * @param {number} increment - The amount to increment by (default: 1)
	 */
	update(increment = 1) {
		this.current += increment;
		const percentage = Math.floor((this.current / this.total) * 100);
		const filled = Math.floor(percentage / 2);
		const bar = "█".repeat(filled) + "░".repeat(50 - filled);
		process.stdout.write(
			`\r[${bar}] ${percentage}% (${this.current}/${this.total})`,
		);

		if (this.current >= this.total) {
			console.log(""); // New line when complete
		}
	}
}
