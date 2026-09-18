"""Unit tests for pure analysis helpers (no ffprobe, no FFmpeg binary)."""

import analysis


def test_get_random_timestamps_basic():
    ts = analysis._get_random_timestamps(100.0, 10)
    assert len(ts) == 10
    assert ts == sorted(ts)
    assert all(0 < t < 100.0 for t in ts)


def test_get_random_timestamps_short_video():
    ts = analysis._get_random_timestamps(0.5, 5)
    assert ts == [0.25]


def test_get_random_timestamps_zero():
    assert analysis._get_random_timestamps(100.0, 0) == []


def test_chroma_subsampling():
    assert analysis._get_chroma_subsampling("yuv420p") == "4:2:0"
    assert analysis._get_chroma_subsampling("yuv422p10le") == "4:2:2"
    assert analysis._get_chroma_subsampling("yuv444p") == "4:4:4"
    assert analysis._get_chroma_subsampling("gray") == "Grayscale"
    assert analysis._get_chroma_subsampling("") == "N/A"
    assert analysis._get_chroma_subsampling(None) == "N/A"


def test_audio_bit_depth():
    assert analysis._get_audio_bit_depth("s16") == "16-bit"
    assert analysis._get_audio_bit_depth("s32") == "32-bit"
    assert analysis._get_audio_bit_depth("fltp") == "32-bit float"
    assert analysis._get_audio_bit_depth("") == "N/A"


def test_video_bit_depth():
    assert analysis._get_video_bit_depth({"bits_per_raw_sample": "10"}) == 10
    assert analysis._get_video_bit_depth({"pix_fmt": "yuv420p10le"}) == 10
    assert analysis._get_video_bit_depth({"pix_fmt": "yuv420p"}) == 8
    assert analysis._get_video_bit_depth({}) == 8


def _info(pixels_w=1920, pixels_h=1080, fps=24.0, bitrate=8_000_000):
    return {"width": pixels_w, "height": pixels_h, "frame_rate": fps, "bit_rate": bitrate}


def test_source_complexity_clean():
    # Low bits-per-pixel -> clean.
    assert analysis.analyze_source_complexity(_info(bitrate=1_000_000)) == "clean"


def test_source_complexity_film():
    # Very high bits-per-pixel -> film/grain.
    assert analysis.analyze_source_complexity(_info(bitrate=60_000_000)) == "film"


def test_source_complexity_modern():
    assert analysis.analyze_source_complexity(_info(bitrate=8_000_000)) == "modern"


def test_source_complexity_missing_data_defaults_modern():
    assert analysis.analyze_source_complexity({}) == "modern"


def test_source_details_text():
    info = {
        "video_stream": {
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "color_transfer": "bt709",
        },
        "audio_stream": {
            "codec_name": "aac",
            "channels": 2,
            "sample_rate": "48000",
            "channel_layout": "stereo",
        },
    }
    text = analysis.get_source_details_text(info)
    assert "H264" in text
    assert "SDR" in text
    assert "AAC" in text
    assert analysis.get_source_details_text({}) == "No video loaded."
    hdr = {"video_stream": {"codec_name": "hevc", "pix_fmt": "yuv420p10le",
                            "color_transfer": "smpte2084"}, "audio_stream": None}
    assert "HDR" in analysis.get_source_details_text(hdr)
    no_audio = {"video_stream": {"codec_name": "h264", "pix_fmt": "yuv420p",
                                 "color_transfer": ""}, "audio_stream": None}
    assert "No Audio" in analysis.get_source_details_text(no_audio)
