"""Match catalogues by provider IDs; titles never establish an automatic identity."""
from datetime import datetime,timezone
from sqlalchemy import select
from media_manager.emby import EmbyClient,playable
from media_manager.media_features_models import EmbyMatch
from media_manager.movies.models import Movie
from media_manager.tv.models import Show,Season,Episode
from media_manager.library_models import ShowExternalId

def identifiers(media,aliases=()):
    result={media.metadata_provider.lower():str(media.external_id)}
    if getattr(media,'imdb_id',None):result['imdb']=media.imdb_id
    for alias in aliases:result.setdefault(alias.provider.lower(),str(alias.external_id))
    return result

def provider_ids(item):return {k.lower():str(v) for k,v in item.get('ProviderIds',{}).items() if v}
def identity_match(ids,item):
    actual=provider_ids(item);common=set(ids)&set(actual)
    # A conflicting identifier is not rescued by a matching title or another provider.
    return bool(common) and all(ids[k]==actual[k] for k in common)

def episode_match(episode,provider,item):
    actual=provider_ids(item)
    if provider in actual and episode.external_id:
        return actual[provider]==str(episode.external_id)
    return item.get('IndexNumber')==episode.number and item.get('ParentIndexNumber')==episode.season.number

def scan(db,client=None):
    client=client or EmbyClient()
    # Fetch completely before writing: failed/partial API reads cannot clear known matches.
    catalogue=client.items(Recursive='true',IncludeItemTypes='Movie,Series',Fields='ProviderIds,Path,MediaSources',IsMissing='false',IsVirtualItem='false')
    rows=[];series_episodes={}
    def save(kind,media,items,evidence,status=None):
        row=db.get(EmbyMatch,(kind,media.id))
        if row is None:row=EmbyMatch(kind=kind,media_id=media.id,status='unmatched',emby_ids=[],evidence={},checked_at=datetime.now(timezone.utc));db.add(row)
        row.status=status or ('matched' if items else 'unmatched');row.emby_ids=[i['Id'] for i in items];row.evidence=evidence;row.checked_at=datetime.now(timezone.utc);rows.append(row)
    for model,kind in [(Movie,'movie'),(Show,'show')]:
        for media in db.scalars(select(model)):
            aliases=list(db.scalars(select(ShowExternalId).where(ShowExternalId.show_id==media.id))) if kind=='show' else []
            ids=identifiers(media,aliases)
            matches=[i for i in catalogue if i.get('Type')==('Movie' if kind=='movie' else 'Series') and identity_match(ids,i) and (kind=='show' or playable(i))]
            save(kind,media,matches,{'provider_ids':ids,'title':media.name})
            if kind=='show':
                episodes=[]
                for item in matches:
                    if item['Id'] not in series_episodes:series_episodes[item['Id']]=client.items(ParentId=item['Id'],Recursive='true',IncludeItemTypes='Episode',Fields='ProviderIds,Path,MediaSources',IsMissing='false',IsVirtualItem='false')
                    episodes.extend(ep for ep in series_episodes[item['Id']] if playable(ep))
                for season in db.scalars(select(Season).where(Season.show_id==media.id)):
                    seasonmatches=[];expected=list(db.scalars(select(Episode).where(Episode.season_id==season.id)))
                    for ep in expected:
                        candidates=[item for item in episodes if episode_match(ep,media.metadata_provider,item)]
                        candidates=[item for item in candidates if item.get('ParentIndexNumber')==season.number and item.get('IndexNumber')==ep.number]
                        save('episode',ep,candidates,{'title':media.name,'season':season.number,'episode':ep.number,'method':'episode_provider_id_or_series_id_and_number'})
                        seasonmatches.extend(candidates)
                    save('season',season,seasonmatches,{'title':media.name,'season':season.number,'available':sum(1 for ep in expected if any(episode_match(ep,media.metadata_provider,item) and item.get('ParentIndexNumber')==season.number for item in episodes)),'total':len(expected)})
    db.commit();return summary(db)

def summary(db):
    rows=list(db.scalars(select(EmbyMatch)))
    return {'checked_at':max((r.checked_at for r in rows),default=None),'counts':{kind:{'matched':sum(r.kind==kind and r.status=='matched' for r in rows),'unmatched':sum(r.kind==kind and r.status!='matched' for r in rows)} for kind in ['movie','show','season','episode']},'items':[{'kind':r.kind,'media_id':r.media_id,'status':r.status,'emby_ids':r.emby_ids,'details':r.evidence} for r in rows if r.kind in ('movie','show')]}

def automatic_scan():
    from media_manager.config import MediaManagerConfig
    from media_manager.database import get_session
    from sqlalchemy import text
    import logging
    if not MediaManagerConfig().emby.enabled:return
    with next(get_session()) as db:
        with db.get_bind().connect() as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(194731, 712)')):return
            try:scan(db)
            except Exception:db.rollback();logging.getLogger(__name__).warning('Emby matching failed; existing matches were retained.')
            finally:connection.execute(text('SELECT pg_advisory_unlock(194731, 712)'))
