/**
 * Main commands object that aggregates all command functions
 */

import { dump, dynamicDump } from "./dump.js";
import {
	infomobilitaRSS,
	infomobilitaRSSBox,
	infomobilitaTicker,
} from "./infomobilita.js";
import { datimeteo, datimeteoAll, regione } from "./regions.js";
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
	datimeteo,
	datimeteoAll,
	dettaglioStazione,
	cercaNumeroTrenoTrenoAutocomplete,
	cercaNumeroTreno,
	partenze,
	arrivi,
	andamentoTreno,
	infomobilitaRSS,
	infomobilitaRSSBox,
	infomobilitaTicker,
	dynamicDump,
	dump,
};
