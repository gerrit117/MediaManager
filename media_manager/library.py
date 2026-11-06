"""Read-only discovery for existing libraries. Never extracts or renames files."""
import hashlib
import re
from pathlib import Path

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.ts', '.m2ts', '.mpg', '.mpeg', '.webm', '.wmv'}

def video_files(directory: Path) -> list[str]:
    root = directory.resolve()
    return sorted(str(p.resolve()) for p in directory.rglob('*')
                  if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file()
                  and not p.is_symlink() and p.resolve().is_relative_to(root)
                  and not any(part.startswith('.') for part in p.relative_to(directory).parts)
                  and not re.search(r'(^|[._ -])sample([._ -]|$)', p.stem, re.I))

def catalogue_suffix(directory: Path) -> str:
    return 'CATALOGUED-' + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]

def episode_numbers(files: list[str], season: int) -> set[int]:
    result = set()
    for name in files:
        stem = Path(name).stem if Path(name).suffix.lower() in VIDEO_EXTENSIONS else Path(name).name
        # S01E01, S01E01E02 and 1x01 naming; avoid interpreting resolution/year as an episode.
        for match in re.finditer(r'(?i)(?<![a-z0-9])s(\d{1,3})(e\d{1,3}(?:[._+ -]?e\d{1,3})*)', stem):
            if int(match[1]) == season:
                result.update(int(n) for n in re.findall(r'e(\d+)', match[2], re.I))
        for match in re.finditer(r'(?i)(?<![a-z0-9])(\d{1,3})x(\d{1,3})(?!\d)', stem):
            if int(match[1]) == season:
                result.add(int(match[2]))
        for match in re.finditer(r'(?i)(?<![a-z0-9])s(\d{1,3})e(\d{1,3})-(?:e)?(\d{1,3})(?!\d)',stem):
            if int(match[1])==season and 0<=int(match[3])-int(match[2])<=100:
                result.update(range(int(match[2]),int(match[3])+1))
    return result
