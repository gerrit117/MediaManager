"""Shared release selection and download admission for both transport protocols."""
import re
from fastapi import HTTPException
from media_manager.config import MediaManagerConfig
from media_manager.indexer.config import ReleasePolicyConfig
from media_manager.library import episode_numbers

QUALITY = {1: '2160p', 2: '1080p', 3: '720p', 4: '480p', 5: 'unknown'}

def language(title):
    if re.search(r'(?i)(?<![a-z0-9])(german|ger|deu|de)(?![a-z0-9])', title): return 'de'
    if re.search(r'(?i)(?<![a-z0-9])(english|eng|en)(?![a-z0-9])', title): return 'en'
    # DL/MULTI alone cannot prove that a release includes German.
    return 'unknown'

def rejection(result, config=None):
    cfg = config or MediaManagerConfig().indexers.release_policy
    if not cfg.enabled: return None
    for tag in cfg.excluded_tags:
        pattern = r'(?i)(?<![a-z0-9])'+re.escape(tag).replace(r'\ ',r'[ ._-]*')+r'(?![a-z0-9])'
        if re.search(pattern,result.title): return 'Excluded release tag: '+tag
    if QUALITY[result.quality.value] not in cfg.resolutions: return 'Resolution is not allowed by the release rules.'
    lang=language(result.title)
    if lang not in cfg.languages and not (lang=='unknown' and cfg.allow_unknown_language): return 'Release language is not allowed or cannot be identified.'
    return None

def rank(result, config=None):
    cfg=config or MediaManagerConfig().indexers.release_policy
    resolution=QUALITY[result.quality.value]
    if not cfg.enabled: return (0, -result.quality.value, result.score, int(result.usenet), result.seeders, -result.size)
    lang=language(result.title)
    return (len(cfg.languages)-cfg.languages.index(lang) if lang in cfg.languages else 0,
            len(cfg.resolutions)-cfg.resolutions.index(resolution) if resolution in cfg.resolutions else 0,
            result.score, int(result.usenet), result.seeders, -result.size)

def allowed_results(results, available_only=False):
    cfg=MediaManagerConfig().indexers.release_policy
    return sorted([r for r in results if rejection(r,cfg) is None and (not available_only or r.usenet or r.seeders>=3)],key=lambda r:rank(r,cfg),reverse=True)

def assert_allowed(result):
    reason=rejection(result)
    if reason: raise HTTPException(409,reason)

def validate_selection(result, candidates):
    assert_allowed(result)
    cfg=MediaManagerConfig().indexers.release_policy
    if cfg.enabled:
        eligible=allowed_results(candidates,available_only=True)
        if eligible and rank(result,cfg)[:2] < rank(eligible[0],cfg)[:2]:
            raise HTTPException(409,'A release with higher language/resolution priority is available. Please refresh the search results.')

def same_coverage(selected, other):
    return selected.season==other.season and all(episode_numbers([selected.title],s)==episode_numbers([other.title],s) for s in selected.season)
