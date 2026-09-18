"""Unit tests for input validation and security hardening."""

import config
import validators


def test_validate_year():
    ok, err = validators.validate_year("2024")
    assert ok == "2024" and err is None
    _, err = validators.validate_year("24")
    assert err is not None
    _, err = validators.validate_year("abcd")
    assert err is not None
    _, err = validators.validate_year("1700")
    assert err is not None
    _, err = validators.validate_year("")
    assert err is not None


def test_validate_title():
    ok, err = validators.validate_title("My Movie")
    assert ok == "My Movie" and err is None
    _, err = validators.validate_title("")
    assert err is not None
    _, err = validators.validate_title("   ")
    assert err is not None
    long_title = "x" * 500
    ok, err = validators.validate_title(long_title)
    assert len(ok) == validators.MAX_TEXT_LEN and err is not None


def test_validate_crop_string():
    ok, err = validators.validate_crop_string("1920:800:0:140")
    assert ok == "1920:800:0:140" and err is None
    ok, err = validators.validate_crop_string("crop=1920:800:0:140")
    assert ok == "1920:800:0:140" and err is None
    ok, err = validators.validate_crop_string("")
    assert ok == "" and err is None
    _, err = validators.validate_crop_string("1920x800")
    assert err is not None
    _, err = validators.validate_crop_string("0:800:0:0")
    assert err is not None
    _, err = validators.validate_crop_string("1921:800:0:0")  # odd width
    assert err is not None
    _, err = validators.validate_crop_string("99999:800:0:0")
    assert err is not None


def test_validate_target_mb():
    ok, err = validators.validate_target_mb("500")
    assert ok == 500 and err is None
    ok, err = validators.validate_target_mb("0")
    assert err is not None
    ok, err = validators.validate_target_mb("-5")
    assert err is not None
    ok, err = validators.validate_target_mb("abc")
    assert err is not None
    ok, err = validators.validate_target_mb("99999999")
    assert err is not None


def test_validate_metadata_dict():
    clean, errors = validators.validate_metadata_dict(
        {"title": "Film", "artist": "", "year": "2024", "syndicate": ""}
    )
    assert not errors
    assert clean["title"] == "Film"
    _, errors = validators.validate_metadata_dict(
        {"title": "", "artist": "", "year": "xx", "syndicate": ""}
    )
    assert "title" in errors and "year" in errors


def test_validate_metadata_key():
    assert validators.validate_metadata_key("title")
    assert validators.validate_metadata_key("creation_time")
    assert not validators.validate_metadata_key("title; rm -rf")
    assert not validators.validate_metadata_key("")
    assert not validators.validate_metadata_key("0abc")


def test_validate_input_video_path(tmp_path):
    good = tmp_path / "clip.mp4"
    good.write_bytes(b"\x00" * 16)
    ok, err = validators.validate_input_video_path(str(good))
    assert err is None and ok == str(good)
    _, err = validators.validate_input_video_path(str(tmp_path / "missing.mp4"))
    assert err is not None
    bad_ext = tmp_path / "clip.txt"
    bad_ext.write_text("x")
    _, err = validators.validate_input_video_path(str(bad_ext))
    assert err is not None
    _, err = validators.validate_input_video_path("relative\\clip.mp4")
    assert err is not None


def test_config_validate_presets_passes():
    config.validate_presets()  # raises on any schema violation
