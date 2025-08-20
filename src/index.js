#!/usr/bin/env bun

/**
 * ViaggiaTreno API command-line utilities.
 *
 * This script provides tools for querying train and station data from
 * the ViaggiaTreno API, including station search, train status, and
 * data export features.
 *
 * Rate limiting and retry logic:
 * - Uses p-queue for concurrent request limiting and rate limiting
 * - Uses ky for HTTP requests with built-in exponential backoff on 403
 * - Automatic retry with configurable parameters for robust API interaction
 */

import { setupCLI } from "./cli.js";
import "temporal-polyfill/global";

/**
 * Main function
 */
async function main() {
	try {
		const program = setupCLI();
		await program.parseAsync(process.argv);
	} catch (error) {
		console.error(`Error: ${error.message}`);
		process.exit(1);
	}
}

// Run main function if this script is executed directly
if (import.meta.main) {
	main().catch((error) => {
		console.error("Unhandled error:", error);
		process.exit(1);
	});
}

export { setupCLI } from "./cli.js";
export { commands } from "./commands/index.js";
export { REGIONS } from "./commands/regions.js";
export * from "./utils.js";
