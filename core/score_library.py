"""
乐谱片段库

用于存储和管理可复用的音符/鼓点片段（乐谱片段），支持分组和名称。
"""

import json
import os
import uuid
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QStandardPaths


class ScoreLibrary:
    """乐谱片段库，负责加载/保存和基础管理"""

    def __init__(self, library_file: Optional[str] = None):
        # 默认将库文件放在与 settings.json 同一配置目录下
        if library_file is None:
            app = QApplication.instance()
            if app is not None and os.path.exists(app.applicationDirPath()):
                base_dir = app.applicationDirPath()
                library_file = os.path.join(base_dir, "score_library.json")
            else:
                config_dir = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
                os.makedirs(os.path.join(config_dir, "8bit_music_editor"), exist_ok=True)
                library_file = os.path.join(config_dir, "8bit_music_editor", "score_library.json")

        self.library_file = library_file
        self.snippets: List[Dict[str, Any]] = []
        self._load()
        # 确保内置预设存在（不会覆盖用户已有片段）
        self._ensure_builtin_presets()

    # ---- 基础持久化 ----

    def _load(self) -> None:
        if os.path.exists(self.library_file):
            try:
                with open(self.library_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.snippets = data
            except Exception:
                # 读取失败时不抛出，让库保持为空，避免影响主程序
                self.snippets = []

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.library_file), exist_ok=True)
            with open(self.library_file, "w", encoding="utf-8") as f:
                json.dump(self.snippets, f, indent=2, ensure_ascii=False)
        except Exception:
            # 保存失败不影响运行，只是不持久化
            pass

    # ---- 内置预设 ----

    def _has_builtin_with_key(self, key: str) -> bool:
        """检查是否已经存在指定 key 的内置预设（避免重复添加）"""
        for s in self.snippets:
            if s.get("builtin") and s.get("builtin_key") == key:
                return True
        return False

    def _ensure_builtin_presets(self) -> None:
        """如果用户库中没有内置预设，则追加一些常用鼓点 / 和弦模版"""
        # 小工具：按 120 BPM 将拍数转换为秒（乐谱片段内部使用秒偏移）
        def beats_to_seconds(beats: float, bpm: float = 120.0) -> float:
            return float(beats) * 60.0 / float(bpm)

        # 1. 常用鼓点：简单 4/4 基本鼓点
        if not self._has_builtin_with_key("basic_drum_4_4"):
            drums = [
                # 底鼓：每拍
                {"offset_beats": 0.0, "duration_beats": 0.25, "drum_type": "KICK", "velocity": 110},
                {"offset_beats": 1.0, "duration_beats": 0.25, "drum_type": "KICK", "velocity": 110},
                {"offset_beats": 2.0, "duration_beats": 0.25, "drum_type": "KICK", "velocity": 110},
                {"offset_beats": 3.0, "duration_beats": 0.25, "drum_type": "KICK", "velocity": 110},
                # 军鼓：第 2、4 拍
                {"offset_beats": 1.0, "duration_beats": 0.25, "drum_type": "SNARE", "velocity": 115},
                {"offset_beats": 3.0, "duration_beats": 0.25, "drum_type": "SNARE", "velocity": 115},
                # 踩镲：八分音符
                {"offset_beats": 0.0, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 90},
                {"offset_beats": 0.5, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 80},
                {"offset_beats": 1.0, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 90},
                {"offset_beats": 1.5, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 80},
                {"offset_beats": 2.0, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 90},
                {"offset_beats": 2.5, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 80},
                {"offset_beats": 3.0, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 90},
                {"offset_beats": 3.5, "duration_beats": 0.25, "drum_type": "HIHAT", "velocity": 80},
            ]
            snippet_id = self.add_snippet(
                name="基本 4/4 鼓点",
                group="预设-鼓点",
                snippet_type="drum",
                track_name="打击乐",
                data={"drums": drums},
            )
            # 标记为内置
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "basic_drum_4_4"
                    break

        # 再追加一批不同风格的鼓点模式（尽量多一些“即插即用”的节奏）
        drum_presets = [
            # 4/4：四踩+军鼓，踩镲八分音符（流行/摇滚常见）
            {
                "key": "drum_4_4_four_on_floor",
                "name": "4/4 四踩流行鼓点",
                "pattern": [
                    # Kick on all 4 beats
                    (0.0, 0.25, "KICK", 115),
                    (1.0, 0.25, "KICK", 115),
                    (2.0, 0.25, "KICK", 115),
                    (3.0, 0.25, "KICK", 115),
                    # Snare on 2 and 4
                    (1.0, 0.25, "SNARE", 120),
                    (3.0, 0.25, "SNARE", 120),
                    # Hi-hat 8th notes
                    (0.0, 0.25, "HIHAT", 90),
                    (0.5, 0.25, "HIHAT", 80),
                    (1.0, 0.25, "HIHAT", 90),
                    (1.5, 0.25, "HIHAT", 80),
                    (2.0, 0.25, "HIHAT", 90),
                    (2.5, 0.25, "HIHAT", 80),
                    (3.0, 0.25, "HIHAT", 90),
                    (3.5, 0.25, "HIHAT", 80),
                ],
            },
            # 4/4：半拍军鼓（适合抒情/慢速）
            {
                "key": "drum_4_4_half_time",
                "name": "4/4 半拍军鼓鼓点",
                "pattern": [
                    # Kick: 1 and 3
                    (0.0, 0.5, "KICK", 115),
                    (2.0, 0.5, "KICK", 110),
                    # Snare: only on beat 3 (half-time feel)
                    (2.0, 0.5, "SNARE", 120),
                    # Hi-hat: quarter notes
                    (0.0, 0.25, "HIHAT", 90),
                    (1.0, 0.25, "HIHAT", 90),
                    (2.0, 0.25, "HIHAT", 90),
                    (3.0, 0.25, "HIHAT", 90),
                ],
            },
            # 4/4：前半空，后半连击（适合作为过门）
            {
                "key": "drum_4_4_fill_simple",
                "name": "4/4 过门鼓点（一小节）",
                "pattern": [
                    # 前两拍几乎空，只保留 Kick
                    (0.0, 0.25, "KICK", 115),
                    (1.5, 0.25, "KICK", 100),
                    # 后两拍用军鼓做 16 分填充
                    (2.0, 0.25, "SNARE", 110),
                    (2.25, 0.25, "SNARE", 100),
                    (2.5, 0.25, "SNARE", 105),
                    (2.75, 0.25, "SNARE", 100),
                    (3.0, 0.25, "SNARE", 115),
                    (3.25, 0.25, "SNARE", 105),
                    (3.5, 0.25, "SNARE", 110),
                    (3.75, 0.25, "SNARE", 100),
                    # 最后一个吊镲收尾
                    (3.75, 0.5, "CRASH", 120),
                ],
            },
            # 4/4：切分踩镲（off-beat）
            {
                "key": "drum_4_4_offbeat_hihat",
                "name": "4/4 反拍踩镲鼓点",
                "pattern": [
                    # Kick
                    (0.0, 0.25, "KICK", 115),
                    (1.0, 0.25, "KICK", 105),
                    (2.5, 0.25, "KICK", 110),
                    # Snare
                    (1.0, 0.25, "SNARE", 120),
                    (3.0, 0.25, "SNARE", 120),
                    # Off-beat Hi-hat on 8th off beats
                    (0.5, 0.25, "HIHAT", 95),
                    (1.5, 0.25, "HIHAT", 95),
                    (2.5, 0.25, "HIHAT", 95),
                    (3.5, 0.25, "HIHAT", 95),
                ],
            },
            # 3/4：华尔兹鼓点
            {
                "key": "drum_3_4_waltz",
                "name": "3/4 华尔兹鼓点",
                "pattern": [
                    # Kick on beat 1
                    (0.0, 0.5, "KICK", 115),
                    # Snare (or light hit) on 2 and 3
                    (1.0, 0.25, "SNARE", 90),
                    (2.0, 0.25, "SNARE", 90),
                    # Hi-hat 8th notes
                    (0.0, 0.25, "HIHAT", 80),
                    (0.5, 0.25, "HIHAT", 75),
                    (1.0, 0.25, "HIHAT", 80),
                    (1.5, 0.25, "HIHAT", 75),
                    (2.0, 0.25, "HIHAT", 80),
                    (2.5, 0.25, "HIHAT", 75),
                ],
            },
            # 6/8：摇滚 6/8
            {
                "key": "drum_6_8_rock",
                "name": "6/8 摇滚鼓点",
                "pattern": [
                    # 6/8 以 6 个八分为一小节，拍号换算成 beat=1/4，这里按 3 拍处理
                    # Kick on 1 and (3+)
                    (0.0, 0.5, "KICK", 115),
                    (1.5, 0.5, "KICK", 110),
                    # Snare on 2
                    (1.0, 0.5, "SNARE", 120),
                    # Hi-hat: 8th feel（这里近似用 0.5 拍表示）
                    (0.0, 0.25, "HIHAT", 85),
                    (0.5, 0.25, "HIHAT", 80),
                    (1.0, 0.25, "HIHAT", 85),
                    (1.5, 0.25, "HIHAT", 80),
                    (2.0, 0.25, "HIHAT", 85),
                    (2.5, 0.25, "HIHAT", 80),
                ],
            },
        ]

        for preset in drum_presets:
            key = preset["key"]
            if self._has_builtin_with_key(key):
                continue
            drums = []
            for offset_beats, dur_beats, drum_type, vel in preset["pattern"]:
                drums.append(
                    {
                        "offset_beats": float(offset_beats),
                        "duration_beats": float(dur_beats),
                        "drum_type": drum_type,
                        "velocity": int(vel),
                    }
                )
            snippet_id = self.add_snippet(
                name=preset["name"],
                group="预设-鼓点",
                snippet_type="drum",
                track_name="打击乐",
                data={"drums": drums},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = key
                    break

        # 2. 常用和弦
        # 提供两种形态：
        # - 「和弦」：多个音同时按下，持续一整小节（真实和弦手感，但在网格上会重叠在同一时刻）
        # - 「分解」：一小节内 4 个 1 拍音符，依次弹出和弦音（更易在网格上观察节奏）

        # --- 分解和弦模式 ---
        # C 大三和弦：C4-E4-G4-C5（分解）
        c_major_pattern = [
            (0.0, 1.0, 60),  # 第 1 拍：C4
            (1.0, 1.0, 64),  # 第 2 拍：E4
            (2.0, 1.0, 67),  # 第 3 拍：G4
            (3.0, 1.0, 72),  # 第 4 拍：C5
        ]
        # Am 小三和弦：A3-C4-E4-A4（分解）
        am_pattern = [
            (0.0, 1.0, 57),
            (1.0, 1.0, 60),
            (2.0, 1.0, 64),
            (3.0, 1.0, 69),
        ]
        # F 大三和弦：F3-A3-C4-F4（分解）
        f_major_pattern = [
            (0.0, 1.0, 53),
            (1.0, 1.0, 57),
            (2.0, 1.0, 60),
            (3.0, 1.0, 65),
        ]
        # G 大三和弦：G3-B3-D4-G4（分解）
        g_major_pattern = [
            (0.0, 1.0, 55),
            (1.0, 1.0, 59),
            (2.0, 1.0, 62),
            (3.0, 1.0, 67),
        ]

        def make_chord_notes(pattern):
            notes = []
            for offset_beats, dur_beats, pitch in pattern:
                notes.append(
                    {
                        "offset": beats_to_seconds(offset_beats),
                        "duration": beats_to_seconds(dur_beats),
                        "pitch": int(pitch),
                        "velocity": 100,
                        "waveform": "SQUARE",
                        "duty_cycle": 0.5,
                    }
                )
            return notes

        # C 大三和弦（分解）
        if not self._has_builtin_with_key("chord_C_major_arpeggio"):
            notes = make_chord_notes(c_major_pattern)
            snippet_id = self.add_snippet(
                name="C 大三和弦（分解）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_C_major_arpeggio"
                    break

        # Am 小三和弦（分解）
        if not self._has_builtin_with_key("chord_Am_arpeggio"):
            notes = make_chord_notes(am_pattern)
            snippet_id = self.add_snippet(
                name="Am 小三和弦（分解）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_Am_arpeggio"
                    break

        # F 大三和弦（分解）
        if not self._has_builtin_with_key("chord_F_major_arpeggio"):
            notes = make_chord_notes(f_major_pattern)
            snippet_id = self.add_snippet(
                name="F 大三和弦（分解）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_F_major_arpeggio"
                    break

        # G 大三和弦（分解）
        if not self._has_builtin_with_key("chord_G_major_arpeggio"):
            notes = make_chord_notes(g_major_pattern)
            snippet_id = self.add_snippet(
                name="G 大三和弦（分解）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_G_major_arpeggio"
                    break

        # --- 同步和弦模式（所有和弦音同时按下） ---

        def make_block_chord(pitches):
            """生成一个持续一整小节的 block chord（所有音同时起音和结束）"""
            duration = beats_to_seconds(4.0)
            notes = []
            for pitch in pitches:
                notes.append(
                    {
                        "offset": 0.0,
                        "duration": duration,
                        "pitch": int(pitch),
                        "velocity": 100,
                        "waveform": "SQUARE",
                        "duty_cycle": 0.5,
                    }
                )
            return notes

        # C 大三和弦（和弦）：C4-E4-G4
        if not self._has_builtin_with_key("chord_C_major_block"):
            notes = make_block_chord([60, 64, 67])
            snippet_id = self.add_snippet(
                name="C 大三和弦（和弦）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_C_major_block"
                    break

        # Am 小三和弦（和弦）：A3-C4-E4
        if not self._has_builtin_with_key("chord_Am_block"):
            notes = make_block_chord([57, 60, 64])
            snippet_id = self.add_snippet(
                name="Am 小三和弦（和弦）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_Am_block"
                    break

        # F 大三和弦（和弦）：F3-A3-C4
        if not self._has_builtin_with_key("chord_F_major_block"):
            notes = make_block_chord([53, 57, 60])
            snippet_id = self.add_snippet(
                name="F 大三和弦（和弦）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_F_major_block"
                    break

        # G 大三和弦（和弦）：G3-B3-D4
        if not self._has_builtin_with_key("chord_G_major_block"):
            notes = make_block_chord([55, 59, 62])
            snippet_id = self.add_snippet(
                name="G 大三和弦（和弦）",
                group="预设-和弦",
                snippet_type="note",
                track_name="和声",
                data={"notes": notes},
            )
            for s in self.snippets:
                if s.get("id") == snippet_id:
                    s["builtin"] = True
                    s["builtin_key"] = "chord_G_major_block"
                    break

        # 再自动生成一整套 12 调的大三和弦 / 小三和弦（和弦 + 分解），方便当作背景和声“乐高积木”来拼
        major_intervals = [0, 4, 7]
        minor_intervals = [0, 3, 7]

        # 这里选用一组常见音高作为根音（围绕 C4 附近），避免过高或过低
        chord_roots = [
            ("C", 60),
            ("Db", 61),
            ("D", 62),
            ("Eb", 63),
            ("E", 64),
            ("F", 65),
            ("F#", 66),
            ("G", 67),
            ("Ab", 68),
            ("A", 69),
            ("Bb", 70),
            ("B", 71),
        ]

        def build_triad_pitches(root_pitch: int, intervals):
            return [root_pitch + d for d in intervals]

        # 为每个根音生成：大三和弦/小三和弦（和弦 + 分解）
        for name, root in chord_roots:
            # Major triad
            major_pitches = build_triad_pitches(root, major_intervals)
            # Minor triad（对应自然小调平行调）
            minor_pitches = build_triad_pitches(root - 3, minor_intervals)  # 让根音更靠近中音区

            # Major block chord
            major_block_key = f"chord_{name}_major_block_auto"
            if not self._has_builtin_with_key(major_block_key):
                notes = make_block_chord(major_pitches)
                snippet_id = self.add_snippet(
                    name=f"{name} 大三和弦（和弦，自动）",
                    group="预设-和弦",
                    snippet_type="note",
                    track_name="和声",
                    data={"notes": notes},
                )
                for s in self.snippets:
                    if s.get("id") == snippet_id:
                        s["builtin"] = True
                        s["builtin_key"] = major_block_key
                        break

            # Major arpeggio（分解）：4 拍内依次弹出三和弦 + 高八度根音
            major_arp_key = f"chord_{name}_major_arpeggio_auto"
            if not self._has_builtin_with_key(major_arp_key):
                arp_pattern = [
                    (0.0, 1.0, major_pitches[0]),
                    (1.0, 1.0, major_pitches[1]),
                    (2.0, 1.0, major_pitches[2]),
                    (3.0, 1.0, major_pitches[0] + 12),
                ]
                notes = make_chord_notes(arp_pattern)
                snippet_id = self.add_snippet(
                    name=f"{name} 大三和弦（分解，自动）",
                    group="预设-和弦",
                    snippet_type="note",
                    track_name="和声",
                    data={"notes": notes},
                )
                for s in self.snippets:
                    if s.get("id") == snippet_id:
                        s["builtin"] = True
                        s["builtin_key"] = major_arp_key
                        break

            # Minor block chord
            minor_block_key = f"chord_{name}_minor_block_auto"
            if not self._has_builtin_with_key(minor_block_key):
                notes = make_block_chord(minor_pitches)
                snippet_id = self.add_snippet(
                    name=f"{name} 小三和弦（和弦，自动）",
                    group="预设-和弦",
                    snippet_type="note",
                    track_name="和声",
                    data={"notes": notes},
                )
                for s in self.snippets:
                    if s.get("id") == snippet_id:
                        s["builtin"] = True
                        s["builtin_key"] = minor_block_key
                        break

            # Minor arpeggio
            minor_arp_key = f"chord_{name}_minor_arpeggio_auto"
            if not self._has_builtin_with_key(minor_arp_key):
                arp_pattern = [
                    (0.0, 1.0, minor_pitches[0]),
                    (1.0, 1.0, minor_pitches[1]),
                    (2.0, 1.0, minor_pitches[2]),
                    (3.0, 1.0, minor_pitches[0] + 12),
                ]
                notes = make_chord_notes(arp_pattern)
                snippet_id = self.add_snippet(
                    name=f"{name} 小三和弦（分解，自动）",
                    group="预设-和弦",
                    snippet_type="note",
                    track_name="和声",
                    data={"notes": notes},
                )
                for s in self.snippets:
                    if s.get("id") == snippet_id:
                        s["builtin"] = True
                        s["builtin_key"] = minor_arp_key
                        break

        # 保存一次，写入 builtin 标记
        self._save()

    # ---- 对外 API ----

    def list_snippets(self) -> List[Dict[str, Any]]:
        return list(self.snippets)

    def get_snippet(self, snippet_id: str) -> Optional[Dict[str, Any]]:
        for s in self.snippets:
            if s.get("id") == snippet_id:
                return s
        return None

    def add_snippet(
        self,
        *,
        name: str,
        group: str,
        snippet_type: str,
        track_name: str,
        data: Dict[str, Any],
    ) -> str:
        """
        添加一个新的乐谱片段。

        snippet_type: "note" 或 "drum"
        data: 对于 note 片段，包含 notes 列表；对于 drum 片段，包含 drums 列表。
        """
        snippet_id = str(uuid.uuid4())
        snippet = {
            "id": snippet_id,
            "name": name,
            "group": group or "",
            "type": snippet_type,  # "note" or "drum"
            "track_name": track_name or "",
            "data": data,
        }
        self.snippets.append(snippet)
        self._save()
        return snippet_id

    def rename_snippet(self, snippet_id: str, new_name: str) -> None:
        """重命名指定片段"""
        new_name = (new_name or "").strip()
        if not new_name:
            return
        for s in self.snippets:
            if s.get("id") == snippet_id:
                s["name"] = new_name
                self._save()
                return

    def rename_group(self, old_group: str, new_group: str) -> None:
        """重命名分组：将所有旧分组名改为新分组名"""
        old_group = (old_group or "").strip()
        new_group = (new_group or "").strip()
        if not old_group or not new_group or old_group == new_group:
            return
        changed = False
        for s in self.snippets:
            if (s.get("group") or "") == old_group:
                s["group"] = new_group
                changed = True
        if changed:
            self._save()

    def delete_snippet(self, snippet_id: str) -> None:
        self.snippets = [s for s in self.snippets if s.get("id") != snippet_id]
        self._save()


