"""File presence is distinct from aired, future, special and empty metadata entries."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from media_manager.library import video_files,episode_numbers

def describe(season,present,today=None,pending=(),attention=(),requested=()):
    today=today or datetime.now(ZoneInfo('Europe/Berlin')).date()
    result=[]
    for episode in sorted(season.episodes,key=lambda e:e.number):
        state=('available' if episode.number in present else 'attention' if episode.number in attention else 'downloading' if episode.number in pending else 'upcoming' if episode.air_date and episode.air_date>today else 'unknown' if episode.air_date is None else 'missing')
        data=episode.model_dump() if hasattr(episode,'model_dump') else {k:getattr(episode,k) for k in ['id','number','external_id','title','air_date']}
        result.append(data|{'downloaded':state=='available','state':state,'requested':episode.number in requested})
    counts={key:sum(x['state']==key for x in result) for key in ['available','missing','upcoming','unknown','downloading','attention']}
    required=[x for x in result if x['state']!='upcoming']
    complete=bool(required) and all(x['downloaded'] for x in required)
    state='empty' if not result else 'complete' if complete else 'attention' if counts['attention'] else 'missing' if counts['missing'] else 'downloading' if counts['downloading'] else 'unknown' if counts['unknown'] else 'upcoming'
    return {'episodes':result,'downloaded':complete,'state':state,'available_count':counts['available'],'missing_count':counts['missing'],'upcoming_count':counts['upcoming'],'unknown_count':counts['unknown'],'total_count':len(result)}


def season_presence(service,show,season):
    files=video_files(service.get_root_season_directory(show,season.number))
    for row in service.tv_repository.get_season_files_by_season_id(season.id):
        files.extend(p for p in (row.source_files or []) if Path(p).is_file())
    return episode_numbers(files,season.number)


def public_show(service,show):
    from sqlalchemy import select
    from media_manager.tv.schemas import PublicShow,PublicSeason
    from media_manager.library_models import EpisodeRequest,ShowExternalId
    from media_manager.tv.models import Episode,Season,SeasonFile
    from media_manager.torrent.models import Torrent
    db=service.tv_repository.db
    aliases={r.provider:r.external_id for r in db.scalars(select(ShowExternalId).where(ShowExternalId.show_id==show.id))}
    aliases[show.metadata_provider]=str(show.external_id)
    requested=set(db.scalars(select(EpisodeRequest.episode_id).join(Episode,EpisodeRequest.episode_id==Episode.id).join(Season,Episode.season_id==Season.id).where(Season.show_id==show.id)).all())
    seasons=[]
    for season in sorted(show.seasons,key=lambda s:s.number):
        present=season_presence(service,show,season);pending=set();attention=set()
        for record,torrent in db.execute(select(SeasonFile,Torrent).join(Torrent,SeasonFile.torrent_id==Torrent.id).where(SeasonFile.season_id==season.id,Torrent.imported==False)):
            coverage=set(record.episode_numbers or episode_numbers([torrent.title],season.number) or [e.number for e in season.episodes])
            (attention if torrent.status.name in ['error','unknown'] else pending).update(coverage)
        summary=describe(season,present,pending=pending,attention=attention,requested={e.number for e in season.episodes if e.id in requested})
        if not summary['total_count']:continue
        seasons.append(PublicSeason(**(season.model_dump()|summary)))
    result=PublicShow.model_validate(show);result.seasons=seasons;result.external_ids=aliases
    return result
