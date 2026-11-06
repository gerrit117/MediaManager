import {test} from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import {createTranslator} from '../src/lib/i18n/translate.ts';
const entries=fs.readFileSync(new URL('../src/lib/i18n/strings.tsv',import.meta.url),'utf8').trim().split('\n').map(line=>line.split('\t'));
const t=createTranslator(entries);
test('explicit languages, with German and English source labels',()=>{assert.equal(t('de','Settings'),'Einstellungen');assert.equal(t('en','Benutzerverwaltung'),'User management');assert.equal(t('de','Automatic approval'),'Automatische Genehmigung');assert.equal(t('en','Integriert'),'Integrated');});
test('metadata and identifiers are not translated by guessing',()=>{assert.equal(t('en','Some movie title'),'Some movie title');assert.equal(t('de','API-ID-123'),'API-ID-123');});
test('dictionary has no conflicting duplicate keys and no blank values',()=>{const map=new Map();for(const [key,value] of entries){assert.ok(key&&value);assert.ok(!map.has(key)||map.get(key)===value);map.set(key,value);}});

test('explicit message templates preserve user-provided text',()=>{assert.equal(t('de','Found 12 releases.'),'12 Releases gefunden.');assert.equal(t('en','Kategorien für $1.Movies gespeichert.'),'Saved categories for $1.Movies.');});
