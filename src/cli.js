/**
 * Command-line interface setup and configuration
 */

import { Command } from "commander";
import { commands } from "./commands/index.js";
import { validateMutuallyExclusive } from "./utils.js";

/**
 * Setup and parse command line arguments using Commander.js
 */
export function setupCLI() {
	const program = new Command();

	program
		.name("vt-api")
		.description("ViaggiaTreno API command-line utilities")
		.version("1.0.0");

	// statistiche command
	program
		.command("statistiche")
		.description("Get API statistics")
		.action(commands.statistiche);

	// elencoStazioni command
	program
		.command("elencoStazioni")
		.description("List stations by region")
		.argument("[region]", "Region number (0-22)")
		.option("-a, --all", "Fetch stations from all regions")
		.action((region, options) => {
			validateMutuallyExclusive(
				region !== undefined,
				options.all,
				"region argument",
				"--all option",
			);
			commands.elencoStazioni(Number(region), options.all);
		});

	// cercaStazione command
	program
		.command("cercaStazione")
		.description("Search stations by prefix")
		.argument("[prefix]", "Station name prefix")
		.option("-a, --all", "Fetch all stations")
		.action((prefix, options) => {
			validateMutuallyExclusive(
				prefix,
				options.all,
				"prefix argument",
				"--all option",
			);
			commands.cercaStazione(prefix, options.all);
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
			.action((prefix, options) => {
				validateMutuallyExclusive(
					prefix,
					options.all,
					"prefix argument",
					"--all option",
				);
				commands.autocompleteStation(cmdName, prefix, options.all);
			});
	});

	// regione command
	program
		.command("regione")
		.description("Get region information for a station")
		.argument("[station]", "Station name or code")
		.option("--table", "Show region codes table")
		.action((station, options) => {
			validateMutuallyExclusive(
				station,
				options.table,
				"station argument",
				"--table option",
			);
			commands.regione(station, options.table);
		});

	// dettaglioStazione command
	program
		.command("dettaglioStazione")
		.description("Get detailed station information")
		.argument("<station>", "Station name or code")
		.option("--region <n>", "Region code", (value) => Number(value))
		.action((station, options) => {
			commands.dettaglioStazione(station, options.region);
		});

	// cercaNumeroTrenoTrenoAutocomplete command
	program
		.command("cercaNumeroTrenoTrenoAutocomplete")
		.description("Search train number with autocomplete")
		.argument("<trainNumber>", "Train number", (value) => Number(value))
		.action((trainNumber) => {
			commands.cercaNumeroTrenoTrenoAutocomplete(trainNumber);
		});

	// cercaNumeroTreno command
	program
		.command("cercaNumeroTreno")
		.description("Search train by number")
		.argument("<trainNumber>", "Train number", (value) => Number(value))
		.action((trainNumber) => {
			commands.cercaNumeroTreno(trainNumber);
		});

	// partenze command
	program
		.command("partenze")
		.description("Get departures from a station")
		.argument("[station]", "Station name or code")
		.option(
			"--datetime <datetime>",
			"Search date and time",
			(value) => Temporal.ZonedDateTime.from(value),
			Temporal.Now.zonedDateTimeISO("Europe/Rome"),
		)
		.option("-a, --all", "Process all stations")
		.option("-o, --output <dir>", "Output directory", process.cwd())
		.action((station, options) => {
			validateMutuallyExclusive(
				station,
				options.all,
				"station argument",
				"--all option",
			);
			commands.partenze(station, options.datetime, options.all, options.output);
		});

	// arrivi command
	program
		.command("arrivi")
		.description("Get arrivals at a station")
		.argument("[station]", "Station name or code")
		.option(
			"--datetime <datetime>",
			"Search date and time",
			(value) => Temporal.ZonedDateTime.from(value),
			Temporal.Now.zonedDateTimeISO("Europe/Rome"),
		)
		.option("-a, --all", "Process all stations")
		.option("-o, --output <dir>", "Output directory", process.cwd())
		.action((station, options) => {
			validateMutuallyExclusive(
				station,
				options.all,
				"station argument",
				"--all option",
			);
			commands.arrivi(station, options.datetime, options.all, options.output);
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
		.action((trainNumber, options) => {
			commands.andamentoTreno(
				trainNumber,
				options.departureStation,
				options.date,
			);
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
		.action((options) => {
			commands.dump(
				options.dynamic,
				options.static,
				options.datetime,
				options.output,
			);
		});

	return program;
}
