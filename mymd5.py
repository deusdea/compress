import hashlib

def get_file_md5(file_path: str | None, chunk_size:int = 8192) -> str | None:
    if not file_path: return None
    md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk_size) # 一次只读取一部分字节
                if not data: break
                md5.update(data)
        return md5.hexdigest()
    except Exception as e:
        print(f"计算失败", {e})
        return None

def md5_to_8digits(md5_hash: str | None) -> str | None:
    if not md5_hash: return None
    # 1. 将十六进制哈希转换为巨大的十进制整数
    big_int = int(md5_hash, 16)
    
    # 2. 对 1亿 (10^8) 取模，确保结果在 0 ~ 99999999 之间
    short_id = int((big_int / 1000) % 100000000)
    id_str = str(short_id)
    if len(id_str) < 8:
        id_str += '1' * (8 - len(id_str))
    return id_str
