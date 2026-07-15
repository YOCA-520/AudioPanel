# -*- coding: utf-8 -*-
"""
音量反馈音模块 — 通过 MME waveOut 直推音频到指定设备

播放链 (5层冗余):
    1. MME waveOut → 指定设备 (WAV 文件)
    2. MME waveOut → 指定设备 (合成纯音)
    3. PlaySound → 默认设备 (WAV 文件)
    4. PlaySound → 默认设备 (合成纯音)
    5. winsound.Beep → 蜂鸣器

设计原因:
    Windows 没有"向指定设备播放音效"的简洁 API,
    因此从精确到模糊逐层降级, 确保至少有一种方式能发声.
"""
from __future__ import annotations

import ctypes
import struct
import math
import os
import sys
import threading
from ctypes import wintypes, byref

# ─── WAV 路径 ────────────────────────────────────────

def _get_wav_path() -> str:
    """查找通知音效 WAV 文件路径 (兼容 PyInstaller onefile)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base, "assets", "notify.wav"),
        os.path.join(os.path.dirname(sys.executable), "assets", "notify.wav"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Media", "Speech Disambiguation.wav"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

_WAV_PATH = _get_wav_path()
_WAV_RAW: bytes = b""

def _load_wav() -> None:
    global _WAV_RAW
    try:
        with open(_WAV_PATH, "rb") as f:
            data = f.read()
        if data[:4] != b"RIFF":
            return
        pos = 12
        while pos < len(data) - 8:
            ck_id = data[pos:pos+4]
            ck_size = struct.unpack_from("<I", data, pos+4)[0]
            if ck_id == b"data":
                _WAV_RAW = data
                return
            pos += 8 + ck_size
    except Exception:
        pass

_load_wav()


# ─── 合成音 ──────────────────────────────────────────

_TONE_WAV: bytes = b""

def _gen_tone() -> bytes:
    sr = 44100; freq = 880.0; dur = 0.08; amp = 0.25
    n = int(sr * dur)
    pcm = bytearray()
    for i in range(n):
        w = 0.5*(1-math.cos(2*math.pi*i/(n-1))) if n>1 else 1.0
        v = int(amp*w*32767*math.sin(2*math.pi*freq*i/sr))
        pcm += struct.pack("<h", max(-32768, min(32767, v)))
    dlen = len(pcm)
    return struct.pack("<4sI4s4sIHHIIHH4sI",
        b"RIFF",36+dlen,b"WAVE",b"fmt ",16,1,1,sr,sr*2,2,16,b"data",dlen)+bytes(pcm)


# ─── MME waveOut + CALLBACK_FUNCTION ─────────────────

class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]

class _WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_char_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", wintypes.DWORD),
    ]

winmm = ctypes.windll.winmm
WOM_DONE = 0x3BD
CALLBACK_FUNCTION = 0x00030000


def _find_waveout_id(name: str) -> int:
    """CoreAudio 设备名 → MME waveOut 设备 ID (打分制)."""
    num = winmm.waveOutGetNumDevs()
    short = name.lower()
    keywords = [w for w in short.replace("(", " ").replace(")", " ").split()
                if len(w) > 1]
    best_id, best_score = 0, 0
    for i in range(num):
        caps = (ctypes.c_byte * 84)()
        if winmm.waveOutGetDevCapsW(i, byref(caps), 84) == 0:
            mm_name = ctypes.cast(byref(caps, 8), ctypes.c_wchar_p).value
            if mm_name:
                ml = mm_name.lower()
                score = sum(1 for kw in keywords if kw in ml)
                if score > best_score:
                    best_score, best_id = score, i
    return best_id if best_score > 0 else 0


def _mme_play(device_name: str, wav_data: bytes) -> bool:
    """MME waveOut 直推 WAV 到指定设备名."""
    if not wav_data:
        return False
    try:
        # 解析 WAV 头
        tag, ch, sr, br, ba, bits = 1, 2, 44100, 176400, 4, 16
        pcm = wav_data
        pos = 12
        while pos < len(wav_data) - 8:
            ck_id = wav_data[pos:pos+4]
            ck_size = struct.unpack_from("<I", wav_data, pos+4)[0]
            if ck_id == b"fmt ":
                f = struct.unpack_from("<HHIIHH", wav_data[pos+8:pos+8+ck_size])
                tag, ch, sr, br, ba = f[0], f[1], f[2], f[3], f[4]
                bits = f[5] if ck_size >= 16 else 16
            elif ck_id == b"data":
                pcm = wav_data[pos+8:pos+8+ck_size]
                break
            pos += 8 + ck_size

        # 格式
        wf = _WAVEFORMATEX()
        wf.wFormatTag = tag; wf.nChannels = ch
        wf.nSamplesPerSec = sr; wf.wBitsPerSample = bits
        wf.nBlockAlign = ba; wf.nAvgBytesPerSec = br

        dev_id = _find_waveout_id(device_name)

        # CALLBACK_FUNCTION
        done = threading.Event()
        @ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT,
                            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        def cb(hwo, msg, inst, p1, p2):
            if msg == WOM_DONE:
                done.set()

        hwo = wintypes.HANDLE()
        if winmm.waveOutOpen(byref(hwo), dev_id, byref(wf),
                             cb, 0, CALLBACK_FUNCTION) != 0:
            return False

        buf = ctypes.create_string_buffer(pcm)
        hdr = _WAVEHDR()
        hdr.lpData = ctypes.cast(buf, ctypes.c_char_p)
        hdr.dwBufferLength = len(pcm)

        if winmm.waveOutPrepareHeader(hwo, byref(hdr), ctypes.sizeof(hdr)) != 0:
            winmm.waveOutClose(hwo); return False
        if winmm.waveOutWrite(hwo, byref(hdr), ctypes.sizeof(hdr)) != 0:
            winmm.waveOutUnprepareHeader(hwo, byref(hdr), ctypes.sizeof(hdr))
            winmm.waveOutClose(hwo); return False

        done.wait(timeout=3)
        winmm.waveOutUnprepareHeader(hwo, byref(hdr), ctypes.sizeof(hdr))
        winmm.waveOutClose(hwo)
        return True
    except Exception:
        return False


# ─── 播放入口 ────────────────────────────────────────

def play_beep(device_name: str) -> None:
    """
    冗余播放链:
      1. MME waveOut 直推指定设备 (WAV)
      2. MME waveOut 直推指定设备 (合成音)
      3. PlaySound WAV (默认设备)
      4. PlaySound 合成音 (默认设备)
      5. winsound.Beep 蜂鸣
    """
    name = str(device_name)

    def _play():
        # 1. MME + WAV
        if _WAV_RAW and _mme_play(name, _WAV_RAW):
            return

        # 2. MME + 合成音
        global _TONE_WAV
        if not _TONE_WAV:
            _TONE_WAV = _gen_tone()
        if _mme_play(name, _TONE_WAV):
            return

        # 3. PlaySound WAV
        if _WAV_RAW:
            try:
                ctypes.windll.winmm.PlaySoundW(_WAV_RAW, None, 0x0004|0x0001)
                return
            except Exception:
                pass

        # 4. PlaySound 合成音
        try:
            ctypes.windll.winmm.PlaySoundW(_TONE_WAV, None, 0x0004|0x0001)
            return
        except Exception:
            pass

        # 5. 蜂鸣
        try:
            import winsound
            winsound.Beep(880, 80)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


