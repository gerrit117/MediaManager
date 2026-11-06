from pydantic_settings import BaseSettings
from pydantic import model_validator


class ProwlarrConfig(BaseSettings):
    enabled: bool = False
    api_key: str = ""
    url: str = "http://localhost:9696"
    timeout_seconds: int = 60


class JackettConfig(BaseSettings):
    enabled: bool = False
    api_key: str = ""
    url: str = "http://localhost:9696"
    indexers: list[str] = ["all"]
    timeout_seconds: int = 60


class ScoringRule(BaseSettings):
    name: str
    score_modifier: int = 0
    negate: bool = False


class TitleScoringRule(ScoringRule):
    keywords: list[str]


class IndexerFlagScoringRule(ScoringRule):
    flags: list[str]


class ScoringRuleSet(BaseSettings):
    name: str
    libraries: list[str] = []
    rule_names: list[str] = []


class ReleasePolicyConfig(BaseSettings):
    enabled: bool = False
    languages: list[str] = ["de", "en"]
    resolutions: list[str] = ["2160p", "1080p", "720p", "480p"]
    excluded_tags: list[str] = ["remux", "cam", "camrip", "hdcam", "telesync", "ts", "hdts", "telecine", "tc", "md", "micdubbed", "bdremux", "uhdremux"]
    allow_unknown_language: bool = False

    @model_validator(mode="after")
    def valid_preferences(self):
        if not self.languages or len(set(self.languages)) != len(self.languages) or any(x not in {"de", "en"} for x in self.languages):
            raise ValueError("Languages must be an ordered, unique list of de/en")
        if not self.resolutions or len(set(self.resolutions)) != len(self.resolutions) or any(x not in {"2160p", "1080p", "720p", "480p"} for x in self.resolutions):
            raise ValueError("Resolutions must be an ordered, unique list of 2160p/1080p/720p/480p")
        return self


class IndexerConfig(BaseSettings):
    release_policy: ReleasePolicyConfig = ReleasePolicyConfig()
    prowlarr: ProwlarrConfig = ProwlarrConfig()
    jackett: JackettConfig = JackettConfig()
    title_scoring_rules: list[TitleScoringRule] = []
    indexer_flag_scoring_rules: list[IndexerFlagScoringRule] = []
    scoring_rule_sets: list[ScoringRuleSet] = []
