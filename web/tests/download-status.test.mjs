import {test} from 'node:test';
import assert from 'node:assert/strict';
import {statusLabel,importLabel} from '../src/lib/download-status.ts';
test('download queue and processing queue have distinct labels',()=>{
 assert.equal(statusLabel('Queued',2),'Queued');
 assert.equal(statusLabel('PostProcessQueued',2),'Waiting for post-processing');
});
test('each processing stage has a specific label',()=>{
 for(const [state,label] of Object.entries({QuickCheck:'Verifying',Verifying:'Verifying',Repairing:'Repairing',Extracting:'Extracting',Moving:'Moving files',Running:'Running post-processing script'}))assert.equal(statusLabel(state,2),label);
});
test('completed download is distinct from completed library import',()=>{
 assert.equal(importLabel({phase:'postprocessing',state:'Extracting'},false),'Import follows post-processing');
 assert.equal(importLabel({phase:'complete',state:'Completed'},false),'Waiting for library import');
 assert.equal(importLabel({state:'Completed',imported:true},true),'In library');
 assert.equal(importLabel(undefined,false),'Import pending');
});
