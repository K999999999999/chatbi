"""Evaluation（评测）报告相关的共享错误类型。"""


class ReportingError(RuntimeError):
    """评测报告配置、读取或写入失败。"""
