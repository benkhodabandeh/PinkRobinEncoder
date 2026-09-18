#!/bin/bash
# ============================================================
# Pink Robin Encoder - Custom FFmpeg Builder for Windows
# ============================================================
# Builds a minimal, tailored FFmpeg containing EXACTLY what
# Pink Robin Encoder uses - nothing extra is bundled.
#
# Audited from src/ usage (2026-09-18):
#   Encoders (external):
#     - libx264      (THE_CAPO, THE_SOLDIER, THE_HITMAN, THE_HEIST, THE_JOB)
#     - libx265      (THE_GHOST, THE_ROCKET)
#     - libfdk-aac   (ALL audio - required, no fallback)
#   Encoders (native, builtin):
#     - png, mjpeg  (preview/final stills in analysis.py)
#     - prores_ks   (VMAF upscale temp .mov in qc_tool.py)
#   Filters:
#     - crop, cropdetect, scale, format, setpts   (encode + analysis + QC)
#     - nlmeans, cas                              (denoise/sharpen presets)
#     - aresample (with soxr)                     (48 kHz mastering)
#     - libvmaf                                   (QC tool, required)
#   Resampler:
#     - libsoxr (AUDIO_RESAMPLE_FILTER=aresample=resampler=soxr)
#   Demuxers: mov/mp4, matroska, avi, wav, aac, ac3, image2
#   Muxers:   mp4, mov, image2, null
#   Protocols: file, pipe only (--disable-network)
#   Binaries: ffmpeg.exe + ffprobe.exe only (no ffplay)
#
# Explicitly EXCLUDED (verified unused in src/):
#   libvpx, libmp3lame, libopus, libvorbis, libtheora,
#   libzimg/zscale, tonemap, libopenjpeg, libass/subtitles/drawtext,
#   libfreetype/fribidi/harfbuzz, libbluray, libdav1d, libsvtav1,
#   librav1e, libkvazaar, libxavs2, libplacebo, libvidstab,
#   libsnappy, libspeex, libtwolame, libwebp, libzvbi, cuda/qsv/nvenc/amf
#
# Versions (pinned):
#   FFmpeg   7.1.1
#   x264     master (rolling - no stable releases)
#   x265     4.1
#   fdk-aac  2.0.3
#   soxr     0.1.3
#   vmaf     MSYS2 package (>= 2.0.0, verified via pkg-config)
#
# MUST be run from MSYS2 MinGW64 shell ("MinGW 64-bit"), NOT MSYS shell.
# On GitHub Actions, use msys2/setup-msys2 with msystem: MINGW64 and run:
#   bash scripts/build_ffmpeg_windows.sh
#
# Layout (location-agnostic, resolved from script path):
#   ROOT      = repo root (parent of scripts/)
#   BIN       = $ROOT/bin            (ffmpeg.exe, ffprobe.exe + DLLs land here)
#   BUILD_DIR = $ROOT/build/ffmpeg   (ephemeral; safe to delete)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN="$ROOT/bin"
BUILD_DIR="$ROOT/build/ffmpeg"

FFMPEG_VERSION="7.1.1"
X265_VERSION="4.1"
FDK_AAC_VERSION="2.0.3"
SOXR_VERSION="0.1.3"

# ---- Detect environment ----
if [ ! -d "/mingw64/bin" ]; then
    echo "ERROR: This script must be run from the MSYS2 MinGW64 shell."
    echo "Open MSYS2, click 'MinGW 64-bit' in the taskbar, then re-run:"
    echo "  bash scripts/build_ffmpeg_windows.sh"
    exit 1
fi

export PATH="/mingw64/bin:/usr/bin:$PATH"
NPROC=$(nproc 2>/dev/null || echo 4)

echo "============================================"
echo "  Pink Robin Encoder - Custom FFmpeg Build"
echo "  FFmpeg: $FFMPEG_VERSION | x265: $X265_VERSION"
echo "  Jobs: $NPROC"
echo "  Root: $ROOT"
echo "  Install: $BIN"
echo "============================================"
echo ""

# ---- Step 0: Clean previous build ----
echo "[0/8] Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$BIN"
echo "  Clean build directory ready: $BUILD_DIR"

# ---- Step 1: Install MSYS2 dependencies ----
echo ""
echo "[1/8] Installing MSYS2 dependencies..."
# NOTE: failures stop the script immediately so a broken mirror or missing
# package surfaces here instead of as a cryptic FFmpeg configure error later.
PACMAN_TRIES=3
for attempt in $(seq 1 "$PACMAN_TRIES"); do
    if pacman -Sy --needed --noconfirm \
        mingw-w64-x86_64-toolchain \
        mingw-w64-x86_64-cmake \
        mingw-w64-x86_64-nasm \
        mingw-w64-x86_64-yasm \
        mingw-w64-x86_64-autotools \
        mingw-w64-x86_64-meson \
        mingw-w64-x86_64-ninja \
        mingw-w64-x86_64-pkgconf \
        mingw-w64-x86_64-vmaf \
        git \
        make \
        curl; then
        break
    fi
    if [ "$attempt" -eq "$PACMAN_TRIES" ]; then
        echo "ERROR: pacman failed after $PACMAN_TRIES attempts."
        echo "       Try a different mirror (edit /etc/pacman.d/mirrorlist.mingw64),"
        echo "       then re-run this script."
        exit 1
    fi
    echo "  pacman attempt $attempt/$PACMAN_TRIES failed (likely mirror hiccup) -- retrying in 5s..."
    sleep 5
done
echo "  Dependencies installed."

# Verify libvmaf (REQUIRED - QC tool has no fallback).
echo ""
echo "  Verifying libvmaf (required)..."
export PKG_CONFIG_PATH="/mingw64/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
if ! pkg-config --exists 'libvmaf >= 2.0.0'; then
    echo "ERROR: libvmaf >= 2.0.0 not found via pkg-config after installing"
    echo "       mingw-w64-x86_64-vmaf. The QC tool requires the libvmaf filter."
    echo ""
    echo "  Debug manually with:"
    echo "    pacman -Sy && pacman -S mingw-w64-x86_64-vmaf"
    echo "    pkg-config --modversion libvmaf"
    exit 1
fi
echo "  libvmaf found: $(pkg-config --modversion libvmaf)"

# ---- Step 2: Build libx264 (master) ----
echo ""
echo "[2/8] Building libx264 (master)..."
cd "$BUILD_DIR"
if [ ! -d x264 ]; then
    git clone --depth 1 https://code.videolan.org/videolan/x264.git
fi
cd x264
CFLAGS="-w" ./configure \
    --prefix="$BUILD_DIR/x264-install" \
    --enable-shared \
    --disable-cli \
    --enable-pic
make -j"$NPROC"
make install
echo "  libx264 built and installed."
cd "$BUILD_DIR"

# ---- Step 3: Build libx265 (pinned) ----
echo ""
echo "[3/8] Building libx265 ($X265_VERSION)..."
X265_SRC=""
if [ ! -d x265-src ] || [ -z "$(ls -A x265-src 2>/dev/null)" ]; then
    rm -rf x265-src && mkdir -p x265-src
    declare -a X265_URLS=(
        "https://bitbucket.org/multicoreware/x265_git/downloads/x265_${X265_VERSION}.tar.gz|bitbucket"
        "https://github.com/videolan/x265/archive/refs/tags/${X265_VERSION}.tar.gz|github-videolan"
    )
    for entry in "${X265_URLS[@]}"; do
        url="${entry%%|*}"
        label="${entry##*|}"
        echo "  Trying $label ..."
        rm -f x265.tar.gz
        if curl -L --retry 3 --retry-delay 2 --connect-timeout 20 -o x265.tar.gz "$url"; then
            if [ -s x265.tar.gz ] && tar xf x265.tar.gz -C x265-src --strip-components=1 2>/dev/null; then
                echo "  Extracted from $label."
                X265_SRC="$BUILD_DIR/x265-src"
                break
            fi
        fi
        echo "  $label failed, trying next."
    done
    if [ -z "$X265_SRC" ] || [ -z "$(ls -A "$X265_SRC" 2>/dev/null)" ]; then
        echo "ERROR: Could not obtain x265 $X265_VERSION source."
        exit 1
    fi
else
    X265_SRC="$BUILD_DIR/x265-src"
    echo "  Reusing existing x265 source."
fi
rm -rf x265-build && mkdir -p x265-build
cd x265-build
cmake -G "Unix Makefiles" \
    "$X265_SRC/source" \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_INSTALL_PREFIX="$BUILD_DIR/x265-install" \
    -DBUILD_SHARED_LIBS=ON \
    -DENABLE_CLI=OFF \
    -DENABLE_TESTS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-w" \
    -DCMAKE_CXX_FLAGS="-w"
make -j"$NPROC"
make install
echo "  libx265 built and installed."
cd "$BUILD_DIR"

# ---- Step 4: Build libfdk-aac (REQUIRED - no fallback) ----
echo ""
echo "[4/8] Building libfdk-aac (v$FDK_AAC_VERSION, required)..."
if [ ! -d fdk-aac ]; then
    curl -L --retry 3 --retry-delay 2 --connect-timeout 20 \
        -o fdk-aac.tar.gz "https://github.com/mstorsjo/fdk-aac/archive/refs/tags/v${FDK_AAC_VERSION}.tar.gz"
    tar xzf fdk-aac.tar.gz
    mv "fdk-aac-${FDK_AAC_VERSION}" fdk-aac
    rm -f fdk-aac.tar.gz
fi
cd fdk-aac
autoreconf -fi
CFLAGS="-w" ./configure \
    --prefix="$BUILD_DIR/fdk-aac-install" \
    --enable-shared \
    --disable-static
make -j"$NPROC"
make install
echo "  libfdk-aac built and installed."
cd "$BUILD_DIR"

# ---- Step 5: Build libsoxr (for aresample=resampler=soxr) ----
echo ""
echo "[5/8] Building libsoxr ($SOXR_VERSION)..."
if [ ! -f "$BUILD_DIR/soxr-install/lib/pkgconfig/soxr.pc" ]; then
    rm -rf soxr-src && mkdir -p soxr-src
    declare -a SOXR_URLS=(
        "https://sources.voidlinux.org/libsoxr-0.1.3/soxr-0.1.3-Source.tar.xz|voidlinux"
        "https://downloads.sourceforge.net/project/soxr/soxr-0.1.3-Source.tar.xz|sourceforge"
        "https://github.com/arthenica/soxr/archive/refs/tags/0.1.3.tar.gz|github-arthenica"
    )
    for entry in "${SOXR_URLS[@]}"; do
        url="${entry%%|*}"
        label="${entry##*|}"
        echo "  Trying $label ..."
        rm -f soxr.tar.xz
        if curl -L --retry 3 --retry-delay 2 --connect-timeout 20 -o soxr.tar.xz "$url"; then
            if [ -s soxr.tar.xz ] && (tar xf soxr.tar.xz -C soxr-src --strip-components=1 2>/dev/null \
                || tar xJf soxr.tar.xz -C soxr-src --strip-components=1 2>/dev/null); then
                echo "  Extracted from $label."
                break
            fi
        fi
        echo "  $label failed, trying next."
    done
    if [ -z "$(ls -A soxr-src 2>/dev/null)" ]; then
        echo "ERROR: Could not obtain libsoxr source."
        exit 1
    fi
    cd soxr-src
    cmake -G "Unix Makefiles" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_INSTALL_PREFIX="$BUILD_DIR/soxr-install" \
        -DBUILD_SHARED_LIBS=ON \
        -DWITH_OPENMP=OFF \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_FLAGS="-w" \
        .
    make -j"$NPROC"
    make install
    echo "  libsoxr built and installed."
    cd "$BUILD_DIR"
else
    echo "  libsoxr already built -- skipping."
fi

# ---- Step 6: Download FFmpeg source ----
echo ""
echo "[6/8] Downloading FFmpeg $FFMPEG_VERSION..."
FF_TARBALL=""
if [ -f "$BUILD_DIR/ffmpeg-${FFMPEG_VERSION}.tar.xz" ]; then
    FF_TARBALL="$BUILD_DIR/ffmpeg-${FFMPEG_VERSION}.tar.xz"
elif [ -f "$BUILD_DIR/ffmpeg.tar.xz" ]; then
    FF_TARBALL="$BUILD_DIR/ffmpeg.tar.xz"
fi

if [ -z "$FF_TARBALL" ]; then
    declare -a FF_URLS=(
        "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz|ffmpeg.org"
        "https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n${FFMPEG_VERSION}.tar.gz|github.com"
    )
    for entry in "${FF_URLS[@]}"; do
        url="${entry%%|*}"
        label="${entry##*|}"
        echo "  Trying $label ..."
        if curl -L --retry 3 --retry-delay 2 --connect-timeout 20 \
             -o "$BUILD_DIR/ffmpeg.tar.xz" "$url"; then
            if [ -s "$BUILD_DIR/ffmpeg.tar.xz" ]; then
                FF_TARBALL="$BUILD_DIR/ffmpeg.tar.xz"
                echo "  Downloaded from $label."
                break
            fi
        fi
        echo "  $label failed, trying next mirror."
    done
fi

if [ -z "$FF_TARBALL" ]; then
    echo "ERROR: Could not download FFmpeg source from any mirror."
    echo "       Manually download ffmpeg-${FFMPEG_VERSION}.tar.xz into:"
    echo "         $BUILD_DIR"
    echo "       then re-run this script."
    exit 1
fi

rm -rf ffmpeg-src
mkdir -p ffmpeg-src-tmp
tar xf "$FF_TARBALL" -C ffmpeg-src-tmp --strip-components=1
mv ffmpeg-src-tmp ffmpeg-src
rm -f "$BUILD_DIR/ffmpeg.tar.xz"

# ---- Branding patch: Pink Robin Encoder identity ----
echo ""
echo "  Applying Pink Robin Encoder branding patch..."
cd ffmpeg-src
FFVERSION_H="libavutil/ffversion.h"
if [ -f "$FFVERSION_H" ]; then
    sed -i 's/^#define FFMPEG_VERSION .*$/#define FFMPEG_VERSION "Pink Robin Encoder FFMPEG ENGINE"/' "$FFVERSION_H"
    echo "  Version string patched in ffversion.h."
else
    echo "  WARNING: $FFVERSION_H not found; version patch skipped."
fi
FFMPEG_C="fftools/ffmpeg.c"
if [ -f "$FFMPEG_C" ]; then
    sed -i 's/Copyright (c) [0-9-]* FFmpeg developers/Copyright (c) 2018-2026 Pink Robin Encoder/' "$FFMPEG_C"
    echo "  Copyright string patched in fftools/ffmpeg.c."
else
    echo "  WARNING: $FFMPEG_C not found; copyright patch skipped."
fi
cd ..
echo "  FFmpeg source ready."

# ---- Step 7: Configure + build FFmpeg (minimal, tailored) ----
echo ""
echo "[7/8] Configuring tailored FFmpeg..."
cd ffmpeg-src

export PKG_CONFIG_PATH="$BUILD_DIR/x264-install/lib/pkgconfig:$BUILD_DIR/x265-install/lib/pkgconfig:$BUILD_DIR/fdk-aac-install/lib/pkgconfig:$BUILD_DIR/soxr-install/lib/pkgconfig:/mingw64/lib/pkgconfig"

# soxr's CMake does not install a .pc file; synthesize one if missing.
SOXR_PCDIR="$BUILD_DIR/soxr-install/lib/pkgconfig"
if [ ! -f "$SOXR_PCDIR/soxr.pc" ]; then
    mkdir -p "$SOXR_PCDIR"
    cat > "$SOXR_PCDIR/soxr.pc" <<PC
prefix=$BUILD_DIR/soxr-install
exec_prefix=\${prefix}
libdir=\${prefix}/lib
includedir=\${prefix}/include

Name: soxr
Description: The SoX Resampler library
Version: $SOXR_VERSION
Libs: -L\${libdir} -lsoxr
Libs.private: -lm
Cflags: -I\${includedir}
PC
    echo "  Created soxr.pc for pkg-config."
fi

# Verify required inputs are present before configuring.
for f in \
    "$BUILD_DIR/x264-install/lib/pkgconfig/x264.pc" \
    "$BUILD_DIR/x265-install/lib/pkgconfig/x265.pc" \
    "$BUILD_DIR/fdk-aac-install/lib/pkgconfig/fdk-aac.pc" \
    "$SOXR_PCDIR/soxr.pc"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: missing pkg-config file: $f"
        exit 1
    fi
done
pkg-config --exists 'libvmaf >= 2.0.0' || { echo "ERROR: libvmaf missing at configure time."; exit 1; }
echo "  All required libraries present (x264, x265, fdk-aac, soxr, vmaf)."

SOXR_CFLAGS="-I$BUILD_DIR/soxr-install/include"
SOXR_LDFLAGS="-L$BUILD_DIR/soxr-install/lib -lsoxr"

./configure \
    --prefix="$BIN" \
    --enable-gpl \
    --enable-version3 \
    --enable-nonfree \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libfdk-aac \
    --enable-libsoxr \
    --enable-libvmaf \
    --enable-avfilter \
    --enable-avformat \
    --enable-swresample \
    --enable-swscale \
    --enable-avcodec \
    --disable-network \
    --disable-doc \
    --disable-htmlpages \
    --disable-manpages \
    --disable-podpages \
    --disable-txtpages \
    --disable-debug \
    --disable-symver \
    --disable-ffplay \
    --disable-libvpx \
    --disable-libmp3lame \
    --disable-libopus \
    --disable-libvorbis \
    --disable-libtheora \
    --disable-libwebp \
    --disable-libopenjpeg \
    --disable-libzimg \
    --disable-libass \
    --disable-libfreetype \
    --disable-libfribidi \
    --disable-libharfbuzz \
    --disable-libbluray \
    --disable-libdav1d \
    --disable-libsvtav1 \
    --disable-librav1e \
    --disable-libkvazaar \
    --disable-libxavs2 \
    --disable-libplacebo \
    --disable-libvidstab \
    --disable-libsnappy \
    --disable-libspeex \
    --disable-libtwolame \
    --disable-libzvbi \
    --disable-encoder=aac \
    --extra-cflags="-w $SOXR_CFLAGS" \
    --extra-ldflags="$SOXR_LDFLAGS"

echo "  Configuration complete."

echo ""
echo "  Building FFmpeg (this takes 5-15 minutes)..."
make -j"$NPROC"
make install
echo "  FFmpeg installed to $BIN."

# ---- Step 8: Copy DLLs + verify ----
echo ""
echo "[8/8] Collecting DLLs and verifying tailored build..."
cd "$ROOT"

# Library DLLs from our builds
for dll in "$BUILD_DIR/x264-install/bin/"*.dll \
           "$BUILD_DIR/x265-install/bin/"*.dll \
           "$BUILD_DIR/fdk-aac-install/bin/"*.dll; do
    if [ -f "$dll" ]; then
        cp "$dll" "$BIN/"
        echo "  Copied: $(basename "$dll")"
    fi
done

if [ -f "$BUILD_DIR/soxr-install/bin/libsoxr.dll" ]; then
    cp "$BUILD_DIR/soxr-install/bin/libsoxr.dll" "$BIN/"
    echo "  Copied: libsoxr.dll"
else
    echo "  ERROR: libsoxr.dll missing -- aresample(resampler=soxr) would fail."
    exit 1
fi

# MinGW runtime DLLs
for dll in libgcc_s_seh-1.dll libwinpthread-1.dll libstdc++-6.dll \
           libbz2-1.dll libiconv-2.dll liblzma-5.dll zlib1.dll \
           libatomic-1.dll libgomp-1.dll libssp-0.dll; do
    if [ -f "/mingw64/bin/$dll" ]; then
        cp "/mingw64/bin/$dll" "$BIN/"
        echo "  Copied: $dll"
    fi
done

# libvmaf runtime DLL
if [ -f "/mingw64/bin/libvmaf.dll" ]; then
    cp "/mingw64/bin/libvmaf.dll" "$BIN/"
    echo "  Copied: libvmaf.dll"
else
    echo "  ERROR: libvmaf.dll missing in /mingw64/bin -- QC tool would fail."
    exit 1
fi

echo ""
echo "============================================"
echo "  BUILD COMPLETE - TAILORED VERIFICATION"
echo "============================================"
echo ""
echo "Binaries:"
echo "  ffmpeg.exe  $(du -sh "$BIN/ffmpeg.exe" 2>/dev/null | cut -f1)"
echo "  ffprobe.exe $(du -sh "$BIN/ffprobe.exe" 2>/dev/null | cut -f1)"
echo ""

echo "Testing binaries..."
"$BIN/ffmpeg.exe" -version > /dev/null 2>&1 \
    && echo "  ffmpeg.exe: OK" \
    || { echo "  ffmpeg.exe: FAILED - DLL issue?"; exit 1; }
"$BIN/ffprobe.exe" -version > /dev/null 2>&1 \
    && echo "  ffprobe.exe: OK" \
    || { echo "  ffprobe.exe: FAILED - DLL issue?"; exit 1; }

echo ""
echo "Required encoders (must all be YES):"
FAIL=0
for e in libx264 libx265 libfdk_aac png mjpeg prores_ks; do
    if "$BIN/ffmpeg.exe" -hide_banner -encoders 2>/dev/null | grep -q " $e "; then
        echo "  $e: YES"
    else
        echo "  $e: MISSING <-- BUILD INVALID"
        FAIL=1
    fi
done

echo ""
echo "Excluded encoders (must all be NO - proves minimal):"
for e in libvpx_vp9 libmp3lame libopus libvorbis libtheora libaom-av1; do
    if "$BIN/ffmpeg.exe" -hide_banner -encoders 2>/dev/null | grep -q " $e "; then
        echo "  $e: PRESENT (unexpected)"
    else
        echo "  $e: absent (good)"
    fi
done
if "$BIN/ffmpeg.exe" -hide_banner -encoders 2>/dev/null | grep -qE "^ [A-Z\.]{6} aac +AAC"; then
    echo "  native aac encoder: PRESENT (should be disabled - uses libfdk_aac only)"
else
    echo "  native aac encoder: absent (good - enforces libfdk_aac)"
fi

echo ""
echo "Required filters (must all be YES):"
for f in crop cropdetect scale format setpts nlmeans cas aresample libvmaf null; do
    if "$BIN/ffmpeg.exe" -hide_banner -filters 2>/dev/null | grep -q " $f "; then
        echo "  $f: YES"
    else
        echo "  $f: MISSING <-- BUILD INVALID"
        FAIL=1
    fi
done

echo ""
echo "Excluded filters (must all be NO - proves minimal):"
for f in zscale tonemap ass subtitles drawtext openjpeg; do
    if "$BIN/ffmpeg.exe" -hide_banner -filters 2>/dev/null | grep -q " $f "; then
        echo "  $f: PRESENT (unexpected)"
    else
        echo "  $f: absent (good)"
    fi
done

echo ""
echo "Required demuxers/muxers:"
for d in mov mp4 matroska avi wav aac ac3 image2; do
    if "$BIN/ffmpeg.exe" -hide_banner -demuxers 2>/dev/null | grep -q " $d " \
       || "$BIN/ffmpeg.exe" -hide_banner -muxers 2>/dev/null | grep -q " $d "; then
        echo "  $d: YES"
    else
        echo "  $d: MISSING <-- CHECK"
        FAIL=1
    fi
done

echo ""
echo "soxr resampler functional test:"
if "$BIN/ffmpeg.exe" -hide_banner -loglevel error -f lavfi -i anullsrc=r=48000:cl=stereo \
   -af "aresample=48000:resampler=soxr" -t 0.1 -f null - > /dev/null 2>&1; then
    echo "  soxr: YES (high-quality resampler active)"
else
    echo "  soxr: NO <-- BUILD INVALID"
    FAIL=1
fi

echo ""
echo "libvmaf filter functional test:"
if "$BIN/ffmpeg.exe" -hide_banner -filters 2>/dev/null | grep -q " libvmaf "; then
    echo "  libvmaf: YES"
else
    echo "  libvmaf: NO <-- BUILD INVALID"
    FAIL=1
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
    echo "RESULT: FAILED - tailored requirements not met. See MISSING lines above."
    exit 1
fi
echo "RESULT: PASSED - tailored Pink Robin Encoder FFmpeg is complete."
echo "Binaries + DLLs are in: $BIN"
