import numpy as np
import sys

def read_and_display_npz(file_path, output_file=None):
    """读取.npz文件并以文本格式展示所有数据"""
    
    # 打开.npz文件
    data = np.load(file_path)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append(f"NPZ File: {file_path}")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # 获取文件中所有的数组名称
    array_names = data.files
    output_lines.append(f"包含 {len(array_names)} 个数组:\n")
    
    # 遍历每个数组
    for i, name in enumerate(array_names, 1):
        array = data[name]
        
        output_lines.append("-" * 80)
        output_lines.append(f"[{i}] 数组名称: {name}")
        output_lines.append("-" * 80)
        output_lines.append(f"  形状 (Shape): {array.shape}")
        output_lines.append(f"  数据类型 (Dtype): {array.dtype}")
        output_lines.append(f"  维度 (Ndim): {array.ndim}")
        output_lines.append(f"  元素总数 (Size): {array.size}")
        
        # 统计信息（仅对数值类型）
        if np.issubdtype(array.dtype, np.number):
            output_lines.append(f"  最小值 (Min): {np.min(array)}")
            output_lines.append(f"  最大值 (Max): {np.max(array)}")
            output_lines.append(f"  平均值 (Mean): {np.mean(array)}")
            output_lines.append(f"  标准差 (Std): {np.std(array)}")
        
        output_lines.append("")
        output_lines.append("  数据内容:")
        output_lines.append("")
        
        # 根据数组大小决定显示方式
        if array.size <= 50:
            # 小数组：完整显示
            output_lines.append(f"{array}")
        elif array.ndim == 1:
            # 1维大数组：显示前后各10个元素
            output_lines.append(f"  前10个元素: {array[:10]}")
            output_lines.append(f"  ...")
            output_lines.append(f"  后10个元素: {array[-10:]}")
        elif array.ndim == 2:
            # 2维大数组：显示前后各5行
            output_lines.append(f"  前5行:")
            for row in array[:5]:
                if row.size <= 10:
                    output_lines.append(f"    {row}")
                else:
                    output_lines.append(f"    [{row[0]}, {row[1]}, ..., {row[-2]}, {row[-1]}]")
            output_lines.append(f"  ...")
            output_lines.append(f"  后5行:")
            for row in array[-5:]:
                if row.size <= 10:
                    output_lines.append(f"    {row}")
                else:
                    output_lines.append(f"    [{row[0]}, {row[1]}, ..., {row[-2]}, {row[-1]}]")
        else:
            # 高维数组：只显示基本信息和部分数据
            flat = array.flatten()
            output_lines.append(f"  展平后前20个元素: {flat[:20]}")
            output_lines.append(f"  ...")
            output_lines.append(f"  展平后后20个元素: {flat[-20:]}")
        
        output_lines.append("")
    
    output_lines.append("=" * 80)
    output_lines.append("解析完成")
    output_lines.append("=" * 80)
    
    # 输出到文件或打印
    result_text = "\n".join(output_lines)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result_text)
        # Windows控制台兼容输出
        try:
            print(f"Result saved to: {output_file}")
        except:
            print("Result saved successfully")
    else:
        # 直接输出，使用兼容编码
        try:
            print(result_text)
        except UnicodeEncodeError:
            print(result_text.encode('utf-8', errors='replace').decode('utf-8'))
    
    data.close()
    return result_text

if __name__ == "__main__":
    input_file = "data/cli_results/composed_spectrum.npz"
    output_file = "data/cli_results/composed_spectrum_data.txt"
    
    try:
        read_and_display_npz(input_file, output_file)
        print("\nData parsing completed successfully")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
