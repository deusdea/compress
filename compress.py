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
import sys
# from send2trash import send2trash
import shutil
ISMAIN: bool = __name__ == "__main__"


filters: list[list[dict[str, int]]] = [[{"id": p7.FILTER_LZMA2, "preset": 7}],
                                             [{"id": p7.FILTER_ZSTD, "level": 3}]]
cwd: str = os.getcwd()
filter_level_dict: dict[str, str] = {"0": "preset", "1": "level"}

def seven_zip(name: str = "compressed", password: str = PASSWORD, 
            if_spit: bool = False, max_part_size: str = "20MB",
            source_path_str: str = cwd, target_path_str: str = cwd, 
            filter_choice:int = 0, level: int = -1, delete_original: bool = False) -> Result: 
    source_path: Path = Path(source_path_str)
    target_path: Path = Path(target_path_str)
    if not 0 <= filter_choice < len(filters):
        raise ValueError(f"输入的过滤器选择错误，请输入[0-{len(filters) - 1}]")
    if Path(name).suffix != ".7z":
        name += ".7z"
    filter: list[dict[str, int]] = filters[filter_choice]
    if 0 <= level <= 9: filters[filter_choice][0][filter_level_dict[str(filter_choice)]] = level
    
    file_list: list[Path] = []
    if source_path.is_dir(): file_list = [fp for fp in source_path.iterdir()]
    elif source_path.is_file(): file_list.append(source_path)
    if file_list == []: return None, "文件列表为空！"
    total_size: int = sum(f.stat().st_size for f in file_list)
    target_file: Path = target_path / Path(name)
    
    skip: bool = False
    if target_file.exists(): 
        log.Info("文件已经存在！跳过压缩吗？(Y/N)")
        str1 = input().strip().lower()
        skip = str1 == "y" or str1 == "yes"
    if source_path.exists() and target_path.exists() and not skip:
        log.Info("开始压缩。")
        with p7.SevenZipFile(target_file, "w", password = password, filters = filter, mp = True) as archive:
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="7z压缩中")
            for _, fp in enumerate(file_list):
                archive.write(fp)
                if delete_original: shutil.rmtree(fp)
                pbar.update(fp.stat().st_size)
            pbar.close()
    else: 
        if not source_path.exists():
            log.Error("源文件不存在！")
            return None, log.error("源文件不存在！")
        if not target_path.exists(): 
            log.Error("目标路径不存在！")
            return None, log.error("目标路径不存在！")
    log.Info("压缩完毕！")

    file_size: int = target_file.stat().st_size

   
    if(if_spit):
        data, message = get_byte_size_from_format(max_part_size)
        if not data: return (None, message)
        if math.ceil(file_size / data) > SUB_CNT_THRESHOLD: 
            log.Error("分片过小！分卷过多！")
            return (None, log.error("分片过小！分卷过多！"))
        data, _ = spilt_file(target_file, data)
        if not data: return (None, log.error(message))
        log.Info("分片完毕！")
        target_file.unlink()
    return (True, log.success("压缩成功！"))

def spilt_file(file: Path, part_byte_size: int) -> Result:
    part_num: int = 1
    base_filename: str = file.name
    width: int = math.ceil(math.log10(SUB_CNT_THRESHOLD))
    file_size: int = file.stat().st_size
    with open(file, 'rb') as source_file:
        pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc="进行分片中")
        while True:
            chunk = source_file.read(part_byte_size)
            if not chunk: break
            num_str: str = str(part_num).strip().zfill(width)
            part_filename = Path(f"{base_filename}.{num_str}")
            new_file: Path = file.parent / part_filename
            with open(new_file, 'wb') as part_file:
                part_file.write(chunk)
            part_num += 1
            pbar.update(len(chunk))
        pbar.close()
    
    return (True, log.success("分片成功！"))

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



if ISMAIN:
    parser = argparse.ArgumentParser(description="文件处理工具")
    parser.add_argument("-o", "--name", type=str, help="压缩文件名称")
    parser.add_argument("-O", "--output", type=str, help="压缩文件路径")
    parser.add_argument("-l", "--level", type=int, help="压缩等级0-9")
    parser.add_argument("-f", "--filter", type=int, help="过滤链格式")
    parser.add_argument("--password", type=int, help="压缩包密码")
    parser.add_argument("-p", "--partial", action="store_true", help="开启分片")
    parser.add_argument("--psize", type=str, help="分片大小")
    parser.add_argument("-s", "--source", type=str, help="来源路径")
    parser.add_argument("-e", "--encode_name", action="store_true", help="加密名字")
    parser.add_argument("-d", "--delete_original", action="store_true", help="删除源文件")
    args = parser.parse_args()
    log.Info(str(args))
    name: str = "compressed"
    password: str = PASSWORD
    if_spit: bool = False 
    max_part_size: str = "20MB"
    source_path_str: str = cwd
    target_path_str: str = cwd 
    filter_choice: int = 0
    level: int = -1
    delete_original: bool = False
    if args.delete_original: delete_original = True
    if args.source: 
        source_path_str = args.source
    elif not args.encode_name: log.Info("如果压缩指定来源路径或文件！")
    if args.output:
        target_path_str = args.output
    else: target_path_str = source_path_str
    if args.name:
        name = args.name
    if args.partial:
        if_spit = True
        if args.psize:
            max_part_size = args.psize
    if args.filter:
        filter_choice = args.filter
    if args.password:
        password = args.password
    if args.level:
        level = args.level
    
    if args.source: seven_zip(name, password, if_spit, max_part_size, source_path_str, target_path_str, filter_choice, level)
    if args.encode_name: 
        os.chdir(target_path_str)
        encode.auto_ed_code(math.ceil(math.log10(SUB_CNT_THRESHOLD)))