#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unity_video_extract.py
专门针对 Unity 视频资源优化的提取工具，确保视频文件完整性。
适用于 Termux（Android）上的 Python 环境。
"""

import os
import sys
import argparse
import struct
from pathlib import Path

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def safe_print(*args, **kwargs):
    print(*args, **kwargs, flush=True)

def parse_mp4_atoms(data, start_pos=0):
    """解析 MP4 原子结构，找到完整的视频文件"""
    atoms = []
    pos = start_pos
    
    while pos < len(data) - 8:  # 至少需要8字节来读取原子头
        # 读取原子大小和类型（大端）
        if pos + 8 > len(data):
            break
            
        atom_size = struct.unpack('>I', data[pos:pos+4])[0]
        atom_type = data[pos+4:pos+8]
        
        # 验证原子大小合理性
        if atom_size < 8 or atom_size > len(data) - pos:
            break
            
        atoms.append((atom_type, pos, atom_size))
        
        # 移动到下一个原子
        pos += atom_size
    
    return atoms

def extract_mp4_video(data, start_pos):
    """从指定位置提取完整的 MP4 视频文件"""
    try:
        # 解析 MP4 原子结构
        atoms = parse_mp4_atoms(data, start_pos)
        
        if not atoms:
            return None
        
        # 查找重要的原子来确定视频范围
        moov_pos = None
        mdat_pos = None
        
        for atom_type, pos, size in atoms:
            if atom_type == b'moov':
                moov_pos = pos
            elif atom_type == b'mdat':
                mdat_pos = pos
        
        # 如果有 moov 原子，尝试找到完整的文件范围
        if moov_pos is not None:
            # 找到最后一个原子的结束位置
            last_atom = atoms[-1]
            end_pos = last_atom[1] + last_atom[2]
            
            # 提取完整的 MP4 文件
            video_data = data[start_pos:end_pos]
            
            # 验证文件头
            if video_data.startswith(b'ftyp'):
                return video_data
        
        # 如果没有找到完整的结构，尝试提取一定大小的数据
        # MP4 文件通常至少有几个关键原子
        if len(data) - start_pos > 1000:  # 至少1KB
            # 尝试提取最多100MB的数据
            end_pos = min(start_pos + 100 * 1024 * 1024, len(data))
            video_data = data[start_pos:end_pos]
            
            # 验证是否包含关键原子
            if b'moov' in video_data or b'mdat' in video_data:
                return video_data
        
        return None
        
    except Exception as e:
        safe_print(f"MP4 提取错误: {e}")
        return None

def extract_unity_videos(file_path, output_dir):
    """专门提取 Unity 中的视频资源"""
    try:
        safe_print(f"提取视频资源: {os.path.basename(file_path)}")
        
        # 创建输出目录
        file_name = Path(file_path).stem
        file_output_dir = os.path.join(output_dir, file_name + "_videos")
        ensure_dir(file_output_dir)
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        extracted_count = 0
        
        # 查找所有可能的 MP4 文件起始位置
        pos = 0
        video_index = 0
        
        while True:
            # 查找 ftyp 原子（MP4 文件开始）
            pos = content.find(b'ftyp', pos)
            if pos == -1:
                break
            
            # ftyp 原子应该至少在前面有4字节的大小字段
            if pos < 4:
                pos += 1
                continue
            
            # 检查是否真的是 MP4 文件头
            start_pos = pos - 4
            if start_pos < 0:
                pos += 1
                continue
            
            # 尝试提取完整的 MP4 文件
            video_data = extract_mp4_video(content, start_pos)
            
            if video_data and len(video_data) > 1000:  # 至少1KB
                # 保存视频文件
                video_path = os.path.join(file_output_dir, f"video_{video_index}.mp4")
                with open(video_path, 'wb') as f:
                    f.write(video_data)
                
                safe_print(f"  提取视频: video_{video_index}.mp4 ({len(video_data)} 字节)")
                extracted_count += 1
                video_index += 1
            
            # 移动到下一个可能的位置
            pos += 4
        
        return extracted_count
        
    except Exception as e:
        safe_print(f"视频提取失败: {e}")
        return 0

def extract_unitypy_videos(file_path, output_dir):
    """使用 UnityPy 提取视频资源"""
    try:
        import UnityPy
        
        safe_print(f"使用 UnityPy 提取视频: {os.path.basename(file_path)}")
        
        # 创建输出目录
        file_name = Path(file_path).stem
        file_output_dir = os.path.join(output_dir, file_name + "_unitypy_videos")
        ensure_dir(file_output_dir)
        
        # 加载 Unity 环境
        env = UnityPy.load(file_path)
        
        # 获取所有对象
        objects = list(env.objects)
        safe_print(f"  找到 {len(objects)} 个对象")
        
        extracted_count = 0
        
        # 提取每个对象
        for i, obj in enumerate(objects):
            try:
                # 获取对象类型
                obj_type = obj.type.name if hasattr(obj, 'type') and hasattr(obj.type, 'name') else "Unknown"
                
                # 只处理视频相关类型
                if obj_type not in ["VideoClip", "MovieTexture"]:
                    continue
                
                # 尝试读取对象数据
                data = obj.read()
                
                # 尝试提取视频数据
                raw_data = None
                
                # 尝试不同的属性名
                for attr in ['m_VideoData', 'm_MovieData', 'data', 'bytes', 'm_Data']:
                    if hasattr(data, attr):
                        candidate = getattr(data, attr)
                        if isinstance(candidate, (bytes, bytearray)):
                            raw_data = candidate
                            break
                        elif hasattr(candidate, 'read'):
                            try:
                                candidate.seek(0)
                                raw_data = candidate.read()
                                break
                            except:
                                pass
                
                if raw_data and len(raw_data) > 1000:
                    # 检查是否是有效的 MP4 文件
                    if raw_data.startswith(b'ftyp'):
                        ext = '.mp4'
                    else:
                        # 尝试在数据中查找 MP4 文件头
                        ftyp_pos = raw_data.find(b'ftyp')
                        if ftyp_pos != -1 and ftyp_pos >= 4:
                            # 提取从 ftyp 开始的数据
                            start_pos = ftyp_pos - 4
                            video_data = extract_mp4_video(raw_data, start_pos)
                            if video_data:
                                raw_data = video_data
                                ext = '.mp4'
                            else:
                                ext = '.bin'
                        else:
                            ext = '.bin'
                    
                    if ext == '.mp4':
                        video_path = os.path.join(file_output_dir, f"unitypy_{obj_type}_{i}.mp4")
                        with open(video_path, 'wb') as f:
                            f.write(raw_data)
                        
                        extracted_count += 1
                        safe_print(f"  提取视频: unitypy_{obj_type}_{i}.mp4")
                
            except Exception as e:
                # 忽略单个对象的错误
                continue
        
        return extracted_count
        
    except Exception as e:
        safe_print(f"UnityPy 视频提取失败: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Unity 视频资源专门提取工具")
    parser.add_argument("--input", "-i", required=True, help="Unity 游戏的 Data 目录或资源文件")
    parser.add_argument("--out", "-o", required=True, help="输出目录")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.out
    
    if not os.path.exists(input_path):
        safe_print(f"错误: 输入路径不存在: {input_path}")
        sys.exit(1)
    
    ensure_dir(output_path)
    
    # 收集目标文件
    if os.path.isfile(input_path):
        files = [input_path]
    else:
        files = []
        for root, _, filenames in os.walk(input_path):
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                files.append(os.path.join(root, filename))
    
    safe_print(f"找到 {len(files)} 个文件")
    
    total_extracted = 0
    
    for i, file_path in enumerate(files, 1):
        file_size = os.path.getsize(file_path)
        safe_print(f"处理文件 {i}/{len(files)}: {os.path.basename(file_path)} ({file_size} 字节)")
        
        # 首先尝试使用 UnityPy 提取
        extracted = extract_unitypy_videos(file_path, output_path)
        
        # 如果 UnityPy 没有提取到视频，尝试二进制提取
        if extracted == 0:
            extracted = extract_unity_videos(file_path, output_path)
        
        total_extracted += extracted
        safe_print(f"  该文件提取了 {extracted} 个视频")
    
    safe_print(f"视频提取完成！共提取 {total_extracted} 个视频文件。")
    safe_print(f"输出目录: {output_path}")

if __name__ == "__main__":
    main()