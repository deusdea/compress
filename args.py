from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# --- 1. 定义各个层级的 Dataclass ---

@dataclass
class CompressPlusConfig:
    """压缩拓展选项"""
    level: int = 7
    filter_choice: int = 0
    password: Optional[str] = None
    if_partial: bool = False
    max_part_size: str = "100MB"
    if_encode_name: bool = False
    if_delete_original: bool = False

@dataclass
class ExtractPlusConfig:
    """解压拓展选项"""
    password: str = ""
    if_delete_original: bool = False
    if_decode_name: bool = False

@dataclass
class BaseCommandConfig:
    """基础命令配置 (适用于 compress 和 extract)"""
    name: Optional[str] = "compress" 
    source_path: Path = Path()
    output_path: Optional[Path] = None

@dataclass
class AppConfig:
    """应用总配置入口"""
    command: Optional[str] = None       # 记录当前执行的是 'compress' 还是 'extract'
    sub_command: Optional[str] = None   # 记录是否进入了 'plus' 模式
    base: BaseCommandConfig = field(default_factory=BaseCommandConfig)
    compress_plus: CompressPlusConfig = field(default_factory=CompressPlusConfig)
    extract_plus: ExtractPlusConfig = field(default_factory=ExtractPlusConfig)

