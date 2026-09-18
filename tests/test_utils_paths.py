"""Unit tests for pure utility helpers (no FFmpeg, no GUI)."""

import utils


def test_sanitize_removes_illegal_chars():
    # Illegal chars become "_" then collapse to spaces (allow_spaces=True).
    assert utils.sanitize_filename_component('a<b>c:d"e/f\\g|h?i*j') == "a b c d e f g h i j"
    assert utils.sanitize_filename_component("a<b>c", allow_spaces=False) == "a_b_c"
    assert utils.sanitize_filename_component("") == "Untitled"
    assert utils.sanitize_filename_component(None) == "Untitled"
    assert utils.sanitize_filename_component("   ") == "Untitled"


def test_sanitize_collapses_whitespace():
    assert utils.sanitize_filename_component("My   Movie___2024") == "My Movie 2024"


def test_format_eta():
    assert utils._format_eta(0) == "00:00:00"
    assert utils._format_eta(3661) == "01:01:01"
    assert utils._format_eta(-1) == "--:--:--"
    assert utils._format_eta(None) == "--:--:--"
    assert utils._format_eta("bad") == "--:--:--"


def test_parse_time_to_seconds():
    assert utils._parse_time_to_seconds("01:02:03.5") == 3723.5
    assert utils._parse_time_to_seconds("90") == 90.0
    assert utils._parse_time_to_seconds(None) == 0.0
    assert utils._parse_time_to_seconds("bad") == 0.0


def test_dict_to_cmd_list():
    assert utils.dict_to_cmd_list({"preset": "slow", "level": "4.2"}) == [
        "-preset",
        "slow",
        "-level",
        "4.2",
    ]


def test_get_audio_bitrate_from_options():
    assert utils.get_audio_bitrate_from_options("-b:a 192k", 128) == 192
    assert utils.get_audio_bitrate_from_options("-vbr 5", 128) == 256
    assert utils.get_audio_bitrate_from_options("-vbr 4", 128) == 192
    assert utils.get_audio_bitrate_from_options("", 128) == 128
    assert utils.get_audio_bitrate_from_options(None, 128) == 128


def test_get_resolution_name():
    assert utils.get_resolution_name(3840, 2160) == "UHD"
    assert utils.get_resolution_name(1920, 1080) == "FHD"
    assert utils.get_resolution_name(1280, 720) == "HD"
    assert utils.get_resolution_name(640, 480) == "480p"
    assert utils.get_resolution_name(0, 0) == ""


def test_parse_filename_for_metadata():
    meta = utils.parse_filename_for_metadata("My.Movie.2024.1080p.BluRay.x264.mkv")
    assert meta["year"] == "2024"
    assert "My Movie" in meta["title"]
    meta2 = utils.parse_filename_for_metadata("")
    assert meta2 == {"title": "", "year": ""}


def test_escape_ffmpeg_path_for_filter():
    escaped = utils.escape_ffmpeg_path_for_filter("C:\\temp\\vmaf log.json")
    assert "\\\\" in escaped  # backslashes escaped on Windows
    assert utils.escape_ffmpeg_path_for_filter(None) == ""
    assert utils.escape_ffmpeg_path_for_filter(123) == ""


def test_prepare_long_running_cmd_passthrough():
    # -nostdin is intentionally not injected (bundled FFmpeg doesn't support it).
    cmd = utils._prepare_long_running_cmd(["ffmpeg", "-y", "-i", "in.mp4"])
    assert cmd == ["ffmpeg", "-y", "-i", "in.mp4"]
    assert cmd is not None and cmd[1] != "-nostdin"
    assert utils._prepare_long_running_cmd(["git", "status"]) == ["git", "status"]
    assert utils._prepare_long_running_cmd([]) == []
