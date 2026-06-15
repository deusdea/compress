
import py7zr as p7
import os
from pathlib import Path
import re
import math
import argparse
from tqdm import tqdm
import log
from constants import *
import encode
from send2trash import send2trash
# import shutil
import psutil
from args import *
import sys

TAIL_LEN: int = math.ceil(math.log10(SUB_CNT_THRESHOLD))


filters: list[list[dict[str, int]]] = [[{"id": p7.FILTER_LZMA2, "preset": 7}],
                                             [{"id": p7.FILTER_ZSTD, "level": 3}]]
cwd = Path(os.getcwd())
filter_level_dict: dict[str, str] = {"0": "preset", "1": "level"}

def base_seven_zip(name: str = "compressed", 
            source_path: Path = cwd, 
            target_path: Path = cwd
            ) -> Result:
    file_list: list[Path] = []
    if source_path.is_dir(): file_list = [fp for fp in source_path.iterdir()]
    else: 
        file_list.append(source_path)
        target_path = source_path.parent
    if file_list == []: return None, "文件列表为空！"

    total_size: int = sum(f.stat().st_size for f in file_list)
    target_file: Path = target_path / Path(name)

    skip: bool = False
    if target_file.exists(): 
        log.Info("文件已经存在！跳过压缩吗？(Y/N)")
        str1 = input().strip().lower()
        skip = str1 == "y" or str1 == "yes"
    if not skip:
        log.Info("开始压缩。")
        with p7.SevenZipFile(target_file, "w", filters = filters[0], mp = True) as archive:
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="7z压缩中")
            for _, fp in enumerate(file_list):
                archive.write(fp)
                pbar.update(fp.stat().st_size)
            pbar.close()
    log.Info("压缩完毕！")
    return True, log.success("压缩成功！")
    
     
def seven_zip(name: str = "compressed", password: Optional[str] = None, 
            if_spit: bool = False, max_part_size: str = "100MB",
            source_path: Path = cwd, target_path: Path = cwd, 
            filter_choice:int = 0, level: int = 0, delete_original: bool = False) -> Result: 
    filter: list[dict[str, int]] = filters[filter_choice]
    filters[filter_choice][0][filter_level_dict[str(filter_choice)]] = level
    file_list: list[Path] = []
    if source_path.is_dir(): file_list = [fp for fp in source_path.iterdir()]
    elif source_path.is_file(): 
        file_list.append(source_path)
        target_path = source_path.parent
    if file_list == []: return None, "文件列表为空！"
    total_size: int = sum(f.stat().st_size for f in file_list) # 预留5%空间给压缩包结构等元数据，避免分片过多
    expected_size: int = math.ceil(total_size * 0.95)
    target_file: Path = target_path / Path(name)
    part_byte_size: int = 0
    if if_spit:
        data, message = get_byte_size_from_format(max_part_size)
        if not data: return (None, message)
        if math.ceil(expected_size / data) > SUB_CNT_THRESHOLD: 
            log.Error("分片过小！分卷过多！")
            return (None, log.error("分片过小！分卷过多！"))
        part_byte_size = data
    skip: bool = False
    if target_file.exists(): 
        log.Info("文件已经存在！跳过压缩吗？(Y/N)")
        str1 = input().strip().lower()
        skip = str1 == "y" or str1 == "yes"
    if not skip:
        log.Info("开始压缩。")
        with p7.SevenZipFile(target_file, "w", password = password, filters = filter, mp = True) as archive:
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="7z压缩中")
            for _, fp in enumerate(file_list):
                archive.write(fp)
                if delete_original: send2trash(fp)
                pbar.update(fp.stat().st_size)
            pbar.close()
    log.Info("压缩完毕！")
    
    if(if_spit):
        data, msg = spilt_file(target_file, part_byte_size)
        if not data: return (None, log.error(msg))
        log.Info("分片完毕！")
        target_file.unlink()
    return True, log.success("压缩成功！")

def spilt_file(file: Path, part_byte_size: int) -> Result:
    part_num: int = 1
    base_filename: str = file.name
    width: int = math.ceil(math.log10(SUB_CNT_THRESHOLD))
    file_size: int = file.stat().st_size
    with open(file, 'rb') as source_file:
        pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc="进行分片中")
        available_memory = psutil.virtual_memory().available
        use_max_buffer = min(available_memory // 2, USE_MAX_BUFFER_SIZE) # 使用可用内存的一半，但不超过100MB
        while True:
            total_size: int = part_byte_size
            read_size: int = min(use_max_buffer, total_size)
            num_str: str = str(part_num).strip().zfill(width)
            part_filename = Path(f"{base_filename}.{num_str}")
            new_file: Path = file.parent / part_filename
            with open(new_file, 'wb') as part_file:
                if read_size == total_size:
                    chunk = source_file.read(read_size)
                    if not chunk: break
                    part_file.write(chunk)
                    pbar.update(len(chunk))
                else:
                    while True:
                        chunk = source_file.read(read_size)
                        if not chunk: break
                        part_file.write(chunk)
                        total_size -= len(chunk)
                        pbar.update(len(chunk))
            part_num += 1

        pbar.close()
    
    return (True, log.success("分片成功！"))



def merge_file(source_path_or_file: Path, output_path_or_file: Path, if_delete_chunks: bool = False) -> Result:
    file_list: list[Path] = []
    file_prefixs: set[str] = set()
    file_exts: set[str] = set()
    total_size: int = 0
    if source_path_or_file.is_file():
        match = re.search(r".*\.(.*)", source_path_or_file.name)
        if match: return output_path_or_file, log.success("无需合并！")
        source_path_or_file = source_path_or_file.parent
    for fp in source_path_or_file.iterdir():
        match = re.match(r"(.*)\.(.*)\.(\d+)$", fp.name)
        if fp.is_file() and match:
            file_list.append(fp)
            total_size += fp.stat().st_size
            file_prefixs.add(match.group(1))
            file_exts.add(match.group(2))
            if len(file_prefixs) > 1: return (None, log.error("分片文件前缀不一致！"))
            if len(file_exts) > 1: return (None, log.error("分片文件扩展名不一致！"))
    if not file_list: return (None, log.error("未找到任何匹配的分片文件！"))
    if file_prefixs.pop() == "": prefix = "dist"
    else: prefix = file_prefixs.pop()
    if output_path_or_file.is_dir(): output_path_or_file = output_path_or_file / Path(prefix)

    chunk_files = sorted(file_list)
    part_num = chunk_files[0].name.split(".")[-1]
    for _, chunk_file in enumerate(chunk_files):
        expected_part_num = part_num.strip().zfill(math.ceil(math.log10(SUB_CNT_THRESHOLD)))
        actual_part_num = chunk_file.name.split(".")[-1]
        if expected_part_num != actual_part_num:
            return (None, log.error(f"分片文件缺失或命名不规范！期望的分片编号: {expected_part_num}, 实际的分片编号: {actual_part_num}"))
        part_num = str(int(part_num) + 1)
    try:
        # 3. 以二进制追加模式打开输出文件
        with open(output_path_or_file, 'wb') as target_file:
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="合并分片中")
            for chunk_file in chunk_files:
                with open(chunk_file, 'rb') as src:
                    available_memory = psutil.virtual_memory().available
                    use_buffer = min(available_memory // 2, USE_MAX_BUFFER_SIZE) # 使用可用内存的一半，但不超过100MB
                    while True:
                        buffer = src.read(use_buffer) 
                        if not buffer: break
                        target_file.write(buffer)
                        pbar.update(len(buffer))                
            pbar.close()
        send2trash(chunk_files) 
    except Exception as e:
        # 如果合并中途失败，清理掉生成了一半的损坏文件
        if output_path_or_file.exists():
            output_path_or_file.unlink()
        return (None, log.error(f"合并文件失败: {e}"))
    return (output_path_or_file, log.success("合并成功！"))

def get_byte_size_from_format(size: str) -> Result:
    size_lower: str = size.strip().lower()
    match = re.search(rf"^(\d+)([mkg]b)$", size_lower)
    if not match: return (None, log.error("大小不符合格式！"))
    num_str, suffix = match.groups()
    num: int = int(num_str)
    res: int = num
    if suffix == "gb":
        res = num * 1024 * 1024 * 1024
    elif suffix == "mb":
        res = num * 1024 * 1024
    elif suffix == "kb":
        if num < 1024: return (None, log.error("分片大小至少1024KB(1MB)！"))
        res = num * 1024
    return (res, "大小识别成功！")


def base_seven_extract(source_path_file: Path = cwd, target_path: Path = cwd.parent) -> Result:
    target_file, message = merge_file(source_path_file, target_path)
    if not target_file: return (None, message)
    if target_file.is_file(): target_path = target_file.parent
    with p7.SevenZipFile(target_file, "r") as archive:
        log.Info("开始解压。")
        archive.extractall(path=target_path)
    log.Info("提取完毕！")
    return True, log.success("提取成功！")
def seven_extract(
        password: Optional[str] = None, 
        source_path_file: Path = cwd, 
        target_path: Path = cwd.parent, 
        if_delete_original: bool = False
    ) -> Result:
    target_file, message = merge_file(source_path_file, target_path)
    if not target_file: return (None, message)
    if target_file.is_file(): target_path = target_file.parent
    with p7.SevenZipFile(target_file, "r", password = password) as archive:
        log.Info("开始解压。")
        archive.extractall(path=target_path)
    log.Info("提取完毕！")
    if if_delete_original: send2trash(target_file)
    return True, log.success("提取成功！")


def __input_args() -> Result:
    parser = argparse.ArgumentParser(description="文件处理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    # 创建 compress 子命令
    compress_parser = subparsers.add_parser("compress", help="压缩文件")
    compress_parser.add_argument("-o", "--name", type=str, help="压缩文件名称")
    compress_parser.add_argument("-s", "--source", type=Path, required=True, help="文件来源")
    compress_parser.add_argument("-O", "--output", type=Path, help="压缩文件路径")
    compress_plus_parser = compress_parser.add_subparsers(dest="sub_command", help="可用命令").add_parser("plus", help="压缩拓展选项")
    compress_plus_parser.add_argument("-l", "--level", type=int, help="压缩等级0-9")
    compress_plus_parser.add_argument("-f", "--filter", type=int, help="过滤链格式")
    compress_plus_parser.add_argument("--password", type=str, help="压缩包密码")
    compress_plus_parser.add_argument("-p", "--partial", action="store_true", help="开启分片")
    compress_plus_parser.add_argument("--psize", type=str, help="分片大小")
    compress_plus_parser.add_argument("-e", "--encode", action="store_true", help="加密名字")
    compress_plus_parser.add_argument("-d", "--delete", action="store_true", help="删除源文件")
    # 创建 extract 子命令
    extract_parser = subparsers.add_parser("extract", help="解压文件")
    extract_parser.add_argument("-o", "--name", type=str, help="压缩文件名称")
    extract_parser.add_argument("-s", "--source", type=Path, required=True, help="文件来源")
    extract_parser.add_argument("-O", "--output", type=Path, help="压缩文件路径")
    extract_plus_parser = extract_parser.add_subparsers(dest="sub_command", help="可用命令").add_parser("plus", help="解压拓展选项")
    extract_plus_parser.add_argument("--password", type=str, help="压缩包密码")
    extract_plus_parser.add_argument("-d", "--delete", action="store_true", help="删除源文件")
    extract_plus_parser.add_argument("-e", "--decode", action="store_true", help="加密名字")
    return parser.parse_args(), log.success("成功！")
def __parse_args(args: argparse.Namespace) -> Result:
    config = AppConfig(
        command=args.command,
        sub_command=getattr(args, "sub_command", None), # 兼容可能没有子命令的情况
    )
    # 提取基础参数 (注意 dest 名称可能与字段名不同)
    config.base.name = args.name if args.name else AppConfig.base.name
    config.base.source_path = args.source 
    config.base.output_path = args.output if args.output else args.source.parent

    if args.command == "compress" and getattr(args, "sub_command") == "plus":
        config.compress_plus.level = args.level if 0 < args.level < 10 else CompressPlusConfig.level
        config.compress_plus.filter_choice = args.filter if 0 <= args.filter < len(filters) else CompressPlusConfig.filter_choice
        config.compress_plus.password = args.password
        config.compress_plus.if_partial = args.partial
        config.compress_plus.max_part_size = args.psize if args.psize is not None else CompressPlusConfig.max_part_size
        config.compress_plus.if_encode_name = args.encode
        config.compress_plus.if_delete_original = args.delete
    elif args.command == "extract" and getattr(args, "sub_command") == "plus":
        config.extract_plus.password = args.password
        config.extract_plus.if_delete_original = args.delete
        config.extract_plus.if_decode_name = args.decode
    else : return None, log.error("参数解析失败！")

    return config, log.success("参数获取成功！")
def __vaild_args_and_process(config: AppConfig) -> Result:
    # 命令格式校验
    mode: str | None = config.command
    if mode is None: return None, log.error("必须选择基础命令！")
    if mode != "compress" and mode != "extract":
        return None, log.error("基础命令无效！")
    plus: str | None = config.sub_command
    if plus is not None and plus != "plus": return None, log.error("拓展命令无效！")
    if_plus: bool = plus is not None
    # 通用校验
    if not config.base.source_path.exists(): return None, log.error("源文件路径不存在！")
    if not config.base.output_path or not config.base.output_path.exists(): return None, log.error("目标路径不存在！")
    if mode == "compress": # 压缩
        if not config.base.name: return None, log.error("参数name读取错误！")
        if not config.base.name.endswith(".7z"):
            config.base.name += ".7z"
        if if_plus: # 压缩拓展
            base_valid, message = seven_zip(name=config.base.name, 
                    password=config.compress_plus.password,
                    if_spit=config.compress_plus.if_partial, 
                    max_part_size=config.compress_plus.max_part_size,
                    source_path=config.base.source_path, 
                    target_path=config.base.output_path,   
                    filter_choice=config.compress_plus.filter_choice, 
                    level=config.compress_plus.level, 
                    delete_original=config.compress_plus.if_delete_original
                    )
            if not base_valid: return None, log.error(message)
            if config.compress_plus.if_encode_name:
                working_path: Path = config.base.output_path
                os.chdir(working_path)
                file_name_str_list, msg = encode.get_target_file_name_list()
                if not file_name_str_list: return None, log.error(msg)
                name_map, msg = encode.get_encode_name_map(file_name_str_list)
                if not name_map: return None, log.error(msg)
                encode.execute_rename(name_map)

        else:
            base_valid, message = base_seven_zip(name=config.base.name, source_path=config.base.source_path, target_path=config.base.output_path)
            if not base_valid: return None, log.error(message)

    else: # 解压
        if config.base.source_path.is_dir(): return None, log.error("解压源路径不能是文件夹！")
        if if_plus: # 解压拓展
            base_valid, message = seven_extract(password=config.extract_plus.password, 
                    source_path_file=config.base.source_path, 
                    target_path=config.base.output_path, 
                    if_delete_original=config.extract_plus.if_delete_original
                    )
            if config.extract_plus.if_decode_name:
                working_pathq: Path = config.base.output_path
                os.chdir(working_pathq)
                file_name_str_list, msg = encode.get_target_file_name_list()
                if not file_name_str_list: return None, log.error(msg)
                name_map, msg = encode.get_decode_name_map(file_name_str_list, TAIL_LEN, config.base.name)
                if not name_map: return None, log.error(msg)
                encode.execute_rename(name_map)
        else:
            base_valid, message = base_seven_extract(source_path_file=config.base.source_path, target_path=config.base.output_path)
            if not base_valid: return None, log.error(message)
    
    return True, log.success("成功！")



if __name__ == "__main__":
    config: Optional[AppConfig]
    config, msg = __parse_args(__input_args()[0])
    if config is None: sys.exit(1)
    if not __vaild_args_and_process(config)[0]: sys.exit(1)
