#!/usr/bin/env python3
import requests
import sys
import os
import re
import pandas as pd
from io import StringIO
from Bio import SeqIO

# 尝试导入菜单库
try:
    from simple_term_menu import TerminalMenu
except ImportError:
    print("❌ 缺少必要的库。请运行: pip3 install simple-term-menu")
    sys.exit(1)

# ==========================================
# 1. 配置与菜单
# ==========================================
TAXONOMY_MENU = {
    "0": ("不限制 (All)", "*"),
    "1": ("Viridiplantae (绿色植物)", "33090"),
    "2": ("Embryophyta (陆生植物)", "3193"),
    "3": ("Tracheophyta (维管植物)", "58023"),
    "4": ("Spermatophyta (种子植物)", "58024"),
    "5": ("Angiospermae (被子植物)", "3398"),
    "6": ("Gymnospermae (裸子植物)", "3312"),
    "7": ("Polypodiopsida (真蕨)", "241806"),
    "8": ("Lycopodiopsida (石松)", "3247"),
    "9": ("Bryophyta (苔藓)", "3208"),
    "10": ("Chlorophyta (绿藻)", "3041"),
    "11": ("Arabidopsis thaliana", "3702"),
    "12": ("Oryza sativa", "4530")
}

def get_search_params():
    print("\n=== 🧬 UniProt 终极检索器 v5.4 (去干扰版) ===")
    
    query = input(f"\n[1] 搜索关键词 [默认: 1-aminocyclopropane-1-carboxylate oxidase]: ").strip()
    if not query: query = "1-aminocyclopropane-1-carboxylate oxidase"

    print("\n[2] 数据库类型:")
    print("   r: Reviewed (Swiss-Prot) [默认]")
    print("   u: Unreviewed (TrEMBL)")
    print("   a: All")
    db = input("   选择: ").lower().strip()
    
    rev_str = " AND (reviewed:true)" 
    if db == 'u': rev_str = " AND (reviewed:false)"
    elif db == 'a': rev_str = ""

    print("\n[3] 物种范围:")
    for k, v in TAXONOMY_MENU.items():
        print(f"   {k.ljust(2)}: {v[0]}")
    
    tax_in = input("   选择 ID (或输入 'c' 自定义): ").strip()
    
    if tax_in == 'c':
        ids = input("   输入 Taxonomy ID (逗号分隔): ").split(',')
        tax_q = " OR ".join([f"taxonomy_id:{x.strip()}" for x in ids])
        tax_str = f" AND ({tax_q})"
    else:
        if not tax_in: tax_in = "1"
        if tax_in == "0": tax_str = ""
        else: tax_str = f" AND taxonomy_id:{TAXONOMY_MENU.get(tax_in, ('', '33090'))[1]}"

    return query, tax_str, rev_str

# ==========================================
# 2. 获取数据
# ==========================================
def fetch_metadata(keyword, tax_filter, reviewed_filter):
    print("\n⏳ 正在获取元数据...")
    
    if " " in keyword and not keyword.startswith('"'):
        search_term = f'"{keyword}"'
    else:
        search_term = keyword
        
    full_query = f'({search_term}){tax_filter}{reviewed_filter}'
    # 移除了 length 字段
    columns = "accession,id,protein_name,gene_names,organism_name"
    
    try:
        r = requests.get(
            "https://rest.uniprot.org/uniprotkb/stream",
            params={"query": full_query, "format": "tsv", "fields": columns}
        )
        r.raise_for_status()
        if not r.text.strip(): return None
        return pd.read_csv(StringIO(r.text), sep='\t')
    except Exception as e:
        print(f"❌ API 请求失败: {e}")
        sys.exit(1)

# ==========================================
# 3. 数据清洗
# ==========================================
def clean_dataframe(df):
    rename_map = {
        'Entry': 'ID', 'Entry Name': 'EntryName', 
        'Protein names': 'Protein', 'Gene Names': 'Gene', 
        'Organism': 'Species'
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    df.fillna('Unknown', inplace=True)
    
    df['Gene'] = df['Gene'].astype(str)
    df['Species'] = df['Species'].astype(str)
    df['Protein'] = df['Protein'].astype(str)
    
    # 1. 基因名：只取第一个
    df['Gene_Short'] = df['Gene'].apply(lambda x: x.split(' ')[0] if x != 'Unknown' else 'Unk')
    
    # 2. 物种名：移除括号内容，只保留拉丁名，看着更清爽
    # 例如: "Arabidopsis thaliana (Mouse-ear cress)" -> "Arabidopsis thaliana"
    df['Species_Clean'] = df['Species'].apply(lambda x: x.split(' (')[0])
    
    # 3. 蛋白名：保留全称
    df['Protein_Full'] = df['Protein']
    
    return df

# ==========================================
# 4. 交互菜单 (无竖线安全版)
# ==========================================
def interactive_selection(df):
    # 动态计算列宽
    # 留出额外的 padding (比如 +3) 增加呼吸感
    w_id = max(df['ID'].str.len().max(), 8) + 2
    w_gene = max(df['Gene_Short'].str.len().max(), 6) + 3
    w_species = max(df['Species_Clean'].str.len().max(), 15) + 3
    
    menu_items = []
    
    # 构建表头 (仅用于显示，不放入菜单列表以免被误选)
    # 使用空格分隔，绝对不使用 |
    header = f"{'ID':<{w_id}}   {'Gene':<{w_gene}}   {'Species':<{w_species}}   {'Protein Name'}"
    
    for idx, row in df.iterrows():
        # 构建每一行字符串
        item = f"{row['ID']:<{w_id}}   {row['Gene_Short']:<{w_gene}}   {row['Species_Clean']:<{w_species}}   {row['Protein_Full']}"
        menu_items.append(item)

    print(f"\n✅ 检索到 {len(df)} 条记录。")
    print("-" * 120)
    print(header)
    print("-" * 120)
    
    terminal_menu = TerminalMenu(
        menu_items,
        title="👉 操作: [↑/↓]移动 | [Space]选中/取消 | [/]搜索过滤 | [Enter]确认",
        multi_select=True,
        show_multi_select_hint=True,
        show_search_hint=True,
        # 默认全选
        preselected_entries=list(range(len(menu_items)))
    )
    
    selected_indices = terminal_menu.show()
    
    if selected_indices is None or len(selected_indices) == 0:
        return None
        
    return df.iloc[list(selected_indices)]

# ==========================================
# 5. 下载与保存
# ==========================================
def download_sequences(df, filename_prefix):
    print(f"\n🚀 正在下载选中的 {len(df)} 条序列...")
    
    ids = df['ID'].tolist()
    batch_size = 100
    final_records = []
    base_url = "https://rest.uniprot.org/uniprotkb/stream"

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i+batch_size]
        query = " OR ".join([f"accession:{x}" for x in batch_ids])
        
        try:
            r = requests.get(base_url, params={"query": query, "format": "fasta"})
            r.raise_for_status()
            
            for record in SeqIO.parse(StringIO(r.text), "fasta"):
                acc_id = record.id.split('|')[1]
                row = df[df['ID'] == acc_id].iloc[0]
                
                # Header: >Gene_Species_ID
                gene = str(row['Gene_Short'])
                if gene == "Unknown": gene = acc_id
                sp = str(row['Species_Clean']).replace(' ', '_').replace('.', '')
                
                new_id = f"{gene}_{sp}_{acc_id}"
                
                record.id = new_id
                record.description = row['Protein_Full']
                final_records.append(record)
                
        except Exception as e:
            print(f"⚠️ 批次下载失败: {e}")

    safe_name = re.sub(r'[^\w\-_\.]', '_', filename_prefix)
    outfile = f"{safe_name}_ref.fasta"
    
    if final_records:
        with open(outfile, "w") as f:
            SeqIO.write(final_records, f, "fasta")
        print(f"\n🎉 成功！文件已保存: {os.path.abspath(outfile)}")
    else:
        print("❌ 下载失败。")

if __name__ == "__main__":
    kw, tax, rev = get_search_params()
    df_meta = fetch_metadata(kw, tax, rev)
    
    if df_meta is None or df_meta.empty:
        print("❌ 无搜索结果。")
    else:
        df_clean = clean_dataframe(df_meta)
        df_selected = interactive_selection(df_clean)
        
        if df_selected is not None and not df_selected.empty:
            download_sequences(df_selected, kw)
        else:
            print("⚠️ 未选择任何序列。")
