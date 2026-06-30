from unittest.mock import patch, MagicMock
from src.sources.github_source import GitHubSource, _extract_username


def test_extract_username_from_url():
    assert _extract_username("https://github.com/torvalds") == "torvalds"
    assert _extract_username("https://github.com/torvalds/") == "torvalds"


def test_extract_username_bare():
    assert _extract_username("torvalds") == "torvalds"


def test_extract_username_invalid():
    assert _extract_username("not a url ???") is None
    assert _extract_username("") is None


@patch("src.sources.github_source.requests.get")
def test_happy_path(mock_get):
    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {
        "name": "Linus Torvalds",
        "bio": "Creator of Linux",
        "html_url": "https://github.com/torvalds",
        "location": "Portland, OR",
    }
    repos_resp = MagicMock(status_code=200)
    repos_resp.json.return_value = [
        {"language": "C"}, {"language": "Shell"}, {"language": None},
    ]
    mock_get.side_effect = [user_resp, repos_resp]

    parser = GitHubSource()
    records = parser.parse("https://github.com/torvalds")

    assert len(records) == 1
    assert records[0].data["full_name"] == "Linus Torvalds"
    assert records[0].data["languages"] == ["C", "Shell"]
    assert records[0].candidate_key is None


@patch("src.sources.github_source.requests.get")
def test_404_returns_empty(mock_get):
    mock_get.return_value = MagicMock(status_code=404)
    parser = GitHubSource()
    records = parser.parse("https://github.com/this-user-does-not-exist-xyz")
    assert records == []


def test_malformed_url_returns_empty():
    parser = GitHubSource()
    records = parser.parse("???not a url???")
    assert records == []