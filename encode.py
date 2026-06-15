import os
import re
import random
from pathlib import Path
import string
import sys
import uuid
from mymd5 import *
from constants import *
from typing import Any, Optional
ISMAIN: bool = __name__ == "__main__"
archive_exts = ('.zip', '.rar', '.7z', '.tar.gz', '.gz', '.bz2', '.xz')
def confirm_pause():
    confirm = input("\n⚠️ 确认继续执行吗？(请输入 yes 继续): ").strip().lower()
    if confirm != 'yes': print("已取消操作。\n"); return False
    return True

def get_anchor_info_for_encode_name(file_list: list[str]) -> Result:
    """找到最小的文件，并提取其大小(MB取整)和日期"""
    if not file_list: return (None, "未找到任何符合格式的文件")
    
    # 找出文件大小最小的那个
    min_file_name: str | None = min(file_list, key=os.path.getsize)
    if not min_file_name: return (None, "未找到任何符合格式的文件")
    min_size: int = os.path.getsize(min_file_name)
    size_mb: str = str(int(os.path.getsize(min_file_name) / (1024 * 1024)))

    # 检查是否有多个文件大小等于最小值
    if sum(1 for f in file_list if os.path.getsize(f) == min_size) > 1:
        print("⚠️ 错误：检测到多个大小相同的文件，当前不支持此操作！")
        return None, "暂时不支持！"

    # 提取前缀
    match = re.search(r'(.*?)\.',  Path(min_file_name).name)
    if not match: return None, "前缀匹配失败！"
    prefix_match: str = match.group(1)
    date_string = md5_to_8digits(get_file_md5(min_file_name))
    if not date_string: return None, "文件MD5计算失败！"
    
    print(f"[INFO] 锚点文件(最小): {min_file_name}")
    print(f"[INFO] 提取参数: Prefix={prefix_match}, Date={date_string}, Size_MB={size_mb}\n")
    return {"file": min_file_name, "date": date_string, "size_mb": size_mb, "prefix": prefix_match}, ""

def format_key_string(origin_name: str, target_len: int) -> str:
    s = str(origin_name)
    while len(s) < target_len:
        insert_pos = random.randint(0, len(s))
        rand_char = random.choice(string.ascii_letters)
        s = s[:insert_pos] + rand_char + s[insert_pos:]
    return s

def get_dynamic_key(md5_num: int, mb_size: int) -> int:
    return (md5_num * 31) ^ (mb_size * 17)

def get_random_charset_string(len: int) -> str:
    return ''.join(random.choice(string.ascii_letters) for _ in range(len))

def process_new_name(file_list: list[str], anchor: dict[str, str]) -> Result:
    dynamic_key = get_dynamic_key(int(anchor["date"]), int(anchor["size_mb"]))
    anchor_file_string = anchor["file"]
    rename_map: dict[str, Any] = {}
    # 处理名字
    print("加密映射列表为：")
    for i, f in enumerate(file_list, 1):
        match = re.search(r"(.*?)\.(.*?)\.(\d+)", f)
        prefix_len = 10 + random.randint(0, 10)
    
        if not match: return (None, "匹配发生错误！")
        _, _, suffix_num = match.groups()
       
        index = int(suffix_num)
        # 核心判断：是否为最小文件（即锚点文件本身）
        if f == anchor_file_string:
            
            new_name = f"{get_random_charset_string(prefix_len)}"
        else:
            raw_key = dynamic_key ^ index
            formatted_key_string = format_key_string(str(raw_key), prefix_len)
            # 拼接新文件名: newKeyx.dd.尾数
            new_name = f"{formatted_key_string}"

        rename_map[f] = new_name.strip()
        print(f"{i}. {f}  ➡️  {new_name}")
    return (rename_map, "")


def execute_rename(rename_map: dict[str, str]) -> None:
    # ========== 阶段 0：事务预检 (Dry Run) ==========
    print("\n🔍 [事务预检] 正在检查目标环境...")
    existing_files = set(os.listdir('.'))  # 获取当前目录所有文件
    
    for old_name, new_name in rename_map.items():
        # 1. 检查源文件是否存在
        if old_name not in existing_files:
            print(f"❌ 预检失败: 源文件 [{old_name}] 不存在！事务已中止。")
            return
        
        # 2. 检查新文件名是否已存在（防止覆盖）
        if new_name in existing_files and new_name != old_name:
            print(f"❌ 预检失败: 目标文件 [{new_name}] 已存在！事务已中止。")
            return
            
    print("✅ 预检通过：未发现冲突，准备执行事务...\n")

    # ========== 阶段 1：批量转入临时状态 ==========
    temp_map: dict[str, dict[str, str]] = {}
    print("⏳ [步骤 1/2] 正在安全转移至临时状态...")
    try:
        for old_name, new_name in rename_map.items():
            temp_name = f"_tmp_{uuid.uuid4().hex}_{old_name}"
            os.rename(old_name, temp_name)
            temp_map[temp_name] = {"old_name": old_name, "new_name": new_name}
    except Exception as e:
        print(f"❌ 阶段1异常中断: {e}")
        print("🔄 正在紧急回滚已修改的文件...")
        
        # 现在遍历出来的 info 是一个包含新旧名字的字典
        for tmp, info in temp_map.items():
            try: 
                os.rename(tmp, info["old_name"])  # 完美！精准还原到最初的旧名字
            except: 
                pass
                
        print("⚠️ 事务已回滚，未造成数据损坏。")
        return

    # ========== 阶段 2：完成最终重命名 ==========
    print("⏳ [步骤 2/2] 正在应用最终名称...")
    success_count = 0
    for temp_name, info in temp_map.items():
        final_name = info["new_name"]
        try: 
            os.rename(temp_name, final_name)
            print(f"✅ OK: {final_name}")
            success_count += 1
        except FileExistsError: 
            print(f"❌ 致命冲突: {final_name} 在执行期间被外部创建！")
        except Exception as e: 
            print(f"❌ 阶段2失败: {e}")

    print(f"\n🎉 事务提交成功！共处理 {success_count}/{len(rename_map)} 个文件。\n")

def get_target_file_name_list(current_dir: str = "") -> Result:
    # todo完全路径校验
    if current_dir == "": current_dir = os.getcwd()
    current_path = Path(current_dir)
    oper_type: str = "encode"
    file_list = [
        f.name for f in current_path.iterdir() 
        if f.is_file() and re.search(r".*\..*\.\d+", f.name)
    ]
    if not file_list: 
        file_list = [f.name for f in current_path.iterdir() 
                                   if f.is_file() and re.search(r"^([0-9a-zA-Z]*?)$", f.name) != None]
        oper_type = "decode"
    if not file_list: return None, "未找到任何文件！"
    return file_list, oper_type

def get_anchor_info_for_decode_name(file_name_list: list[str]) -> Result:
    if not file_name_list: return None, "未找到任何符合格式的文件"
    # 找出文件大小最小的那个
    min_file = min(file_name_list, key=os.path.getsize)
    min_size = os.path.getsize(min_file)
    size_mb = int(os.path.getsize(min_file) / (1024 * 1024))

    # 检查是否有多个文件大小等于最小值
    if sum(1 for f in file_name_list if os.path.getsize(f) == min_size) > 1:
        print("⚠️ 错误：检测到多个大小相同的文件，当前不支持此操作！")
        return None, "暂时不支持！"
    # min_file = file_name_list[7]
    # size_mb = 167
    # 提取前缀
    match = re.search('(.*)', min_file)
    if not match: return None, "无法提取文件前缀！"
    prefix_string: str = match.group(1)
    # 提取8位日期（从索引1开始，每隔1个取一个，直到凑够16个字符的长度）
    # date_string = prefix_string[1:16:2] 
    date_string = md5_to_8digits(get_file_md5(min_file))
    print(f"[INFO] 锚点文件(最小): {min_file}")
    print(f"[INFO] 提取参数: Prefix={prefix_string}, Date={date_string}, Size_MB={size_mb}\n")
    return {"file": min_file, "date": date_string, "size_mb": size_mb, "prefix": prefix_string}, ""



def recovery_name(file_list: list[str], anchor: dict[str, str], ext: str = ".7z", base_name: str = "compressed", tail_len: int = 3) -> Result:
    dynamic_key = get_dynamic_key(int(anchor["date"]), int(anchor["size_mb"]))
    anchor_file_string = anchor["file"]
    
    rename_map: dict[str, str] = {}
    print("解密映射列表为：")
    for i, f in enumerate(file_list):
        match = re.search("(.*)", f)
        if not match: return None, "无法提取文件前缀！"
        file_prefix_string = match.group(1)
        if f == anchor_file_string:
            file_recovery_name = f"{base_name}{ext}.{str(len(file_list)).zfill(tail_len)}"
        else: 
            # 提取数据
            encode_string = re.sub(r'[^\d]', '', file_prefix_string)
            encode_num = int(encode_string)
            decode_num = dynamic_key ^ encode_num
            file_recovery_name = f"{base_name}{ext}.{str(decode_num).zfill(tail_len)}"
        rename_map[f] = file_recovery_name.strip()
        print(f"{i}. {f}  ➡️  {file_recovery_name}")
    return (rename_map, "")

    
def check_operation(file_list: list[str], oper_type: str) -> Result:
    if not file_list:
        return None, "文件列表为空！"
    if oper_type != "encode" and oper_type != "decode":
        return None, "类型非法"
    
    # 假设 ext_len_num = 2 (对应 7z)
    base_names: set[str] = set()
    for f in file_list:
        if oper_type == "encode":
            match_encode = re.search(r'(.+)(\..+)\.(\d+)', f)
            if not match_encode: return None, "无法提取文件前缀！"
            prefix, ext, _ = match_encode.groups() 
            # 将 '前缀' + '.' + '扩展名' 组合成基础文件名
            base_names.add(f"{prefix}{ext}")
        else:
            body = f
            base_names.add(f"{len(body)}")
    # 核心判断逻辑：
    # 如果集合的长度为 1，说明为有效文件
    if len(base_names) != 1:
        if oper_type == "encode": return False, f"发现不符合格式的文件"
    if oper_type == "decode" and len(base_names) != 0:
        return True, ""
    return True, ""

def get_encode_name_map(file_list: list[str]) -> Result: 
    data, msg = get_anchor_info_for_encode_name(file_list)
    if not data: print(msg);  return data, msg
    if ISMAIN:
        print(f"[Info] anchor文件名称为: {data}")
    name_map, msg = process_new_name(file_list, data)
    if not name_map: print(msg);  return name_map, msg
    return name_map, ""

def get_decode_name_map(file_list: list[str], tail_len: int = 3, name: Optional[str] = None) -> Result:
    data, msg = get_anchor_info_for_decode_name(file_list)
    if not data: print(msg);  return data, msg
    ext = ".7z"
    if ISMAIN:
        ext_chose = input("分卷压缩的格式是？1.7z 2.zip 3.其他 , 请输入：").strip()
        if ext_chose == "2":
            ext = "zip"
        elif ext_chose == "3":
            ext = input("输入后缀：")
    base_name: str = "compressed"
    if name: base_name = name
    if ISMAIN:
        base_name_choice = input("\n⚠️需要自定义前缀吗？(请输入 yes 继续否则跳过): ").strip().lower()
        if base_name_choice == "yes" or base_name_choice == "y":
            base_name = input("输入前缀：")
        
    if ISMAIN:
        print(f"[Info] anchor文件名称为: {data}")
    name_map, msg = recovery_name(file_list, data, ext, base_name, tail_len)
    if not name_map: print(msg);  return name_map, msg
    return name_map, ""


def print_list(list: list[Any]):
    for i, e in enumerate(list, 1):
        print(i, e)

def auto_ed_code(tail_len: int) -> None:
    file_list, oper_type = get_target_file_name_list()
    isEncodeOperation, msg = check_operation(file_list, oper_type)
    if not isEncodeOperation: print(msg); sys.exit(1)
    res: dict[str, str] = {}
    if isEncodeOperation != None: 
        print("[Info] 文件验证成功！")
        if oper_type == "encode":
            print(f"加密文件列表为:")
            print_list(file_list)
            if ISMAIN and not confirm_pause(): sys.exit(1)
            print("开始加密！")
            res, msg = get_encode_name_map(file_list)
            if not res: print(msg);  sys.exit(1)
        elif oper_type == "decode":
            print(f"解密文件列表为:")
            print_list(file_list)    
            if ISMAIN and not confirm_pause(): sys.exit(1)
            print("开始解密！")
            res, msg = get_decode_name_map(file_list, tail_len)
            if not res: print(msg);  sys.exit(1)
        print("即将进行文件的修改。")
        if ISMAIN and  not confirm_pause(): sys.exit(1)
        execute_rename(res)
        sys.exit(0)
    sys.exit(1)


if ISMAIN:
    auto_ed_code(3)
