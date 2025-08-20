/**
 * Main commands object that aggregates all command functions
 */

import { dump, dynamicDump } from "./dump.js";
import { regione } from "./regions.js";
import { arrivi, partenze } from "./schedules.js";
import {
	autocompleteStation,
	cercaStazione,
	dettaglioStazione,
	elencoStazioni,
} from "./stations.js";
import { statistiche } from "./statistics.js";
import {
	andamentoTreno,
	cercaNumeroTreno,
	cercaNumeroTrenoTrenoAutocomplete,
} from "./trains.js";

export const commands = {
	statistiche,
	elencoStazioni,
	cercaStazione,
	autocompleteStation,
	regione,
	dettaglioStazione,
	cercaNumeroTrenoTrenoAutocomplete,
	cercaNumeroTreno,
	partenze,
	arrivi,
	andamentoTreno,
	dynamicDump,
	dump,
};
