import type {DownloadProgress} from './download-progress';
const labels:Record<string,string>={Downloading:'Downloading',Queued:'Queued',Paused:'Paused',QueuePaused:'Queue paused',Completed:'Completed',Failed:'Failed',Extracting:'Extracting',Moving:'Moving files',Running:'Running post-processing script',Repairing:'Repairing',Verifying:'Verifying',QuickCheck:'Verifying',Fetching:'Downloading repair data',Propagating:'Waiting for availability',PostProcessQueued:'Waiting for post-processing',PostProcessing:'Post-processing',Unknown:'Status unknown'};
export function statusLabel(state:string|undefined,fallback:number):string {
 return state ? labels[state]??state : ({1:'Completed',2:'Downloading',3:'Failed',4:'Status unknown'}[fallback]??'Status unknown');
}
export function importLabel(live:DownloadProgress|undefined,imported:boolean):string {
 if(imported)return 'In library';
 if(live?.phase==='postprocessing')return 'Import follows post-processing';
 if(live?.state==='Completed')return 'Waiting for library import';
 return 'Import pending';
}
