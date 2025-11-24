"""
命令模式实现 - 撤销/重做功能

使用命令模式实现操作的撤销和重做。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
import copy

from .models import Project, Track, Note, WaveformType, ADSRParams


class Command(ABC):
    """命令基类"""
    
    @abstractmethod
    def execute(self) -> None:
        """执行命令"""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """撤销命令"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取命令描述（用于显示）"""
        pass


class CommandHistory:
    """命令历史管理器"""
    
    def __init__(self, max_history: int = 100):
        """
        初始化命令历史
        
        Args:
            max_history: 最大历史记录数
        """
        self.history: List[Command] = []
        self.current_index: int = -1  # 当前命令索引（-1表示没有命令）
        self.max_history = max_history
    
    def execute_command(self, command: Command) -> None:
        """
        执行命令并添加到历史
        
        Args:
            command: 要执行的命令
        """
        # 执行命令
        command.execute()
        
        # 如果当前不在历史末尾，删除后面的命令（分支历史）
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # 添加到历史
        self.history.append(command)
        self.current_index = len(self.history) - 1
        
        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.current_index -= 1
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return self.current_index < len(self.history) - 1
    
    def undo(self) -> Optional[str]:
        """
        撤销上一个命令
        
        Returns:
            命令描述，如果无法撤销则返回None
        """
        if not self.can_undo():
            return None
        
        command = self.history[self.current_index]
        command.undo()
        self.current_index -= 1
        
        return command.get_description()
    
    def redo(self) -> Optional[str]:
        """
        重做下一个命令
        
        Returns:
            命令描述，如果无法重做则返回None
        """
        if not self.can_redo():
            return None
        
        self.current_index += 1
        command = self.history[self.current_index]
        command.execute()
        
        return command.get_description()
    
    def clear(self) -> None:
        """清空历史"""
        self.history.clear()
        self.current_index = -1
    
    def get_history_info(self) -> Dict[str, Any]:
        """获取历史信息（用于调试）"""
        return {
            "total_commands": len(self.history),
            "current_index": self.current_index,
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo()
        }


# ========== 具体命令类 ==========

class AddNoteCommand(Command):
    """添加音符命令"""
    
    def __init__(self, sequencer, track: Track, note: Note):
        """
        初始化添加音符命令
        
        Args:
            sequencer: 序列器对象
            track: 目标轨道
            note: 要添加的音符
        """
        self.sequencer = sequencer
        self.track = track
        self.note = note
    
    def execute(self) -> None:
        """执行：添加音符"""
        self.track.add_note(self.note)
    
    def undo(self) -> None:
        """撤销：删除音符"""
        self.track.remove_note(self.note)
    
    def get_description(self) -> str:
        """获取描述"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = self.note.pitch // 12 - 1
        note_name = note_names[self.note.pitch % 12]
        return f"添加音符: {note_name}{octave}"


class DeleteNoteCommand(Command):
    """删除音符命令"""
    
    def __init__(self, sequencer, track: Track, note: Note):
        """
        初始化删除音符命令
        
        Args:
            sequencer: 序列器对象
            track: 目标轨道
            note: 要删除的音符
        """
        self.sequencer = sequencer
        self.track = track
        self.note = note
        # 保存音符的深拷贝用于撤销
        self.note_copy = self._copy_note(note)
    
    def _copy_note(self, note: Note) -> Note:
        """深拷贝音符"""
        return Note(
            pitch=note.pitch,
            start_time=note.start_time,
            duration=note.duration,
            velocity=note.velocity,
            waveform=note.waveform,
            duty_cycle=note.duty_cycle,
            adsr=ADSRParams(
                attack=note.adsr.attack,
                decay=note.adsr.decay,
                sustain=note.adsr.sustain,
                release=note.adsr.release
            ) if note.adsr else None,
            note_value=note.note_value,
            grid_index=note.grid_index
        )
    
    def execute(self) -> None:
        """执行：删除音符"""
        self.track.remove_note(self.note)
    
    def undo(self) -> None:
        """撤销：恢复音符"""
        # 恢复音符（使用保存的拷贝）
        restored_note = self._copy_note(self.note_copy)
        self.track.add_note(restored_note)
        # 更新引用
        self.note = restored_note
    
    def get_description(self) -> str:
        """获取描述"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = self.note.pitch // 12 - 1
        note_name = note_names[self.note.pitch % 12]
        return f"删除音符: {note_name}{octave}"


class ModifyNoteCommand(Command):
    """修改音符命令"""
    
    def __init__(self, sequencer, track: Track, note: Note, **kwargs):
        """
        初始化修改音符命令
        
        Args:
            sequencer: 序列器对象
            track: 目标轨道
            note: 要修改的音符
            **kwargs: 要修改的属性（pitch, start_time, duration, velocity, waveform, duty_cycle, adsr等）
        """
        self.sequencer = sequencer
        self.track = track
        self.note = note
        
        # 保存旧值
        self.old_values = {}
        self.new_values = {}
        
        for key, new_value in kwargs.items():
            if hasattr(note, key):
                old_value = getattr(note, key)
                self.old_values[key] = old_value
                self.new_values[key] = new_value
    
    def execute(self) -> None:
        """执行：应用新值"""
        for key, value in self.new_values.items():
            if key == 'adsr' and value is not None:
                # ADSR需要特殊处理
                if self.note.adsr is None:
                    self.note.adsr = ADSRParams()
                if isinstance(value, dict):
                    for adsr_key, adsr_value in value.items():
                        if hasattr(self.note.adsr, adsr_key):
                            setattr(self.note.adsr, adsr_key, adsr_value)
                elif isinstance(value, ADSRParams):
                    self.note.adsr = value
            else:
                setattr(self.note, key, value)
        
        # 如果修改了start_time或duration，需要重新排序
        if 'start_time' in self.new_values or 'duration' in self.new_values:
            self.track.notes.sort(key=lambda n: n.start_time)
    
    def undo(self) -> None:
        """撤销：恢复旧值"""
        for key, value in self.old_values.items():
            if key == 'adsr' and value is not None:
                # ADSR需要特殊处理
                if self.note.adsr is None:
                    self.note.adsr = ADSRParams()
                if isinstance(value, dict):
                    for adsr_key, adsr_value in value.items():
                        if hasattr(self.note.adsr, adsr_key):
                            setattr(self.note.adsr, adsr_key, adsr_value)
                elif isinstance(value, ADSRParams):
                    self.note.adsr = value
            else:
                setattr(self.note, key, value)
        
        # 如果修改了start_time或duration，需要重新排序
        if 'start_time' in self.old_values or 'duration' in self.old_values:
            self.track.notes.sort(key=lambda n: n.start_time)
    
    def get_description(self) -> str:
        """获取描述"""
        changed_attrs = list(self.new_values.keys())
        if len(changed_attrs) == 1:
            attr_name = changed_attrs[0]
            attr_names = {
                'pitch': '音高',
                'start_time': '位置',
                'duration': '时长',
                'velocity': '力度',
                'waveform': '波形',
                'duty_cycle': '占空比',
                'adsr': '包络'
            }
            return f"修改音符{attr_names.get(attr_name, attr_name)}"
        else:
            return f"修改音符属性 ({len(changed_attrs)}项)"


class MoveNoteCommand(Command):
    """移动音符命令（修改start_time）"""
    
    def __init__(self, sequencer, track: Track, note: Note, new_start_time: float):
        """
        初始化移动音符命令
        
        Args:
            sequencer: 序列器对象
            track: 目标轨道
            note: 要移动的音符
            new_start_time: 新的开始时间
        """
        self.sequencer = sequencer
        self.track = track
        self.note = note
        self.old_start_time = note.start_time
        self.new_start_time = new_start_time
    
    def execute(self) -> None:
        """执行：移动到新位置"""
        self.note.start_time = self.new_start_time
        self.track.notes.sort(key=lambda n: n.start_time)
    
    def undo(self) -> None:
        """撤销：恢复到旧位置"""
        self.note.start_time = self.old_start_time
        self.track.notes.sort(key=lambda n: n.start_time)
    
    def get_description(self) -> str:
        """获取描述"""
        return "移动音符"


class ModifyTrackCommand(Command):
    """修改轨道属性命令"""
    
    def __init__(self, sequencer, track: Track, **kwargs):
        """
        初始化修改轨道命令
        
        Args:
            sequencer: 序列器对象
            track: 要修改的轨道
            **kwargs: 要修改的属性（name, waveform, volume, pan, enabled等）
        """
        self.sequencer = sequencer
        self.track = track
        
        # 保存旧值
        self.old_values = {}
        self.new_values = {}
        
        for key, new_value in kwargs.items():
            if hasattr(track, key):
                old_value = getattr(track, key)
                self.old_values[key] = old_value
                self.new_values[key] = new_value
    
    def execute(self) -> None:
        """执行：应用新值"""
        for key, value in self.new_values.items():
            setattr(self.track, key, value)
    
    def undo(self) -> None:
        """撤销：恢复旧值"""
        for key, value in self.old_values.items():
            setattr(self.track, key, value)
    
    def get_description(self) -> str:
        """获取描述"""
        changed_attrs = list(self.new_values.keys())
        if len(changed_attrs) == 1:
            attr_name = changed_attrs[0]
            attr_names = {
                'name': '名称',
                'waveform': '波形',
                'volume': '音量',
                'pan': '声相',
                'enabled': '启用状态'
            }
            return f"修改轨道{attr_names.get(attr_name, attr_name)}"
        else:
            return f"修改轨道属性 ({len(changed_attrs)}项)"


class AddTrackCommand(Command):
    """添加轨道命令"""
    
    def __init__(self, sequencer, track: Track):
        """
        初始化添加轨道命令
        
        Args:
            sequencer: 序列器对象
            track: 要添加的轨道
        """
        self.sequencer = sequencer
        self.track = track
    
    def execute(self) -> None:
        """执行：添加轨道"""
        self.sequencer.project.add_track(self.track)
    
    def undo(self) -> None:
        """撤销：删除轨道"""
        self.sequencer.project.remove_track(self.track)
    
    def get_description(self) -> str:
        """获取描述"""
        return f"添加轨道: {self.track.name}"


class DeleteTrackCommand(Command):
    """删除轨道命令"""
    
    def __init__(self, sequencer, track: Track):
        """
        初始化删除轨道命令
        
        Args:
            sequencer: 序列器对象
            track: 要删除的轨道
        """
        self.sequencer = sequencer
        self.track = track
        self.track_index = None  # 保存轨道在列表中的位置
    
    def execute(self) -> None:
        """执行：删除轨道"""
        # 保存轨道位置
        if self.track in self.sequencer.project.tracks:
            self.track_index = self.sequencer.project.tracks.index(self.track)
        self.sequencer.project.remove_track(self.track)
    
    def undo(self) -> None:
        """撤销：恢复轨道"""
        if self.track_index is not None:
            self.sequencer.project.tracks.insert(self.track_index, self.track)
        else:
            self.sequencer.project.add_track(self.track)
    
    def get_description(self) -> str:
        """获取描述"""
        return f"删除轨道: {self.track.name}"


class BatchModifyNotesCommand(Command):
    """批量修改多个音符的命令"""
    
    def __init__(self, sequencer, notes_and_tracks: list, **kwargs):
        """
        初始化批量修改音符命令
        
        Args:
            sequencer: 序列器对象
            notes_and_tracks: [(note, track), ...] 音符和轨道对列表
            **kwargs: 要修改的属性
        """
        self.sequencer = sequencer
        self.notes_and_tracks = notes_and_tracks
        self.kwargs = kwargs
        
        # 保存所有音符的旧值
        self.old_values_list = []
        for note, track in notes_and_tracks:
            old_values = {}
            for key in kwargs.keys():
                if hasattr(note, key):
                    old_value = getattr(note, key)
                    if key == 'adsr' and old_value is not None:
                        # ADSR需要特殊处理
                        old_values[key] = {
                            'attack': old_value.attack,
                            'decay': old_value.decay,
                            'sustain': old_value.sustain,
                            'release': old_value.release
                        }
                    else:
                        old_values[key] = old_value
            self.old_values_list.append(old_values)
    
    def execute(self) -> None:
        """执行：应用新值到所有音符"""
        for (note, track), old_values in zip(self.notes_and_tracks, self.old_values_list):
            for key, value in self.kwargs.items():
                if hasattr(note, key):
                    if key == 'adsr' and value is not None:
                        # ADSR需要特殊处理
                        if note.adsr is None:
                            note.adsr = ADSRParams()
                        if isinstance(value, dict):
                            for adsr_key, adsr_value in value.items():
                                if hasattr(note.adsr, adsr_key):
                                    setattr(note.adsr, adsr_key, adsr_value)
                    else:
                        setattr(note, key, value)
            
            # 如果修改了start_time或duration，需要重新排序
            if 'start_time' in self.kwargs or 'duration' in self.kwargs:
                track.notes.sort(key=lambda n: n.start_time)
    
    def undo(self) -> None:
        """撤销：恢复所有音符的旧值"""
        for (note, track), old_values in zip(self.notes_and_tracks, self.old_values_list):
            for key, value in old_values.items():
                if key == 'adsr' and value is not None:
                    # ADSR需要特殊处理
                    if note.adsr is None:
                        note.adsr = ADSRParams()
                    if isinstance(value, dict):
                        for adsr_key, adsr_value in value.items():
                            if hasattr(note.adsr, adsr_key):
                                setattr(note.adsr, adsr_key, adsr_value)
                else:
                    setattr(note, key, value)
            
            # 如果修改了start_time或duration，需要重新排序
            if 'start_time' in old_values or 'duration' in old_values:
                track.notes.sort(key=lambda n: n.start_time)
    
    def get_description(self) -> str:
        """获取描述"""
        changed_attrs = list(self.kwargs.keys())
        if len(changed_attrs) == 1:
            attr_name = changed_attrs[0]
            attr_names = {
                'pitch': '音高',
                'start_time': '位置',
                'duration': '时长',
                'velocity': '力度',
                'waveform': '波形',
                'duty_cycle': '占空比',
                'adsr': '包络'
            }
            return f"批量修改{len(self.notes_and_tracks)}个音符的{attr_names.get(attr_name, attr_name)}"
        else:
            return f"批量修改{len(self.notes_and_tracks)}个音符的属性 ({len(changed_attrs)}项)"


class BatchCommand(Command):
    """批量命令（用于组合多个命令）"""
    
    def __init__(self, commands: List[Command], description: str = "批量操作"):
        """
        初始化批量命令
        
        Args:
            commands: 命令列表
            description: 命令描述
        """
        self.commands = commands
        self.description = description
    
    def execute(self) -> None:
        """执行：按顺序执行所有命令"""
        for command in self.commands:
            command.execute()
    
    def undo(self) -> None:
        """撤销：按逆序撤销所有命令"""
        for command in reversed(self.commands):
            command.undo()
    
    def get_description(self) -> str:
        """获取描述"""
        return self.description

