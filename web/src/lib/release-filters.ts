export type Release = { title: string; usenet?: boolean };
export type Facets = { resolution: string[]; source: string[]; audio: string[]; protocol: string[] };
export const emptyFacets = (): Facets => ({ resolution: [], source: [], audio: [], protocol: [] });
export const facetLabels: Record<keyof Facets, string> = { resolution: 'Auflösung', source: 'Bildquelle', audio: 'Audio', protocol: 'Downloadart' };
const boundary = (pattern: string) => new RegExp(`(?:^|[^a-z0-9])(?:${pattern})(?=$|[^a-z0-9])`, 'i');
export function releaseTags(release: Release): Facets {
 const title = release.title;
 const tags = emptyFacets();
 const resolution: [string, string][] = [['2160p', '2160p|4k|uhd'], ['1080p', '1080[pi]|full[ ._-]?hd'], ['720p', '720p'], ['SD', '480p|576[pi]|360p|sd']];
 for (const [label, pattern] of resolution) if (boundary(pattern).test(title)) { tags.resolution.push(label); break; }
 const source: [string, string][] = [['REMUX', 'remux'], ['BDRip', 'bdrip'], ['BRRip', 'brrip'], ['BluRay', 'blu[ ._-]?ray|bdmv'], ['WEB-DL', 'web[ ._-]?dl'], ['WEBRip', 'web[ ._-]?rip'], ['WEB', 'web'], ['HDTV', 'hdtv'], ['DVD', 'dvd[ ._-]?rip|dvd'], ['CAM/TS', 'cam|hdcam|ts|telesync|telecine|hdts|tc']];
 for (const [label, pattern] of source) if (boundary(pattern).test(title)) tags.source.push(label);
 if (tags.source.includes('WEB-DL') || tags.source.includes('WEBRip')) tags.source = tags.source.filter(x => x !== 'WEB');
 const audio: [string, string][] = [['Atmos', 'atmos'], ['TrueHD', 'true[ ._-]?hd'], ['DTS-HD', 'dts[ ._-]?hd(?:[ ._-]?ma)?'], ['DTS', 'dts'], ['DD+', 'ddp(?:[ ._-]?\\d(?:[ ._-]\\d)?)?|dd\\+|e[ ._-]?ac[ ._-]?3'], ['AC3/DD', 'ac[ ._-]?3|dd(?:[ ._-]?\\d(?:[ ._-]\\d)?)?'], ['AAC', 'aac'], ['FLAC', 'flac'], ['MP3', 'mp3'], ['5.1', '5[ ._-]1'], ['7.1', '7[ ._-]1'], ['2.0', '2[ ._-]0'], ['Deutsch', 'german|deutsch|ger'], ['Englisch', 'english|eng'], ['Mic/Line dubbed', 'mic[ ._-]?dubbed|md|line[ ._-]?dubbed|ld']];
 const audioTitle = title.replace(/(ddp|dd|aac|ac3|dts|truehd)(?=\d)/ig, '$1.');
 for (const [label, pattern] of audio) if (boundary(pattern).test(audioTitle)) tags.audio.push(label);
 if (tags.audio.includes('DTS-HD')) tags.audio = tags.audio.filter(x => x !== 'DTS');
 tags.protocol = [release.usenet ? 'Usenet / NZB' : 'Torrent'];
 return tags;
}
// OR within a group; AND between groups. Only filters already fetched results.
export function matchesFacets(release: Release, selected: Facets): boolean {
 const tags = releaseTags(release);
 return (Object.keys(selected) as (keyof Facets)[]).every(group => !selected[group].length || selected[group].some(tag => tags[group].includes(tag)));
}
export function availableFacets(releases: Release[]): Facets {
 const result = emptyFacets();
 for (const release of releases) {
  const tags = releaseTags(release);
  for (const group of Object.keys(result) as (keyof Facets)[]) for (const tag of tags[group]) if (!result[group].includes(tag)) result[group].push(tag);
 }
 return result;
}
