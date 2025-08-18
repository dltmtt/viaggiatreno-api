/**
 * Main commands object that aggregates all command functions
 */

import { dump, dynamicDump } from "./dump.js";
import { andamentoTreno } from "./journey.js";
import { dettaglioStazione, regione } from "./regions.js";
import { arrivi, partenze } from "./schedules.js";
import {
	autocompleteStation,
	cercaStazione,
	elencoStazioni,
} from "./stations.js";
import { statistiche } from "./statistics.js";
import {
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
