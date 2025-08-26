import os
import sys
from datetime import datetime
from typing import Optional


def _get_timestamp() -> str:
    """获取时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FanTwoLogger:
    """带颜色标记的日志记录器"""

    # ANSI 颜色代码
    COLORS = {
        'RESET': '\033[0m',
        'BLACK': '\033[30m',
        'RED': '\033[31m',
        'GREEN': '\033[32m',
        'YELLOW': '\033[33m',
        'BLUE': '\033[34m',
        'MAGENTA': '\033[35m',
        'CYAN': '\033[36m',
        'WHITE': '\033[37m',
        'BRIGHT_BLACK': '\033[90m',
        'BRIGHT_RED': '\033[91m',
        'BRIGHT_GREEN': '\033[92m',
        'BRIGHT_YELLOW': '\033[93m',
        'BRIGHT_BLUE': '\033[94m',
        'BRIGHT_MAGENTA': '\033[95m',
        'BRIGHT_CYAN': '\033[96m',
        'BRIGHT_WHITE': '\033[97m',
    }

    # 日志级别颜色映射
    LEVEL_COLORS = {
        'DEBUG': 'BRIGHT_BLACK',
        'INFO': 'BLUE',
        'SUCCESS': 'BRIGHT_GREEN',
        'WARNING': 'BRIGHT_YELLOW',
        'ERROR': 'BRIGHT_RED',
        'CRITICAL': 'RED',
    }

    LEVEL_PRIORITY = {
        'DEBUG': 10,
        'INFO': 20,
        'SUCCESS': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50,
    }
    SUPPORTED_LEVELS = ['DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']

    def __init__(self, name: str = "", log_file: Optional[str] = None, level: str = "INFO"):

        self.level = level.upper()
        self._current_priority = self.LEVEL_PRIORITY[self.level]
        self.name = name
        self.log_file = log_file
        # self._check_color_support()
        
    def set_level(self, level: str):
        """设置日志输出级别"""
        level_upper = level.upper()
        if level_upper not in self.SUPPORTED_LEVELS:
            raise ValueError(f"不支持的日志级别: {level}. 支持的级别: {', '.join(self.SUPPORTED_LEVELS)}")
        self.level = level_upper
        self._current_priority = self.LEVEL_PRIORITY[level_upper]

    def _should_log(self, level: str) -> bool:
        """检查是否应该记录该级别的日志"""
        return self.LEVEL_PRIORITY.get(level, 0) >= self._current_priority

    def get_level(self) -> str:
        """获取当前日志级别"""
        return self.level

    def _check_color_support(self):
        """检查终端是否支持颜色"""
        self.supports_color = (
                hasattr(sys.stdout, 'isatty') and
                sys.stdout.isatty() and
                os.name != 'nt'  # Windows 需要额外的处理
        )

    def _write_log(self, level: str, message: str, color: str = None):
        """写入日志"""
        timestamp = _get_timestamp()
        log_message = f"[{timestamp}] [{level}] {self.name}: {message}"
        if not self._should_log(level):
            return

        # 控制台输出（带颜色）
        if color:
            colored_message = f"{self.COLORS[color]}{log_message}{self.COLORS['RESET']}"
            print(colored_message)
        else:
            print(log_message)

        # 文件输出（无颜色）
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
            except Exception:
                pass

    def debug(self, message: str):
        """调试信息"""
        self._write_log('DEBUG', message, self.LEVEL_COLORS['DEBUG'])

    def info(self, message: str):
        """普通信息"""
        self._write_log('INFO', message, self.LEVEL_COLORS['INFO'])

    def success(self, message: str):
        """成功信息"""
        self._write_log('SUCCESS', message, self.LEVEL_COLORS['SUCCESS'])

    def warning(self, message: str):
        """警告信息"""
        self._write_log('WARNING', message, self.LEVEL_COLORS['WARNING'])

    def error(self, message: str):
        """错误信息"""
        self._write_log('ERROR', message, self.LEVEL_COLORS['ERROR'])

    def critical(self, message: str):
        """严重错误信息"""
        self._write_log('CRITICAL', message, self.LEVEL_COLORS['CRITICAL'])

    def progress(self, current: int, total: int, message: str = ""):
        """进度信息"""
        percentage = (current / total) * 100
        progress_msg = f"[{current}/{total}] {percentage:.1f}% {message}"
        self._write_log('INFO', progress_msg, 'BRIGHT_CYAN')

    def separator(self, char: str = "=", length: int = 60):
        """分隔线"""
        separator_line = char * length
        self._write_log('INFO', separator_line, 'BRIGHT_BLUE')


# Windows 颜色支持
if os.name == 'nt':  # Windows
    try:
        import ctypes

        # 获取标准输出句柄
        STD_OUTPUT_HANDLE = -11
        handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        # 获取当前控制台模式
        current_mode = ctypes.c_uint32()
        ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(current_mode))

        # 启用虚拟终端处理 (ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004)
        new_mode = current_mode.value | 0x0004
        ctypes.windll.kernel32.SetConsoleMode(handle, new_mode)

    except (AttributeError, OSError, WindowsError):
        # 如果API调用失败，回退到无颜色模式
        pass

