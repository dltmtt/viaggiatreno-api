/**
 * API client configuration and setup
 */

import ky from "ky";
import PQueue from "p-queue";

/**
 * Configuration for making calls to the ViaggiaTreno API with
 * ky for HTTP requests with built-in retry on retryable errors
 */
export const api = ky.create({
	prefixUrl: "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno",
	timeout: 30_000,
	retry: {
		limit: 10,
		statusCodes: [403],
		backoffLimit: 120_000,
	},
	headers: {
		Accept: "application/json; charset=utf-8, text/*; charset=utf-8",
	},
});

export const queue = new PQueue({
	concurrency: 60,
	interval: 1000,
	intervalCap: 60,
	carryoverConcurrencyCount: true,
});
