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
