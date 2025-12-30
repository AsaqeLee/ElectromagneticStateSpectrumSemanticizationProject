"""
NPZ to CSV Converter - 将NPZ文件转换为人类可读的CSV格式
"""
import numpy as np
import csv
import sys

def convert_npz_to_csv(npz_file, output_csv, output_txt=None):
    """
    将NPZ文件转换为CSV和格式化TXT文件
    
    Args:
        npz_file: 输入的.npz文件路径
        output_csv: 输出的.csv文件路径
        output_txt: 可选的格式化.txt文件路径
    """
    
    print(f"Loading NPZ file: {npz_file}")
    
    # 加载NPZ文件
    data = np.load(npz_file)
    
    # 获取所有数组
    array_names = data.files
    print(f"Found {len(array_names)} arrays: {array_names}")
    
    # 读取数据
    arrays = {}
    for name in array_names:
        arrays[name] = data[name]
        print(f"  - {name}: shape={arrays[name].shape}, dtype={arrays[name].dtype}")
    
    data.close()
    
    # ============================================================
    # 输出1：CSV格式（Excel兼容）
    # ============================================================
    print(f"\nWriting CSV file: {output_csv}")
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # 写入表头
        header = list(arrays.keys())
        writer.writerow(header)
        
        # 写入数据行
        # 假设所有数组长度相同（或取最短长度）
        min_length = min(arr.size for arr in arrays.values())
        
        for i in range(min_length):
            row = [arrays[name].flat[i] for name in header]
            writer.writerow(row)
    
    print(f"CSV file created: {output_csv}")
    print(f"  - Rows: {min_length + 1} (1 header + {min_length} data rows)")
    print(f"  - Columns: {len(header)}")
    
    # ============================================================
    # 输出2：格式化TXT文件（可选，更易读）
    # ============================================================
    if output_txt:
        print(f"\nWriting formatted TXT file: {output_txt}")
        
        with open(output_txt, 'w', encoding='utf-8') as txtfile:
            # 文件头
            txtfile.write("=" * 80 + "\n")
            txtfile.write(f"Data Source: {npz_file}\n")
            txtfile.write("=" * 80 + "\n\n")
            
            # 统计信息
            txtfile.write("Dataset Summary:\n")
            txtfile.write("-" * 80 + "\n")
            for name in header:
                arr = arrays[name]
                txtfile.write(f"{name}:\n")
                txtfile.write(f"  Range: {arr.min():.6f} to {arr.max():.6f}\n")
                txtfile.write(f"  Mean: {arr.mean():.6f}\n")
                txtfile.write(f"  Std: {arr.std():.6f}\n")
                txtfile.write(f"  Data points: {arr.size}\n")
                txtfile.write("\n")
            
            # 数据表格
            txtfile.write("\n" + "=" * 80 + "\n")
            txtfile.write("Data Table (formatted for readability)\n")
            txtfile.write("=" * 80 + "\n\n")
            
            # 表头
            col_width = 20
            header_line = "  ".join(f"{name:>{col_width}}" for name in header)
            txtfile.write(header_line + "\n")
            txtfile.write("-" * len(header_line) + "\n")
            
            # 数据行（显示所有行）
            for i in range(min_length):
                row = [arrays[name].flat[i] for name in header]
                row_line = "  ".join(f"{val:>{col_width}.10f}" for val in row)
                txtfile.write(row_line + "\n")
            
            txtfile.write("\n" + "=" * 80 + "\n")
            txtfile.write(f"Total: {min_length} data points\n")
            txtfile.write("=" * 80 + "\n")
        
        print(f"TXT file created: {output_txt}")
    
    # ============================================================
    # 验证输出
    # ============================================================
    print("\n" + "=" * 80)
    print("Conversion completed successfully!")
    print("=" * 80)
    print(f"\nYou can now open:")
    print(f"  1. {output_csv} - with Excel, LibreOffice, or any text editor")
    if output_txt:
        print(f"  2. {output_txt} - with any text editor (formatted view)")
    print("\nData preview:")
    print(f"  First row: {[f'{arrays[name].flat[0]:.2f}' for name in header]}")
    print(f"  Last row: {[f'{arrays[name].flat[-1]:.2f}' for name in header]}")

if __name__ == "__main__":
    # 输入文件
    npz_file = "data/cli_results/composed_spectrum.npz"
    
    # 输出文件
    csv_file = "data/cli_results/composed_spectrum.csv"
    txt_file = "data/cli_results/composed_spectrum_formatted.txt"
    
    try:
        convert_npz_to_csv(npz_file, csv_file, txt_file)
        print("\nSuccess! Files are ready to open.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
