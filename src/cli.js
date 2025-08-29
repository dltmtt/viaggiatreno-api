/**
 * Command-line interface setup and configuration
 */

import { Command } from "commander";
import data from "../package.json";
import { commands } from "./commands/index.js";
import { REGIONS } from "./commands/regions.js";

/**
 * Check if either a specific argument is provided or the --all option is used.
 * @param {any} argument - The specific argument to check.
 * @param {boolean} all - The --all option flag.
 * @param {Command} command - The Commander.js command instance.
 * @param {string} message - The error message to display.
 */
function requireArgOrAll(argument, all, command, message) {
	if (argument === undefined && !all) {
		console.error(message);
		command.help({ error: true });
	}
	if (argument !== undefined && all) {
		console.warn(
			`Both ${argument} and --all options are specified. Using --all option.`,
		);
	}
}

/**
 * Setup and parse command line arguments using Commander.js
 */
export function setupCLI() {
	const program = new Command();

	program
		.name(Object.keys(data.bin)[0])
		.description(data.description)
		.version(data.version);

	// statistiche command
	program
		.command("statistiche")
		.description("Get API statistics")
		.action(async () => {
			const res = await commands.statistiche();
			console.log(JSON.stringify(res, null, 2));
		});

	// elencoStazioni command
	program
		.command("elencoStazioni")
		.description("List stations by region")
		.argument("[region]", "Region number (0-22)")
		.option("-a, --all", "Fetch stations from all regions")
		.action(async (region, options, command) => {
			requireArgOrAll(
				region,
				options.all,
				command,
				`Specify a region number (0-${Object.keys(REGIONS).length - 1}) or use --all to fetch stations from all regions.`,
			);
			const res = await commands.elencoStazioni(Number(region), options.all);
			console.log(JSON.stringify(res, null, 2));
		});

	// cercaStazione command
	program
		.command("cercaStazione")
		.description("Search stations by prefix")
		.argument("[prefix]", "Station name prefix")
		.option("-a, --all", "Fetch all stations")
		.action(async (prefix, options, command) => {
			requireArgOrAll(
				prefix,
				options.all,
				command,
				"Specify a station name prefix or use --all to fetch all stations.",
			);
			const res = await commands.cercaStazione(prefix, options.all);
			console.log(JSON.stringify(res, null, 2));
		});

	// autocompletaStazione commands
	[
		"autocompletaStazione",
		"autocompletaStazioneImpostaViaggio",
		"autocompletaStazioneNTS",
	].forEach((cmdName) => {
		program
			.command(cmdName)
			.description(`Autocomplete stations using ${cmdName} endpoint`)
			.argument("[prefix]", "Station name prefix")
			.option("-a, --all", "Fetch all stations")
			.action(async (prefix, options, command) => {
				requireArgOrAll(
					prefix,
					options.all,
					command,
					"Specify a station name prefix or use --all to fetch all stations.",
				);
				const res = await commands.autocompleteStation(cmdName, prefix, options.all);
				console.log(res);
			});
	});

	// regione command
	program
		.command("regione")
		.description("Get region information for a station")
		.argument("[station]", "Station name or code")
		.option("--table", "Show region codes table")
		.action((station, options, command) => {
			if ((!station && !options.table) || (station && options.table)) {
				console.error(
					"Specify one of the following: a station name or code, or use --table to show region codes.",
				);
				command.help({ error: true });
			}
			commands.regione(station, options.table);
		});

	// dettaglioStazione command
	program
		.command("dettaglioStazione")
		.description("Get detailed station information")
		.argument("<station>", "Station name or code")
		.option("--region <n>", "Region code", (value) => Number(value))
		.action(async (station, options) => {
			const res = await commands.dettaglioStazione(station, options.region);
			console.log(JSON.stringify(res, null, 2));
		});

	// cercaNumeroTrenoTrenoAutocomplete command
	program
		.command("cercaNumeroTrenoTrenoAutocomplete")
		.description("Search train number with autocomplete")
		.argument("<trainNumber>", "Train number", (value) => Number(value))
		.action(async (trainNumber) => {
			const res = await commands.cercaNumeroTrenoTrenoAutocomplete(trainNumber);
			console.log(res);
		});

	// cercaNumeroTreno command
	program
		.command("cercaNumeroTreno")
		.description("Search train by number")
		.argument("<trainNumber>", "Train number", (value) => Number(value))
		.action(async (trainNumber) => {
			const res = await commands.cercaNumeroTreno(trainNumber);
			console.log(JSON.stringify(res, null, 2));
		});

	// partenze and arrivi commands
	["partenze", "arrivi"].forEach((cmdName) => {
		program
			.command(cmdName)
			.description(`Get ${cmdName} from a station`)
			.argument("[station]", "Station name or code")
			.option(
				"--datetime <datetime>",
				"Search date and time",
				(value) => Temporal.ZonedDateTime.from(value),
				Temporal.Now.zonedDateTimeISO("Europe/Rome"),
			)
			.option("-a, --all", "Process all stations")
			.option("-o, --output <dir>", "Output directory", process.cwd())
			.action(async (station, options, command) => {
				requireArgOrAll(
					station,
					options.all,
					command,
					"Specify a station name or code, or use --all to process all stations.",
				);
				const res = await commands[cmdName](
					station,
					options.datetime,
					options.all,
					options.output,
				);
				console.log(JSON.stringify(res, null, 2));
			});
	});

	// andamentoTreno command
	program
		.command("andamentoTreno")
		.description("Get train status and journey details")
		.argument("<trainNumber>", "Train number", (value) => Number(value))
		.option(
			"-s, --departure-station <station>",
			"Departure station name or code",
		)
		.option("--date <date>", "Departure date", (value) =>
			Temporal.PlainDate.from(value),
		)
		.action(async (trainNumber, options) => {
			const res = await commands.andamentoTreno(
				trainNumber,
				options.departureStation,
				options.date,
			);
			console.log(JSON.stringify(res, null, 2));
		});

	// dump command
	program
		.command("dump")
		.description("Perform a data dump (either dynamic or static)")
		.option(
			"--dynamic",
			"Perform dynamic dump (comprehensive real-time data collection)",
		)
		.option("--static", "Perform static dump (all station-related static data)")
		.option(
			"--datetime <datetime>",
			"Search date and time (for dynamic dump)",
			(value) => Temporal.ZonedDateTime.from(value),
			Temporal.Now.zonedDateTimeISO("Europe/Rome"),
		)
		.option("-o, --output <dir>", "Output directory", process.cwd())
		.action((options, command) => {
			if (!options.dynamic && !options.static) {
				console.error("Specify either --dynamic or --static option.");
				command.help({ error: true });
			}
			commands.dump(
				options.dynamic,
				options.static,
				options.datetime,
				options.output,
			);
		});

	return program;
}
