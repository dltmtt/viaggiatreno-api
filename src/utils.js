/**
 * Utility functions for the ViaggiaTreno API
 */

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
