#!/usr/bin/env python3
# --- 关键修改在这里 ---
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
# --- 修改结束 ---


import sys
import re
import os
from ete3 import Tree
from ete3.treeview import TreeStyle, NodeStyle, TextFace

# --- 路径转换函数 (无变动) ---

def convert_win_path_to_wsl(path):
    """ 自动将 Windows 路径转换为 WSL 路径。"""
    path = path.strip('\"\'')
    win_path_match = re.match(r"([a-zA-Z]):\\", path)
    
    if win_path_match:
        drive_letter = win_path_match.group(1).lower()
        rest_of_path = path[3:].replace("\\", "/")
        wsl_path = f"/mnt/{drive_letter}/{rest_of_path}"
        print(f"[路径转换] 识别到 Windows 路径。转换为: {wsl_path}")
        return wsl_path
    else:
        print("[路径转换] 识别到 Linux/WSL 路径，直接使用。")
        return path

def convert_wsl_path_to_win(path):
    """ 自动将 WSL 路径转换回 Windows 路径 (用于显示)。"""
    wsl_path_match = re.match(r"/mnt/([a-z])/(.*)", path)
    if wsl_path_match:
        drive_letter = wsl_path_match.group(1).upper()
        rest_of_path = wsl_path_match.group(2).replace("/", "\\")
        return f"{drive_letter}:\\{rest_of_path}"
    else:
        return path

# --- 自动检测前缀 (无变动) ---

def auto_detect_prefixes(tree_obj, prefix_regex):
    """ 自动检测物种前缀并让用户选择。"""
    print("\n--- 正在检测物种前缀... ---")
    all_leaves = tree_obj.get_leaf_names()
    detected_prefixes = set()
    
    for name in all_leaves:
        match = prefix_regex.match(name)
        if match:
            detected_prefixes.add(match.group(1))
            
    if not detected_prefixes:
        print("错误: 未能自动检测到任何前缀。")
        return set(), {}

    sorted_prefixes = sorted(list(detected_prefixes))
    print("检测到以下前缀:")
    for i, prefix in enumerate(sorted_prefixes):
        print(f"  {i+1}: {prefix}")
        
    print("\n--- 请选择您要“聚焦”并上色的物种 ---")
    
    focused_prefixes = set()
    while True:
        try:
            choice = input(f"请输入编号 (用逗号分隔, e.g., '1,8'), 或按[回车]跳过: ")
            if not choice:
                print("将不为任何物种上色。")
                return set(), {}

            indices = [int(i.strip()) for i in choice.split(",")]
            
            for index in indices:
                if 1 <= index <= len(sorted_prefixes):
                    focused_prefixes.add(sorted_prefixes[index - 1])
                else:
                    print(f"警告: 编号 {index} 无效, 已忽略。")
                    
            if focused_prefixes:
                print(f"\n已选择聚焦: {', '.join(focused_prefixes)}")
                break
            else:
                print("未选择任何有效编号，请重试。")
                
        except ValueError:
            print("输入无效，请输入数字编号 (如 1, 5)。")

    # 为选中的前缀分配颜色
    COLORS = ["#FF0000", "#0000FF", "#008000", "#FFA500", "#A020F0", 
              "#FFC0CB", "#A52A2A", "#00FFFF", "#800000", "#FFD700",
              "#00FF7F", "#4682B4", "#D2B48C", "#F0E68C", "#9ACD32"]
    
    color_map = {}
    for i, prefix in enumerate(focused_prefixes):
        color_map[prefix] = COLORS[i % len(COLORS)]
        
    print("颜色分配:")
    for prefix, color in color_map.items():
        print(f"  {prefix}: {color}")

    return focused_prefixes, color_map


# --- 渲染函数 (v6.4 修正) ---
def render_clade_svg(ancestor_node, target_node, tree_file_wsl_path, 
                     levels_up, focused_prefixes, color_map, prefix_regex,
                     layout_mode, fixed_branch_length, 
                     r_leaf_fsize, r_vmargin): 
    """
    接收一个 *已经找到的* 祖先节点 (clade) 并将其渲染为 SVG。
    """
    
    # 1. 创建子树的副本
    display_tree = ancestor_node.copy()
    
    # 【v6.4 修正】在渲染前发出大树警告
    num_leaves = len(display_tree)
    if layout_mode == 'rectangular' and num_leaves > 100:
        print(f"\n--- 警告: 渲染包含 {num_leaves} 个叶子的直角树 ---")
        print("  图像将会非常高。已启用“动态宽度”以保持缩放后的可读性。")
        print("  如果图像过大或加载缓慢, 强烈建议：")
        print("  1. 重新运行并选择 'c' (圆形) 布局。")
        print("  2. 重新运行并减小 '垂直间距' (e.g., 5) 和 '字体大小' (e.g., 6)。")

    # 2. 修改副本的分支长度 (如果需要)
    if fixed_branch_length:
        print("警告: 已启用固定分支长度，实际分支长度信息将不被表示。")
        for n in display_tree.traverse():
            n.dist = 1.0 
            
    # 3. 设置节点样式 (上色)
    print("--- 正在应用颜色... ---")
    
    for leaf in display_tree.iter_leaves():
        match = prefix_regex.match(leaf.name)
        if match:
            prefix = match.group(1)
            if prefix in focused_prefixes:
                nstyle = NodeStyle()
                nstyle["bgcolor"] = color_map[prefix]
                leaf.set_style(nstyle)
        else:
            leaf.set_style(NodeStyle())
            
    # 高亮我们的目标基因
    display_target_node = display_tree.search_nodes(name=target_node.name)[0]
    target_node_style = NodeStyle()
    target_node_style["bgcolor"] = "#FFFF00" 
    target_node_style["fgcolor"] = "#000000" 
    display_target_node.set_style(target_node_style)

    # 4. 手动添加内部节点名称 (bootstrap)
    print("--- 正在添加 Bootstrap 值... ---")
    for node in display_tree.traverse():
        if not node.is_leaf() and node.name:
            match = re.match(r"^[0-9.]+", node.name)
            if match:
                val_str = match.group(0)
                try:
                    val = float(val_str)
                    if 0 <= val <= 1.0 and val_str.startswith("0."):
                        final_name = str(int(val * 100))
                    else:
                        final_name = str(int(val))
                        
                    face = TextFace(final_name, fsize=10, fgcolor="#333333") 
                    node.add_face(face, column=0, position="branch-top")
                        
                except ValueError:
                    pass

    # 5. 设置树的整体样式 (TreeStyle)
    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.show_branch_support = False 
    
    if layout_mode == 'circular':
        ts.mode = "c" 
        ts.arc_start = -180 
        ts.arc_span = 360   
    elif layout_mode == 'rectangular':
        ts.mode = "r" 
        ts.branch_vertical_margin = r_vmargin 
        
    # 6. 手动添加所有叶子名称
    
    # 为目标基因的 TextFace 设置特殊样式
    target_face = TextFace(f"-> {target_node.name}", bold=True, fsize=r_leaf_fsize+2) # 目标基因稍大一点
    display_target_node.add_face(target_face, column=0, position="branch-right")

    for leaf in display_tree.iter_leaves():
        if leaf.name == target_node.name:
            continue
            
        leaf_fsize = 10 
        if layout_mode == 'rectangular':
            leaf_fsize = r_leaf_fsize 

        face = TextFace(leaf.name, fsize=leaf_fsize)
        leaf.add_face(face, column=0, position="branch-right")

    # 7. 添加图例
    if color_map:
        ts.legend.add_face(TextFace("物种图例", bold=True, fsize=14), column=0)
        for prefix, color in color_map.items():
            ts.legend.add_face(TextFace(f"  {prefix}", fgcolor=color, bold=True, fsize=12), column=0)

    # 8. 渲染并保存文件
    print("--- 正在生成 SVG 图像... ---")
    
    output_filename = f"{target_node.name}_L{levels_up}_{layout_mode}"
    if fixed_branch_length:
        output_filename += "_fixedBL"
    output_filename += ".svg"
    
    output_dir = os.path.dirname(tree_file_wsl_path)
    output_wsl_path = os.path.join(output_dir, output_filename)
    
    try:
        # 【v6.4 修正】关键修正：动态宽度计算
        if layout_mode == 'rectangular':
            
            # 基础宽度
            base_width = 2000
            
            # 估算高度： (叶子数 * 垂直间距)
            # 这是一个很好的高度代理
            estimated_height = num_leaves * r_vmargin
            
            # 动态宽度：我们希望 宽度 > 高度 / 2 (即 宽高比 > 1:2)
            # 这样缩放后就不会太细
            desired_width = estimated_height / 2
            
            # 取 基础宽度 和 动态宽度 中 *较大* 的一个
            final_width = max(base_width, desired_width)
            
            # 确保宽度是整数
            final_width = int(final_width) 
            
            if final_width > base_width:
                print(f"--- (检测到高树，自动增加画布宽度至 {final_width}px) ---")
            
            # 渲染：只给宽度(w)，不给高度(h)
            display_tree.render(output_wsl_path, tree_style=ts, units="px", w=final_width)
        
        else:
            # 'circular' 模式需要一个固定的正方形画布
            print("--- 正在渲染 (圆形模式, 1600x1600px)... ---")
            display_tree.render(output_wsl_path, tree_style=ts, units="px", w=1600, h=1600)
        
        output_win_path = convert_wsl_path_to_win(output_wsl_path)
        print("\n=======================================================")
        print(f"🎉 图像已成功保存到 (可在 Windows 中打开):")
        print(f"{output_win_path}")
        print("=======================================================")
        
    except Exception as e:
        print("\n--- 错误: 图像渲染失败 ---")
        print("这通常是因为 Qt 环境设置不正确或缺少必要的库。")
        print(f"请确保你已设置环境变量: export QT_QPA_PLATFORM=offscreen")
        print(f"详情: {e}")

# --- 主程序 (v6.4 修正) ---

def interactive_clade_viewer():
    """ 交互式主函数 """
    # 【v6.4 修正】
    print("--- 智能 SVG 树图生成器 v6.4 (动态宽度版) ---")
    print("请确保已安装: pip3 install ete3 PyQt5")
    print("并且在运行前设置环境变量: export QT_QPA_PLATFORM=offscreen")

    # 1. 加载树
    t = None
    tree_file_wsl_path = ""
    while t is None:
        path_input = input("\n请输入 .treefile 文件的路径 (Win或WSL格式): ")
        if not path_input:
            continue
            
        tree_file_wsl_path = convert_win_path_to_wsl(path_input)
        
        print(f"--- 正在加载树: {tree_file_wsl_path} ---")
        try:
            t = Tree(tree_file_wsl_path, format=1)
            print(f"树加载成功。总叶子数: {len(t)}")
        except FileNotFoundError:
            print(f"错误: 文件未找到。请检查路径: {tree_file_wsl_path}")
        except Exception as e:
            print(f"错误: 无法加载树文件。\n详情: {e}")
            
    # 2. 设置前缀
    prefix_regex = re.compile(r'^([a-zA-Z_]+)')
    focused_prefixes, color_map = auto_detect_prefixes(t, prefix_regex)
            
    print("\n--- 树已加载，进入查询模式 ---")
    
    # 3. 外层循环：获取目标基因
    while True:
        target_gene_name = input("\n请输入目标基因 (或输入 'q' 退出): ")
        if target_gene_name.lower() in ['q', 'exit', 'quit']:
            break
            
        # 3.1 检查基因是否存在
        try:
            target_node = t.search_nodes(name=target_gene_name)[0]
            print(f"--- 成功锁定目标: '{target_node.name}' ---")
        except IndexError:
            print(f"错误: 在树中未找到名为 '{target_gene_name}' 的节点。")
            continue 

        # 4. 内层循环：调整参数并重绘
        while True:
            # 4.1 获取级别
            levels_input = input(f"\n查询 '{target_node.name}':\n  请输入级别 (e.g., 6), 或 'n' (新基因), 'q' (退出): ")
            
            if levels_input.lower() == 'q':
                print("\n--- 查询结束，退出程序 ---")
                return 
            if levels_input.lower() == 'n':
                break 
            
            try:
                levels_up = int(levels_input)
                if levels_up <= 0:
                    raise ValueError
            except ValueError:
                print("错误: 请输入一个大于0的数字, 'n', 或 'q'.")
                continue 

            # 4.2 向上追溯
            ancestor = target_node
            for i in range(levels_up):
                if ancestor.is_root():
                    print(f"警告: 在第 {i} 级已到达根节点。")
                    break
                ancestor = ancestor.up
            
            # 4.3 获取布局
            layout_mode = ''
            while layout_mode not in ['c', 'r', 'circular', 'rectangular']:
                layout_input = input("  请选择布局模式 ('c' 为圆形/放射状, 'r' 为直角树，默认 'c'): ").lower()
                if not layout_input or layout_input == 'c':
                    layout_mode = 'circular'
                elif layout_input == 'r':
                    layout_mode = 'rectangular'
                else:
                    print("  无效的布局选择。")
            
            # 【v6.2 新增】如果为 'r' 模式，获取可读性参数
            r_leaf_fsize = 10 # 默认值 (用于 'c' 模式)
            r_vmargin = 1   # 默认值 (用于 'c' 模式)
            
            if layout_mode == 'rectangular':
                try:
                    # 【v6.3 修正】调整默认值，使其更美观
                    fsize_input = input("  [直角模式] 请输入叶子字体大小 (默认 10): ")
                    r_leaf_fsize = 10 if not fsize_input else int(fsize_input)
                    
                    vmargin_input = input("  [直角模式] 请输入叶子垂直间距 (默认 15): ")
                    r_vmargin = 15 if not vmargin_input else int(vmargin_input)
                except ValueError:
                    print("输入无效，将使用默认值 (字体10, 间距15)。")
                    r_leaf_fsize = 10
                    r_vmargin = 15

            # 4.4 获取分支长度选项
            fixed_branch_length = False
            while True:
                fix_bl_input = input("  是否使用固定分支长度？ (y/n, 默认 'n'): ").lower()
                if not fix_bl_input or fix_bl_input == 'n':
                    fixed_branch_length = False
                    break
                elif fix_bl_input == 'y':
                    fixed_branch_length = True
                    break
                else:
                    print("  无效输入，请输入 'y' 或 'n'。")

            # 4.5 执行渲染
            render_clade_svg(ancestor, target_node, tree_file_wsl_path, 
                             levels_up, focused_prefixes, color_map, prefix_regex,
                             layout_mode, fixed_branch_length, 
                             r_leaf_fsize, r_vmargin) # 传入新参数
            
    print("\n--- 查询结束，退出程序 ---")

# --- 脚本主程序 ---
if __name__ == "__main__":
    interactive_clade_viewer()
