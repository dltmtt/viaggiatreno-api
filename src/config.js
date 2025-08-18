/**
 * Configuration constants for the ViaggiaTreno API
 */

import { join } from "node:path";
import envPaths from "env-paths";

// Get platform-appropriate paths for the app
const paths = envPaths("vt-api", { suffix: "" });

export const CONFIG = {
	MAX_RESULTS_TO_SHOW: 10,
	DEFAULT_OUTPUT_DIR: join(paths.data, "dumps"),
	DEFAULT_STATIONS_FILE: join(paths.data, "dumps", "autocompletaStazione.csv"),
};

export const REGIONS = {
	0: "Italia",
	1: "Lombardia",
	2: "Liguria",
	3: "Piemonte",
	4: "Valle d'Aosta",
	5: "Lazio",
	6: "Umbria",
	7: "Molise",
	8: "Emilia Romagna",
	9: "Trentino-Alto Adige",
	10: "Friuli-Venezia Giulia",
	11: "Marche",
	12: "Veneto",
	13: "Toscana",
	14: "Sicilia",
	15: "Basilicata",
	16: "Puglie",
	17: "Calabria",
	18: "Campania",
	19: "Abruzzo",
	20: "Sardegna",
	21: "Provincia autonoma di Trento",
	22: "Provincia autonoma di Bolzano",
};
