"""Contract tests for encoding presets.

These tests enforce the invariants the custom FFmpeg build relies on:
every preset must use only bundled codecs, must carry a description for
the hover tooltip, and must declare rate-control parameters consistent
with its mode. If a preset is added or changed, these tests fail first -
before a broken build ships.
"""

import config


def _all_presets():
    combined = {}
    for source in (
        config.STANDARD_PRESETS,
        config.FAST_PRESETS,
        config.WORKFLOW_PRESETS,
    ):
        for pid, preset in source.items():
            assert pid not in combined, f"Duplicate preset id: {pid}"
            combined[pid] = preset
    return combined


def test_app_is_rebranded():
    assert config.APP_NAME == "Pink Robin Encoder"
    assert "Khodabandeh" not in config.APP_NAME
    assert "BKVideoEncoder" not in config.APP_NAME.replace(" ", "")


def test_audio_codec_is_fixed_libfdk_aac():
    assert config.AUDIO_CODEC == "libfdk_aac"


def test_expected_preset_ids():
    assert set(config.STANDARD_PRESETS) == {"THE_CAPO", "THE_SOLDIER", "THE_GHOST"}
    assert set(config.FAST_PRESETS) == {"THE_HITMAN", "THE_ROCKET"}
    assert set(config.WORKFLOW_PRESETS) == {"THE_HEIST", "THE_JOB"}


def test_every_preset_has_description():
    for pid, preset in _all_presets().items():
        desc = preset.get("description", "")
        assert isinstance(desc, str) and len(desc) >= 20, (
            f"Preset {pid} needs a description (>=20 chars) for the hover tooltip"
        )


def test_video_codecs_are_only_x264_x265():
    for pid, preset in _all_presets().items():
        assert preset["video_codec"] in ("libx264", "libx265"), pid


def test_audio_codecs_are_only_libfdk_aac():
    for pid, preset in _all_presets().items():
        assert preset["audio_codec"] == "libfdk_aac", pid


def test_rate_control_modes_are_known():
    for pid, preset in _all_presets().items():
        assert preset["rate_control_mode"] in ("crf", "2pass_abr"), pid
        if preset["rate_control_mode"] == "crf":
            assert "crf_levels" in preset, pid
            assert set(preset["crf_levels"]) == set(config.Quality.LEVELS), pid
        else:
            assert "video_kbps_levels" in preset or pid == "THE_JOB", pid


def test_containers_are_mp4():
    for pid, preset in _all_presets().items():
        assert preset["container"] == ".mp4", pid


def test_pix_fmt_matches_codec():
    for pid, preset in _all_presets().items():
        if preset["video_codec"] == "libx264":
            assert preset.get("pix_fmt_8bit") == "yuv420p", pid
        else:
            assert preset.get("pix_fmt_10bit") == "yuv420p10le", pid


def test_resolutions_are_known():
    for pid, preset in _all_presets().items():
        res = preset.get("target_resolution_name")
        if res is not None:
            assert res in config.RESOLUTIONS, pid
        override = preset.get("target_w_override", 0)
        assert isinstance(override, int) and override >= 0, pid


def test_quality_levels_sane():
    assert config.Quality.LEVELS == ["Lean", "Standard", "Prime Cut"]
    assert config.Quality.DEFAULT_LEVEL == "Standard"
    assert config.DEFAULT_SOURCE_MATERIAL in config.SOURCE_MATERIAL_OPTIONS
