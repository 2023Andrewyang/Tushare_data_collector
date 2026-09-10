# -*- coding: utf-8 -*-
"""采集任务的统一进度与剩余时间日志。"""
import logging
import time


class ProgressReporter:
    """按工作项记录模块级进度，并以已完成项目的平均耗时估算 ETA。"""

    def __init__(self, logger: logging.Logger, module: str, total: int,
                 item_label: str = "日期"):
        self.logger = logger
        self.module = module
        self.total = max(total, 0)
        self.item_label = item_label
        self.completed = 0
        self.current = None
        self._started_at = time.monotonic()

    def start(self, current) -> None:
        """记录即将处理的工作项；首项前 ETA 尚无可用样本。"""
        self.current = str(current)
        self._log()

    def advance(self, current=None) -> None:
        """将当前工作项计为已完成（无论请求成功或已记录为失败）。"""
        if current is not None:
            self.current = str(current)
        self.completed = min(self.completed + 1, self.total)
        self._log()

    def _eta(self) -> str:
        if self.completed == 0:
            return "计算中"
        remaining = self.total - self.completed
        if remaining == 0:
            return "00:00:00"
        seconds = (time.monotonic() - self._started_at) / self.completed * remaining
        return self._format_seconds(seconds)

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        seconds = max(0, round(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours >= 24:
            days, hours = divmod(hours, 24)
            return f"{days}天{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _log(self) -> None:
        percent = self.completed / self.total * 100 if self.total else 100.0
        current = self.current if self.current is not None else "-"
        self.logger.info(
            "[进度] 模块=%s | 当前%s=%s | 进度=%.2f%% (%d/%d) | 预计剩余=%s",
            self.module, self.item_label, current, percent,
            self.completed, self.total, self._eta())
