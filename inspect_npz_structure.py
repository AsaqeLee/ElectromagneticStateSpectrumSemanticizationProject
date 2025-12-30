"""
NPZ格式深度剖析 - 揭示内部结构
"""
import zipfile
import numpy as np
import os
import struct

def inspect_npz_internal_structure(npz_file):
    """深度剖析NPZ文件的内部结构"""
    
    print("=" * 80)
    print(f"NPZ INTERNAL STRUCTURE ANALYSIS: {npz_file}")
    print("=" * 80)
    print()
    
    # ============================================================
    # 第一层：ZIP容器分析
    # ============================================================
    print("[LAYER 1] ZIP Container Analysis")
    print("-" * 80)
    
    with zipfile.ZipFile(npz_file, 'r') as zf:
        print(f"Compression Type: ZIP (standard ZIP archive)")
        print(f"Total entries: {len(zf.namelist())}")
        print()
        
        for i, name in enumerate(zf.namelist(), 1):
            info = zf.getinfo(name)
            print(f"  [{i}] Entry Name: {name}")
            print(f"      - Compressed Size: {info.compress_size} bytes")
            print(f"      - Uncompressed Size: {info.file_size} bytes")
            print(f"      - Compression Ratio: {info.compress_size/info.file_size*100:.2f}%")
            print(f"      - CRC32: {info.CRC}")
            print()
    
    # ============================================================
    # 第二层：NPY文件格式分析
    # ============================================================
    print("[LAYER 2] NPY File Format Analysis")
    print("-" * 80)
    
    with zipfile.ZipFile(npz_file, 'r') as zf:
        for name in zf.namelist():
            print(f"\nAnalyzing: {name}")
            print("~" * 40)
            
            # 读取原始字节
            npy_bytes = zf.read(name)
            print(f"Total bytes: {len(npy_bytes)}")
            
            # NPY文件格式解析
            # 参考: https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html
            
            # Magic number (前6字节)
            magic = npy_bytes[:6]
            print(f"\n[NPY Header]")
            print(f"  Magic Number: {magic} (hex: {magic.hex()})")
            
            # Version (第7-8字节)
            version = (npy_bytes[6], npy_bytes[7])
            print(f"  Format Version: {version[0]}.{version[1]}")
            
            # Header length (根据版本不同)
            if version == (1, 0):
                header_len = struct.unpack('<H', npy_bytes[8:10])[0]
                header_start = 10
            else:  # version >= (2, 0)
                header_len = struct.unpack('<I', npy_bytes[8:12])[0]
                header_start = 12
            
            print(f"  Header Length: {header_len} bytes")
            
            # Header内容 (Python字典字符串)
            header_bytes = npy_bytes[header_start:header_start+header_len]
            header_str = header_bytes.decode('latin1').rstrip('\n ')
            print(f"  Header Content: {header_str}")
            
            # 解析header字典
            header_dict = eval(header_str)
            print(f"\n[Parsed Metadata]")
            print(f"  dtype: {header_dict['descr']}")
            print(f"  fortran_order: {header_dict['fortran_order']}")
            print(f"  shape: {header_dict['shape']}")
            
            # 数据部分
            data_start = header_start + header_len
            data_bytes = npy_bytes[data_start:]
            print(f"\n[Data Section]")
            print(f"  Data offset: {data_start} bytes")
            print(f"  Data size: {len(data_bytes)} bytes")
            
            # 计算元素数量
            total_elements = 1
            for dim in header_dict['shape']:
                total_elements *= dim
            
            dtype_size = np.dtype(header_dict['descr']).itemsize
            print(f"  Elements: {total_elements}")
            print(f"  Element size: {dtype_size} bytes")
            print(f"  Expected size: {total_elements * dtype_size} bytes")
            match_status = "YES" if len(data_bytes) == total_elements * dtype_size else "NO"
            print(f"  Match: {match_status}")
            
            # 显示前几个字节（原始二进制）
            print(f"\n[Raw Data Preview - First 64 bytes]")
            hex_str = data_bytes[:64].hex()
            for i in range(0, len(hex_str), 32):
                print(f"  {hex_str[i:i+32]}")
            
    # ============================================================
    # 第三层：与NumPy加载的对比
    # ============================================================
    print("\n" + "=" * 80)
    print("[LAYER 3] NumPy Load Verification")
    print("-" * 80)
    
    data = np.load(npz_file)
    for name in data.files:
        array = data[name]
        print(f"\n{name}:")
        print(f"  Shape: {array.shape}")
        print(f"  Dtype: {array.dtype}")
        print(f"  Size: {array.size} elements")
        print(f"  Memory: {array.nbytes} bytes")
        print(f"  First 5 values: {array.flat[:5]}")
        print(f"  Last 5 values: {array.flat[-5:]}")
    
    data.close()
    
    # ============================================================
    # 总结
    # ============================================================
    print("\n" + "=" * 80)
    print("[SUMMARY] NPZ Format Structure")
    print("""
NPZ Structure (Layered View):

Layer 1: ZIP Container
  +- Standard ZIP compression (RFC 1950/1951)
  +- Multiple entries (one per array)

Layer 2: NPY File Format (per entry)
  +- Magic Number: \\x93NUMPY (6 bytes)
  +- Version: Major.Minor (2 bytes)
  +- Header Length: uint16 or uint32 (2 or 4 bytes)
  +- Header Dict: Python literal string
  |   +- Contains: dtype, shape, fortran_order
  +- Data Section: Raw binary array data
      +- C-contiguous or Fortran-contiguous layout

Key Design Principles:
  1. **Simplicity**: Just ZIP + NPY, nothing fancy
  2. **Portability**: Standard formats, cross-platform
  3. **Efficiency**: Minimal overhead, direct memory mapping
  4. **Extensibility**: Dictionary-based metadata
  5. **Self-describing**: All info in file, no external schema

Why This Design?
  - "Good taste": Reuse existing formats (ZIP, Python dicts)
  - "Pragmatic": Solves real problem (multiple arrays in one file)
  - "No special cases": Each array is independent NPY
  - "Never break userspace": Backward compatible, versioned
    """)
    print("=" * 80)

if __name__ == "__main__":
    npz_file = "output/union_spectrum.npz"
    inspect_npz_internal_structure(npz_file)
