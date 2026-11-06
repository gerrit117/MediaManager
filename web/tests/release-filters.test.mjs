import {test} from 'node:test';
import assert from 'node:assert/strict';
import {releaseTags,matchesFacets,emptyFacets,availableFacets} from '../src/lib/release-filters.ts';
test('scene tags distinguish source, audio and resolution',()=>{
 const tags=releaseTags({title:'Own.German.2160p.WEB-DL.DDP5.1.Atmos',usenet:true});
 assert.deepEqual(tags.resolution,['2160p']);assert.deepEqual(tags.source,['WEB-DL']);
 for(const expected of ['DD+','5.1','Atmos','Deutsch'])assert.ok(tags.audio.includes(expected));
 assert.deepEqual(tags.protocol,['Usenet / NZB']);
});
test('punctuation audio and hierarchy',()=>{
 const tags=releaseTags({title:'Own.1080p.BluRay.DD+.DTS-HD.MA.7.1'});
 assert.ok(tags.audio.includes('DD+'));assert.ok(tags.audio.includes('DTS-HD'));assert.ok(!tags.audio.includes('DTS'));
});
test('words are not matched inside titles',()=>{const tags=releaseTags({title:'Cambridge.Webster.Germany'});assert.deepEqual(tags.source,[]);assert.deepEqual(tags.audio,[]);});
test('unknown tags do not invent metadata',()=>{assert.deepEqual(releaseTags({title:'Own release'}).resolution,[]);});
test('OR in a group, AND between groups and reset',()=>{
 const release={title:'Own.1080p.WEBRip.AAC.German',usenet:true};const filter=emptyFacets();filter.resolution=['720p','1080p'];filter.audio=['Deutsch'];
 assert.equal(matchesFacets(release,filter),true);filter.source=['BDRip'];assert.equal(matchesFacets(release,filter),false);assert.equal(matchesFacets(release,emptyFacets()),true);
});
test('only offers available facets, both protocols',()=>{const result=availableFacets([{title:'Own.720p.BDRip',usenet:true},{title:'Own.1080p.WEBRip',usenet:false}]);assert.equal(result.resolution.length,2);assert.equal(result.protocol.length,2);assert.deepEqual(result.audio,[]);});
