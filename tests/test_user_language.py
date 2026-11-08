import pytest
from pydantic import ValidationError
from media_manager.auth.schemas import UserUpdate

@pytest.mark.parametrize("language", ["de", "en", None])
def test_optional_profile_language(language):
    assert UserUpdate(preferred_language=language).model_dump(exclude_unset=True)=={"preferred_language":language}

@pytest.mark.parametrize("language", ["fr", "de-DE", "DE", "", 1, {"de":True}])
def test_unsupported_profile_language(language):
    with pytest.raises(ValidationError):UserUpdate(preferred_language=language)

def test_unrelated_account_edits_leave_language_untouched():
    assert "preferred_language" not in UserUpdate().model_dump(exclude_unset=True)
