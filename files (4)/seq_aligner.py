#!/usr/bin/env python3
"""
序列比对工具 - 命令行交互版本 v4.1
适用于 WSL2 环境，支持 Windows 路径
"""

import os
import subprocess
import tempfile
import glob
import sys
import tty
import termios
from datetime import datetime

DEFAULT_OUTPUT_DIR = "/mnt/c/Users/u0184116/OneDrive - mails.ucas.ac.cn/文档/KUL/Align"

def get_key():
    fd = sys.stdin. fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            ch3 = sys. stdin.read(1)
            if ch2 == '[':
                if ch3 == 'A': return 'UP'
                elif ch3 == 'B': return 'DOWN'
        elif ch == '\r' or ch == '\n':
            return 'ENTER'
        elif ch == ' ':
            return 'SPACE'
        elif ch. lower() in ['a', 'n', 'q', 'd']:
            return ch.upper()
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class SequenceAligner:
    def __init__(self):
        self.sequences = {}
        self.loaded_files = []
        self.last_result = None
        self.last_result_file = None
        
        if os.path.isdir(DEFAULT_OUTPUT_DIR):
            self.output_dir = DEFAULT_OUTPUT_DIR
        else:
            try:
                os. makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
                self. output_dir = DEFAULT_OUTPUT_DIR
            except:
                self.output_dir = os.getcwd()
        
        self.available_tools = self.detect_tools()
        self. pymsaviz_available = self.check_pymsaviz()
        
    def check_pymsaviz(self):
        try:
            import pymsaviz
            return True
        except ImportError:
            return False
    
    def detect_tools(self):
        tools = {}
        for tool, cmd in [('mafft', ['mafft', '--version']), 
                          ('clustalw', ['clustalw', '-help']),
                          ('muscle', ['muscle', '-version'])]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
                tools[tool] = True
            except:
                tools[tool] = False
        return tools
    
    def convert_path(self, path):
        path = path.strip(). strip('"'). strip("'")
        if len(path) >= 2 and path[1] == ':':
            drive = path[0]. lower()
            rest = path[2:].replace('\\', '/')
            return f"/mnt/{drive}{rest}"
        return path
    
    def wsl_to_windows_path(self, wsl_path):
        if wsl_path. startswith('/mnt/'):
            rest = wsl_path[5:]
            drive = rest[0].upper()
            path = rest[1:].replace('/', '\\')
            return f"{drive}:{path}"
        return wsl_path
    
    def parse_fasta_text(self, text):
        sequences = {}
        current_name = None
        current_seq = []
        
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('>'):
                if current_name:
                    sequences[current_name] = ''.join(current_seq)
                current_name = line[1:].split()[0]
                current_seq = []
            elif current_name:
                clean_line = ''.join(c for c in line if c.isalpha() or c == '-')
                if clean_line:
                    current_seq. append(clean_line)
        
        if current_name:
            sequences[current_name] = ''.join(current_seq)
        
        return sequences
    
    def load_fasta(self, filepath):
        filepath = self.convert_path(filepath)
        
        if not os.path.exists(filepath):
            print(f"  ❌ 文件不存在: {filepath}")
            return False
            
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            filename = os.path. basename(filepath)
            self.loaded_files.append(filename)
            
            parsed = self.parse_fasta_text(content)
            count = len(parsed)
            self.sequences.update(parsed)
                
            print(f"  ✅ 已加载: {filename} ({count} 条序列)")
            return True
            
        except Exception as e:
            print(f"  ❌ 读取失败: {e}")
            return False
    
    def load_from_text(self):
        print("\n" + "=" * 60)
        print("  📋 粘贴 FASTA 序列")
        print("=" * 60)
        print("  格式示例:")
        print("  >seq_name1")
        print("  ATGCGATCGATCG...")
        print("-" * 60)
        print("  粘贴完成后，输入单独一行 'END' 结束")
        print("  输入 'q' 取消")
        print("-" * 60)
        
        lines = []
        while True:
            try:
                line = input()
                if line. strip(). upper() == 'END':
                    break
                if line.strip(). lower() == 'q':
                    print("  ⚠️ 已取消")
                    return
                lines.append(line)
            except EOFError:
                break
        
        if not lines:
            print("  ⚠️ 没有输入内容")
            return
        
        text = '\n'.join(lines)
        parsed = self.parse_fasta_text(text)
        
        if parsed:
            self. sequences.update(parsed)
            self.loaded_files. append("text_input")
            print(f"\n  ✅ 成功解析 {len(parsed)} 条序列:")
            for name, seq in parsed.items():
                print(f"     - {name} ({len(seq)} bp)")
        else:
            print("  ❌ 无法解析 FASTA 格式")
    
    def interactive_select_keyboard(self):
        if not self.sequences:
            print("\n  📭 没有加载任何序列")
            return None
        
        seq_names = list(self.sequences.keys())
        selected = [False] * len(seq_names)
        cursor = 0
        
        def display():
            print("\033[2J\033[H", end="")
            
            print("=" * 70)
            print("  🧬 序列选择器 - 键盘操作模式")
            print("=" * 70)
            print("  ↑/↓ 移动  |  空格 选择  |  A 全选  |  N 取消  |  D 完成  |  Q 返回")
            print("-" * 70)
            print(f"  {'':^3} | {'状态':^6} | {'序列名':<38} | {'长度':>10}")
            print("-" * 70)
            
            max_display = 15
            if len(seq_names) <= max_display:
                start_idx, end_idx = 0, len(seq_names)
            else:
                half = max_display // 2
                if cursor < half:
                    start_idx, end_idx = 0, max_display
                elif cursor >= len(seq_names) - half:
                    start_idx, end_idx = len(seq_names) - max_display, len(seq_names)
                else:
                    start_idx, end_idx = cursor - half, cursor + half + 1
            
            for i in range(start_idx, end_idx):
                name = seq_names[i]
                pointer = " ▶" if i == cursor else "  "
                check = "[✓]" if selected[i] else "[ ]"
                seq_len = len(self.sequences[name])
                display_name = name[:36] + ". ." if len(name) > 38 else name
                
                if i == cursor:
                    print(f"\033[7m  {pointer} | {check:^6} | {display_name:<38} | {seq_len:>8} bp\033[0m")
                else:
                    print(f"  {pointer} | {check:^6} | {display_name:<38} | {seq_len:>8} bp")
            
            if len(seq_names) > max_display:
                print(f"  ...  (显示 {start_idx+1}-{end_idx}/{len(seq_names)})")
            
            print("-" * 70)
            print(f"  已选择: {sum(selected)} / {len(seq_names)} 条序列")
            print("=" * 70)
        
        while True:
            display()
            key = get_key()
            
            if key == 'UP':
                cursor = (cursor - 1) % len(seq_names)
            elif key == 'DOWN':
                cursor = (cursor + 1) % len(seq_names)
            elif key == 'SPACE':
                selected[cursor] = not selected[cursor]
            elif key == 'A':
                selected = [True] * len(seq_names)
            elif key == 'N':
                selected = [False] * len(seq_names)
            elif key == 'Q':
                print("\n")
                return None
            elif key == 'D' or key == 'ENTER':
                if sum(selected) < 2:
                    print("\n  ⚠️  需要至少选择2条序列！")
                    import time
                    time.sleep(1)
                    continue
                break
        
        print("\n")
        result = {name: self.sequences[name] for i, name in enumerate(seq_names) if selected[i]}
        print(f"  ✅ 已选择 {len(result)} 条序列")
        return result
    
    def generate_output_filename(self, selected_seqs, tool, ext="fasta"):
        names = list(selected_seqs.keys())
        
        if len(names) <= 3:
            name_part = "_".join([n[:12] for n in names])
        else:
            name_part = f"{names[0][:10]}_{names[1][:10]}_etc{len(names)}"
        
        name_part = "".join(c if c.isalnum() or c in '_-' else '_' for c in name_part)
        timestamp = datetime.now(). strftime("%m%d_%H%M%S")
        
        return f"aln_{name_part}_{tool}_{timestamp}.{ext}"
    
    def run_alignment(self, selected_seqs, tool, params):
        print(f"\n  🚀 使用 {tool. upper()} 进行比对...")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as tmp_in:
            for name, seq in selected_seqs.items():
                tmp_in.write(f">{name}\n{seq}\n")
            tmp_input = tmp_in. name
        
        tmp_output = tempfile.mktemp(suffix='.aln')
        
        try:
            if tool == 'mafft':
                algo = params.get('algorithm', 'auto')
                if algo == 'auto':
                    cmd = ['mafft', '--auto', tmp_input]
                else:
                    cmd = ['mafft', f'--{algo}']
                    if 'op' in params:
                        cmd.extend(['--op', str(params['op'])])
                    if 'ep' in params:
                        cmd.extend(['--ep', str(params['ep'])])
                    cmd.append(tmp_input)
                    
            elif tool == 'clustalw':
                cmd = ['clustalw', f'-INFILE={tmp_input}', f'-OUTFILE={tmp_output}', '-OUTPUT=FASTA']
                
            elif tool == 'muscle':
                cmd = ['muscle', '-align', tmp_input, '-output', tmp_output]
            
            print(f"  📝 命令: {' '.join(cmd)}")
            print("  ⏳ 比对中，请稍候.. .\n")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if tool == 'mafft':
                alignment = result.stdout
            else:
                if os.path.exists(tmp_output):
                    with open(tmp_output, 'r') as f:
                        alignment = f.read()
                else:
                    alignment = result.stdout
            
            if alignment and len(alignment. strip()) > 0:
                self.last_result = alignment
                
                output_filename = self. generate_output_filename(selected_seqs, tool)
                output_path = os. path.join(self.output_dir, output_filename)
                
                with open(output_path, 'w') as f:
                    f.write(alignment)
                
                self.last_result_file = output_path
                
                print("  " + "=" * 65)
                print("  📊 比对结果预览:\n")
                lines = alignment.strip().split('\n')
                for line in lines[:20]:
                    print(f"  {line[:70]}")
                if len(lines) > 20:
                    print(f"\n  ... (共 {len(lines)} 行)")
                
                print("\n  " + "=" * 65)
                print(f"  ✅ 比对完成!")
                print(f"  💾 已保存: {output_path}")
                print("  " + "=" * 65)
                return True
            else:
                print(f"  ❌ 比对失败")
                if result.stderr:
                    print(f"  错误: {result.stderr[:300]}")
                return False
                
        except subprocess. TimeoutExpired:
            print("  ❌ 比对超时")
            return False
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            return False
        finally:
            for f in [tmp_input, tmp_output]:
                if os.path.exists(f):
                    os.remove(f)
    
    def visualize_alignment(self, fasta_path=None):
        print("\n" + "=" * 60)
        print("  🎨 比对结果可视化")
        print("=" * 60)
        
        if fasta_path:
            fasta_path = self.convert_path(fasta_path)
        elif self.last_result_file:
            fasta_path = self.last_result_file
            print(f"  使用上次比对结果: {os.path.basename(fasta_path)}")
        else:
            print("  没有现有比对结果，请输入文件路径:")
            path = input("  文件路径: ").strip()
            if not path:
                return
            fasta_path = self.convert_path(path)
        
        if not os.path.exists(fasta_path):
            print(f"  ❌ 文件不存在: {fasta_path}")
            return
        
        print("\n  选择输出格式:")
        print("  1. PDF (推荐)")
        print("  2.  PNG")
        print("  3. HTML")
        
        format_choice = input("\n  选择 [1]: ").strip() or "1"
        
        if format_choice == "3":
            self.export_html_visualization(fasta_path)
        else:
            ext = "pdf" if format_choice == "1" else "png"
            self. export_pymsaviz(fasta_path, ext)
    
    def export_pymsaviz(self, fasta_path, ext="pdf"):
        if not self.pymsaviz_available:
            print("\n  ⚠️  pymsaviz 未安装")
            print("  请运行: pip install pymsaviz")
            print("  使用 HTML 格式代替...")
            self.export_html_visualization(fasta_path)
            return
        
        try:
            from pymsaviz import MsaViz
            
            base_name = os. path.splitext(os.path.basename(fasta_path))[0]
            output_path = os.path. join(self.output_dir, f"{base_name}_viz.{ext}")
            
            print(f"\n  ⏳ 生成可视化中...")
            
            mv = MsaViz(fasta_path, wrap_length=80, show_count=True)
            mv.savefig(output_path, dpi=150)
            
            print(f"  ✅ 可视化已保存: {output_path}")
            
            try:
                win_path = self.wsl_to_windows_path(output_path)
                os.system(f'cmd. exe /c start "" "{win_path}" 2>/dev/null')
                print(f"  📂 正在打开文件...")
            except:
                print(f"  💡 Windows 路径: {self.wsl_to_windows_path(output_path)}")
                
        except Exception as e:
            print(f"  ❌ 可视化失败: {e}")
            print("  尝试使用 HTML 格式...")
            self.export_html_visualization(fasta_path)
    
    def export_html_visualization(self, fasta_path=None):
        if fasta_path:
            with open(fasta_path, 'r') as f:
                content = f. read()
            seqs = self.parse_fasta_text(content)
            base_name = os. path.splitext(os.path.basename(fasta_path))[0]
        elif self.last_result:
            seqs = self.parse_fasta_text(self.last_result)
            base_name = "alignment"
        else:
            print("  ⚠️ 没有比对结果")
            return
        
        if not seqs:
            print("  ❌ 无法解析序列")
            return
        
        output_path = os. path.join(self.output_dir, f"{base_name}_viz.html")
        
        names = list(seqs.keys())
        sequences = list(seqs.values())
        seq_len = len(sequences[0])
        
        colors = {
            'A': '#f0c000', 'V': '#f0c000', 'L': '#f0c000', 'I': '#f0c000', 
            'M': '#f0c000', 'F': '#f0c000', 'W': '#f0c000', 'P': '#f0c000',
            'S': '#00c000', 'T': '#00c000', 'N': '#00c000', 'Q': '#00c000',
            'D': '#c00000', 'E': '#c00000',
            'K': '#0000c0', 'R': '#0000c0', 'H': '#0080c0',
            'C': '#00c0c0', 'G': '#c0c0c0', 'Y': '#00c0c0',
            '-': '#e5e5e5',
        }
        
        def get_conservation(pos):
            bases = [s[pos]. upper() for s in sequences]
            most_common = max(set(bases), key=bases.count)
            ratio = bases.count(most_common) / len(bases)
            return ratio, most_common
        
        html = f'''<! DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Alignment: {base_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: Consolas, Monaco, 'Courier New', monospace;
            background: #f5f5f5; 
            padding: 20px;
            font-size: 13px;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f, #2d5a87);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .stats {{ display: flex; gap: 20px; margin-top: 15px; }}
        .stat {{ background: rgba(255,255,255,0.1); padding: 8px 15px; border-radius: 4px; }}
        .alignment-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .block {{ margin-bottom: 30px; }}
        .seq-row {{
            display: flex;
            align-items: center;
            height: 22px;
            white-space: nowrap;
        }}
        .seq-name {{
            display: inline-block;
            width: 200px;
            min-width: 200px;
            max-width: 200px;
            padding-right: 15px;
            text-align: right;
            font-weight: bold;
            color: #333;
            overflow: hidden;
            text-overflow: ellipsis;
            border-right: 2px solid #ccc;
            margin-right: 10px;
        }}
        .seq-data {{
            display: flex;
        }}
        .base {{
            display: inline-block;
            width: 14px;
            height: 18px;
            text-align: center;
            line-height: 18px;
            margin: 0;
            font-size: 12px;
        }}
        .conserved {{
            background: #c00000 !important;
            color: white ! important;
            font-weight: bold;
        }}
        .similar {{
            background: #ffcccc !important;
            color: #800000 !important;
        }}
        .position-row {{
            color: #888;
            font-size: 11px;
            border-bottom: 1px solid #ddd;
            margin-bottom: 5px;
            padding-bottom: 3px;
        }}
        .consensus-row {{
            border-top: 1px solid #eee;
            margin-top: 5px;
            padding-top: 5px;
        }}
        .consensus-name {{
            color: #888;
            font-style: italic;
            font-weight: normal;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background: #fafafa;
            border-radius: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        . legend-title {{ width: 100%; font-weight: bold; margin-bottom: 5px; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; padding: 3px 8px; background: white; border-radius: 4px; }}
        .legend-color {{ width: 20px; height: 20px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 Sequence Alignment Visualization</h1>
        <p>File: {base_name}</p>
        <div class="stats">
            <div class="stat">📊 Sequences: {len(names)}</div>
            <div class="stat">📏 Length: {seq_len}</div>
            <div class="stat">🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
    </div>
    <div class="alignment-container">
'''
        
        block_size = 60
        
        for start in range(0, seq_len, block_size):
            end = min(start + block_size, seq_len)
            
            # Position ruler
            ruler_html = '<div class="seq-row position-row"><span class="seq-name"></span><span class="seq-data">'
            for i in range(start, end):
                if (i + 1) % 10 == 0:
                    ruler_html += f'<span class="base" style="font-weight:bold">{i+1}</span>'
                else:
                    ruler_html += '<span class="base">·</span>'
            ruler_html += '</span></div>'
            
            html += f'<div class="block">\n{ruler_html}\n'
            
            # Sequence rows
            for name, seq in zip(names, sequences):
                segment = seq[start:end]
                display_name = name[:22] if len(name) > 22 else name
                
                html += f'<div class="seq-row"><span class="seq-name">{display_name}</span><span class="seq-data">'
                
                for i, base in enumerate(segment):
                    pos = start + i
                    conservation, most_common = get_conservation(pos)
                    base_upper = base.upper()
                    
                    if conservation == 1.0 and base != '-':
                        css_class = "base conserved"
                        style = ""
                    elif conservation >= 0.7 and base_upper == most_common:
                        css_class = "base similar"
                        style = ""
                    else:
                        css_class = "base"
                        color = colors. get(base_upper, '#fff')
                        style = f'style="background:{color}"'
                    
                    html += f'<span class="{css_class}" {style}>{base}</span>'
                
                html += '</span></div>\n'
            
            # Consensus row
            html += '<div class="seq-row consensus-row"><span class="seq-name consensus-name">consensus</span><span class="seq-data">'
            for i in range(start, end):
                conservation, most_common = get_conservation(i)
                if conservation == 1.0 and most_common != '-':
                    html += '<span class="base" style="color:#c00000;font-weight:bold">*</span>'
                elif conservation >= 0.7:
                    html += '<span class="base" style="color:#888">:</span>'
                elif conservation >= 0.5:
                    html += '<span class="base" style="color:#ccc">. </span>'
                else:
                    html += '<span class="base"> </span>'
            html += '</span></div>\n</div>\n'
        
        html += '''
    </div>
    <div class="legend">
        <div class="legend-title">📖 Legend</div>
        <div class="legend-item"><div class="legend-color" style="background:#c00000"></div> 100% conserved</div>
        <div class="legend-item"><div class="legend-color" style="background:#ffcccc"></div> ≥70% similar</div>
        <div class="legend-item"><div class="legend-color" style="background:#f0c000"></div> Hydrophobic</div>
        <div class="legend-item"><div class="legend-color" style="background:#00c000"></div> Polar</div>
        <div class="legend-item"><div class="legend-color" style="background:#0000c0"></div> Positive</div>
        <div class="legend-item"><div class="legend-color" style="background:#c00000;opacity:0.7"></div> Negative</div>
    </div>
</body>
</html>'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n  ✅ HTML 已保存: {output_path}")
        
        try:
            win_path = self.wsl_to_windows_path(output_path)
            os.system(f'cmd.exe /c start "" "{win_path}" 2>/dev/null')
            print(f"  📂 正在打开...")
        except:
            print(f"  💡 Windows 路径: {self.wsl_to_windows_path(output_path)}")
    
    def set_output_dir(self):
        print(f"\n  📁 当前输出目录: {self.output_dir}")
        print("  输入新路径，按回车保持不变:")
        
        path = input("\n  >>> ").strip()
        if not path:
            return
            
        path = self.convert_path(path)
        
        if os.path.isdir(path):
            self.output_dir = path
            print(f"  ✅ 输出目录: {path}")
        else:
            try:
                os.makedirs(path, exist_ok=True)
                self.output_dir = path
                print(f"  ✅ 已创建: {path}")
            except:
                print(f"  ❌ 目录无效")
    
    def configure_params(self, tool):
        params = {}
        if tool == 'mafft':
            print("\n  MAFFT 算法: auto/linsi/ginsi/einsi/fftns")
            algo = input("  算法 [auto]: ").strip(). lower() or 'auto'
            params['algorithm'] = algo
        return params
    
    def menu_load_files(self):
        while True:
            print("\n" + "=" * 55)
            print("  📁 加载序列")
            print("=" * 55)
            print("  1. 从文件加载")
            print("  2. 从粘贴文本加载")
            print("  0. 返回")
            print("-" * 55)
            
            choice = input("  请选择: ").strip()
            
            if choice == '1':
                print("\n  输入文件路径 (支持通配符 *.fasta)")
                print("  输入 q 返回\n")
                while True:
                    path = input("  路径: ").strip()
                    if path. lower() == 'q':
                        break
                    if not path:
                        continue
                    path = self.convert_path(path)
                    if '*' in path or '?' in path:
                        for f in glob.glob(path):
                            self.load_fasta(f)
                    else:
                        self.load_fasta(path)
            elif choice == '2':
                self.load_from_text()
            elif choice == '0':
                break
    
    def menu_align(self):
        if len(self.sequences) < 2:
            print("\n  ⚠️  需要至少2条序列")
            return
        
        selected = self.interactive_select_keyboard()
        if not selected:
            return
        
        print("\n  🔧 选择比对工具:")
        available = [k for k, v in self.available_tools.items() if v]
        if not available:
            print("  ❌ 没有可用工具")
            return
        for i, tool in enumerate(available, 1):
            print(f"  {i}. {tool}")
        
        try:
            tool_idx = int(input("\n  选择 [1]: "). strip() or "1") - 1
            tool = available[tool_idx]
        except:
            tool = available[0]
        
        use_auto = input("\n  使用默认参数?  [Y/n]: "). strip().lower() != 'n'
        params = {'algorithm': 'auto'} if use_auto else self.configure_params(tool)
        
        self.run_alignment(selected, tool, params)
        
        if input("\n  生成可视化?  [y/N]: "). strip().lower() == 'y':
            self.visualize_alignment()
        else:
            input("\n  按回车继续...")
    
    def menu_visualize(self):
        print("\n" + "=" * 55)
        print("  🎨 可视化比对结果")
        print("=" * 55)
        if self.last_result_file:
            print(f"  最近: {os.path. basename(self.last_result_file)}")
        print("\n  1. 可视化最近结果")
        print("  2. 选择文件")
        print("  0. 返回")
        
        choice = input("\n  选择: ").strip()
        if choice == '1':
            if self.last_result_file:
                self.visualize_alignment()
            else:
                print("  ⚠️ 没有最近结果")
        elif choice == '2':
            path = input("  文件路径: ").strip()
            if path:
                self.visualize_alignment(path)
    
    def show_sequences(self):
        if not self.sequences:
            print("\n  📭 没有序列")
            return
        print(f"\n  📋 共 {len(self. sequences)} 条序列:")
        print("  " + "-" * 55)
        for i, (name, seq) in enumerate(self.sequences. items(), 1):
            print(f"  {i:3}. {name[:35]:<35} | {len(seq):>6} bp")
        print("  " + "-" * 55)
    
    def main_menu(self):
        while True:
            print("\n" + "=" * 60)
            print("  🧬 序列比对工具 v4.1")
            print("=" * 60)
            print(f"  已加载: {len(self.sequences)} 条序列")
            print(f"  输出: {self.output_dir}")
            print("-" * 60)
            print("  1. 加载序列")
            print("  2. 查看序列")
            print("  3. 开始比对")
            print("  4. 可视化")
            print("  5. 设置输出目录")
            print("  6. 清除序列")
            print("  0. 退出")
            print("-" * 60)
            
            choice = input("  请选择: ").strip()
            
            if choice == '1':
                self.menu_load_files()
            elif choice == '2':
                self. show_sequences()
            elif choice == '3':
                self. menu_align()
            elif choice == '4':
                self.menu_visualize()
            elif choice == '5':
                self.set_output_dir()
            elif choice == '6':
                self.sequences. clear()
                self.loaded_files.clear()
                print("  🗑️ 已清除")
            elif choice == '0':
                print("\n  👋 再见!\n")
                break


def main():
    aligner = SequenceAligner()
    aligner.main_menu()


if __name__ == "__main__":
    main()