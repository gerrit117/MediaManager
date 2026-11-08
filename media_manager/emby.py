"""Read-only server-wide availability checks. Never reads playback history or users."""
import requests
from media_manager.config import MediaManagerConfig
class EmbyClient:
    def __init__(self,config=None):self.config=config or MediaManagerConfig().emby;self.cache={}
    def get(self,path,**params):
        response=requests.get(self.config.url.rstrip('/')+'/emby/'+path.lstrip('/'),headers={'X-Emby-Token':self.config.api_key},params=params,timeout=(5,15),allow_redirects=False)
        response.raise_for_status();return response.json()
    def items(self,**params):
        result=[];start=0
        while True:
            data=self.get('Items',StartIndex=start,Limit=200,**params);page=data.get('Items',[]);result.extend(page);start+=len(page)
            if not page or start>=data.get('TotalRecordCount',start):break
            if start>=20000:raise ValueError('Emby result limit exceeded.')
        return result
    def available(self,media,kind,season=None,episodes=None,aliases=(),expected_paths=()):
        if not self.config.enabled:return None
        try:
            from media_manager.emby_matching import identifiers,identity_match
            ids=identifiers(media,aliases)
            identity=(tuple(sorted(ids.items())),'Movie' if kind=='movie' else 'Series')
            if identity not in self.cache:
                self.cache[identity]=self.items(Recursive='true',IncludeItemTypes=identity[1],AnyProviderIdEquals=','.join(f'{p}.{i}' for p,i in ids.items()),Fields='ProviderIds,Path,MediaSources',IsMissing='false',IsVirtualItem='false')
            matches=[i for i in self.cache[identity] if identity_match(ids,i)]
            if kind=='movie':return any(playable(i) and path_matches(i,expected_paths) for i in matches)
            required=set(episodes or [])
            if not required:return False
            for item in matches:
                key=('episodes',item['Id'])
                if key not in self.cache:self.cache[key]=self.items(ParentId=item['Id'],Recursive='true',IncludeItemTypes='Episode',Fields='MediaSources',IsMissing='false',IsVirtualItem='false')
                present=set()
                for ep in self.cache[key]:
                    if ep.get('ParentIndexNumber')==season and playable(ep) and path_matches(ep,expected_paths):
                        start=ep.get('IndexNumber');end=ep.get('IndexNumberEnd') or start
                        if isinstance(start,int) and isinstance(end,int) and 0<=end-start<=500:present.update(range(start,end+1))
                if required<=present:return True
            return False
        except (requests.RequestException,ValueError,KeyError,TypeError):return None

def playable(item):
    return not item.get('IsVirtualItem') and not item.get('IsMissing') and item.get('LocationType')!='Virtual' and bool(item.get('Path') or item.get('MediaSources'))

def path_matches(item,expected_paths):
    from pathlib import PurePosixPath
    if not expected_paths:return True
    actual=[item.get('Path','')]+[source.get('Path','') for source in item.get('MediaSources',[])]
    # Containers may mount the same library at different prefixes; stable relative filenames identify imports.
    filenames={PurePosixPath(str(p).replace('\\','/')).name for p in expected_paths}
    return any(PurePosixPath(str(p).replace('\\','/')).name in filenames for p in actual if p)
