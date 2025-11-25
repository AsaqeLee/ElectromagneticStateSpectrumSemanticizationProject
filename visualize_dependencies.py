#!/usr/bin/env python3
"""
依赖关系可视化工具
基于生成的dependency_graph.json创建可视化图表
"""

import json
import sys
import io
from pathlib import Path
from collections import defaultdict

# 修复Windows控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def load_dependency_graph(json_path: Path):
    """加载依赖图JSON文件"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_mermaid_diagram(graph):
    """生成Mermaid流程图代码"""
    lines = []
    lines.append("```mermaid")
    lines.append("graph TB")
    lines.append("")
    
    # 按模块分组节点
    modules = defaultdict(list)
    for node in graph['nodes']:
        module = node['module']
        modules[module].append(node)
    
    # 定义节点样式
    lines.append("    %% 定义样式")
    lines.append("    classDef coreStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px")
    lines.append("    classDef ioStyle fill:#f3e5f5,stroke:#4a148c,stroke-width:2px")
    lines.append("    classDef signalStyle fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px")
    lines.append("    classDef semanticsStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px")
    lines.append("    classDef pipelineStyle fill:#fce4ec,stroke:#880e4f,stroke-width:2px")
    lines.append("    classDef vizStyle fill:#f1f8e9,stroke:#33691e,stroke-width:2px")
    lines.append("    classDef scriptStyle fill:#eceff1,stroke:#263238,stroke-width:2px")
    lines.append("")
    
    # 为每个模块创建子图（示例）
    # 由于Mermaid子图限制，我们简化为直接展示节点
    
    # 生成核心模块节点
    lines.append("    %% 核心模块 (Layer 0)")
    if 'core' in modules:
        for node in modules['core']:
            node_id = node['id'].replace('\\', '_').replace('.py', '')
            node_label = node['label'].replace('.py', '')
            lines.append(f"    {node_id}[{node_label}]:::coreStyle")
    lines.append("")
    
    # 生成功能层模块节点
    lines.append("    %% 功能层模块 (Layer 1)")
    for mod_name in ['io', 'signal', 'semantics']:
        if mod_name in modules:
            for node in modules[mod_name]:
                node_id = node['id'].replace('\\', '_').replace('.py', '')
                node_label = node['label'].replace('.py', '')
                style = f"{mod_name}Style"
                lines.append(f"    {node_id}[{node_label}]:::{style}")
    lines.append("")
    
    # 生成pipeline层节点
    lines.append("    %% Pipeline层 (Layer 2)")
    if 'pipeline' in modules:
        for node in modules['pipeline'][:5]:  # 限制数量避免图太复杂
            node_id = node['id'].replace('\\', '_').replace('.py', '')
            node_label = node['label'].replace('.py', '')
            lines.append(f"    {node_id}[{node_label}]:::pipelineStyle")
        if len(modules['pipeline']) > 5:
            lines.append(f"    pipeline_more[...more pipeline files]:::pipelineStyle")
    lines.append("")
    
    # 生成CLI脚本节点
    lines.append("    %% CLI应用层 (Layer 3)")
    if 'script' in modules:
        for node in modules['script'][:3]:  # 限制数量
            if 'spectrum' in node['id'] or 'demo' in node['id']:
                node_id = node['id'].replace('\\', '_').replace('.py', '')
                node_label = node['label'].replace('.py', '')
                lines.append(f"    {node_id}[{node_label}]:::scriptStyle")
    lines.append("")
    
    # 添加一些关键依赖关系边
    lines.append("    %% 关键依赖关系")
    
    # 示例：core -> 其他模块
    if 'core' in modules:
        core_nodes = [n['id'].replace('\\', '_').replace('.py', '') for n in modules['core']]
        if 'io' in modules:
            io_node = modules['io'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {core_nodes[0]} --> {io_node}")
        if 'signal' in modules:
            signal_node = modules['signal'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {core_nodes[0]} --> {signal_node}")
        if 'semantics' in modules:
            sem_node = modules['semantics'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {core_nodes[0]} --> {sem_node}")
    
    # 功能层 -> pipeline
    if 'pipeline' in modules and len(modules['pipeline']) > 0:
        pipeline_node = modules['pipeline'][0]['id'].replace('\\', '_').replace('.py', '')
        if 'signal' in modules:
            signal_node = modules['signal'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {signal_node} --> {pipeline_node}")
        if 'semantics' in modules:
            sem_node = modules['semantics'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {sem_node} --> {pipeline_node}")
    
    # pipeline -> CLI
    if 'script' in modules and 'pipeline' in modules:
        cli_nodes = [n for n in modules['script'] if 'spectrum' in n['id']]
        if cli_nodes and modules['pipeline']:
            cli_node = cli_nodes[0]['id'].replace('\\', '_').replace('.py', '')
            pipeline_node = modules['pipeline'][0]['id'].replace('\\', '_').replace('.py', '')
            lines.append(f"    {pipeline_node} --> {cli_node}")
    
    lines.append("```")
    
    return '\n'.join(lines)


def generate_module_summary(graph):
    """生成模块统计摘要"""
    modules = defaultdict(int)
    for node in graph['nodes']:
        modules[node['module']] += 1
    
    lines = []
    lines.append("\n## 模块文件统计\n")
    lines.append("| 模块 | 文件数 | 说明 |")
    lines.append("|------|--------|------|")
    
    module_desc = {
        'core': '核心数据结构与配置',
        'io': 'IO文件读写',
        'signal': '信号处理与频谱分析',
        'semantics': '语义编码解码',
        'pipeline': '任务流水线编排',
        'visualization': '可视化工具',
        'viz': '绘图辅助',
        'script': 'CLI脚本与工具',
        'root': '项目根目录'
    }
    
    for module in sorted(modules.keys()):
        count = modules[module]
        desc = module_desc.get(module, '')
        lines.append(f"| {module} | {count} | {desc} |")
    
    lines.append(f"\n**总计**: {sum(modules.values())} 个Python文件\n")
    
    return '\n'.join(lines)


def main():
    """主函数"""
    json_path = Path("docs/dependency_graph.json")
    
    if not json_path.exists():
        print(f"❌ 找不到依赖图文件: {json_path}")
        print("请先运行 analyze_dependencies.py 生成依赖图数据")
        return
    
    print(f"正在加载依赖图: {json_path}")
    graph = load_dependency_graph(json_path)
    
    print(f"节点数: {len(graph['nodes'])}")
    print(f"边数: {len(graph['edges'])}")
    
    # 生成Mermaid图表
    print("\n生成Mermaid流程图...")
    mermaid_diagram = generate_mermaid_diagram(graph)
    
    # 生成模块统计
    module_summary = generate_module_summary(graph)
    
    # 追加到报告文件
    report_path = Path("docs/电磁态频谱语义化工程-代码依赖关系分析报告.md")
    
    with open(report_path, 'a', encoding='utf-8') as f:
        f.write("\n\n---\n\n")
        f.write("## 8. 依赖关系可视化\n\n")
        f.write("### 8.1 模块层次依赖图\n\n")
        f.write(mermaid_diagram)
        f.write("\n\n")
        f.write(module_summary)
    
    print(f"\n✅ 可视化图表已追加到: {report_path}")
    
    # 输出简化的文本依赖树
    print("\n" + "="*60)
    print("📊 项目依赖层次结构:")
    print("="*60)
    print("""
Layer 0 (基础层)
    └── src/core/
        ├── schemas.py          (28个文件依赖)
        └── config.py

Layer 1 (功能层)
    ├── src/io/
    │   └── reader.py           (文件读取)
    ├── src/signal/
    │   ├── jammers.py          (干扰信号生成)
    │   ├── spectrum.py         (频谱计算)
    │   ├── stitcher.py         (频谱拼接)
    │   └── spectrum_composer.py (频谱合成)
    └── src/semantics/
        ├── decode.py           (v1解码)
        ├── decode_multi.py     (多区域解码)
        └── decode_v2.py        (v2解码)

Layer 2 (编排层)
    └── src/pipeline/
        ├── compose_spectrum.py  (任务一)
        ├── stitch_*.py         (任务二)
        └── semantic_eval*.py   (任务三)

Layer 3 (应用层)
    ├── spectrum_cli.py         (交互式CLI)
    ├── spectrum_batch.py       (批处理CLI)
    └── demo_*.py               (演示脚本)
    """)
    
    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
