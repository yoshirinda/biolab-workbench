#!/bin/bash

# =================================================================
# WSL BLAST Pipeline Manager V4.1
#  - 修复 OneDrive/空格路径问题（建库）
#  - 统一数据库目录 & 轻量索引
#  - 增强 BLAST 输出（详细表 + 可读 summary）
#  - 优化交互体验
# =================================================================

# --- 1. 核心配置 ---
WORK_DIR="/mnt/c/Users/u0184116/blast"
DB_ROOT="$WORK_DIR/databases"        # 所有 BLAST DB 放在这里
RAW_FASTA_DIR="$WORK_DIR/raw_fasta"  # 可选：把原始 fasta 拷贝到这里再建库
INDEX_FILE="$DB_ROOT/.db_index.tsv"  # 轻量索引：prefix \t name \t type

# --- 2. 初始化 ---
mkdir -p "$WORK_DIR" "$DB_ROOT" "$RAW_FASTA_DIR"
# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

# --- 3. 辅助函数 ---

normalize_path() {
    local input_path="$1"
    # 去掉前后引号
    input_path=$(echo "$input_path" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    # 包含 : 或 \ 视为 Windows 路径
    if [[ "$input_path" == *":"* ]] || [[ "$input_path" == *"\\"* ]]; then
        wslpath "$input_path"
    else
        echo "$input_path"
    fi
}

detect_seq_type() {
    local file="$1"
    local seq
    seq=$(grep -v "^>" "$file" | head -n 1 | cut -c 1-50 | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
    if [[ "$seq" =~ [EFILPQ] ]]; then
        echo "prot"
    else
        echo "nucl"
    fi
}

# 轻量索引：追加记录
index_database() {
    local prefix="$1"    # 完整前缀路径
    local name="$2"      # 用户给的库名
    local type="$3"      # prot / nucl
    mkdir -p "$DB_ROOT"
    {
        echo -e "${prefix}\t${name}\t${type}"
    } >> "$INDEX_FILE"
}

# --- 4. 数据库扫描逻辑 ---
find_databases() {
    DB_PATHS=()
    DB_NAMES=()
    DB_TYPES=()
    
    echo -e "正在扫描数据库文件 (.psq / .nsq) 于: ${YELLOW}$DB_ROOT${NC}"
    
    # 只扫 DB_ROOT（及其子目录），避免 WORK_DIR 里其他东西干扰
    while IFS= read -r file; do
        base_name=$(basename "$file")
        
        if [[ "$base_name" == *.psq ]]; then
            real_db_prefix="${file%.psq}"
            display_name=$(basename "$real_db_prefix")
            DB_PATHS+=("$real_db_prefix")
            DB_NAMES+=("$display_name [Protein]")
            DB_TYPES+=("prot")
        elif [[ "$base_name" == *.nsq ]]; then
            real_db_prefix="${file%.nsq}"
            display_name=$(basename "$real_db_prefix")
            DB_PATHS+=("$real_db_prefix")
            DB_NAMES+=("$display_name [Nucleotide]")
            DB_TYPES+=("nucl")
        fi
    done < <(find "$DB_ROOT" -maxdepth 5 -type f \( -name "*.psq" -o -name "*.nsq" \) 2>/dev/null)
}

# --- 5. 功能模块 ---

# [建库]
make_database() {
    echo -e "${CYAN}>>> 建库模式${NC}"
    echo "请粘贴 FASTA 文件路径（可直接从 Windows 复制，支持含空格路径）:"
    read -r raw_input
    local_path=$(normalize_path "$raw_input")

    if [ ! -f "$local_path" ]; then
        echo -e "${RED}错误: 文件不存在: $local_path${NC}"
        read -p "回车返回主菜单..."
        return
    fi

    echo "请输入库名称 (如 Athaliana_TAIR10):"
    read -r db_name
    if [ -z "$db_name" ]; then
        echo -e "${RED}库名称不能为空${NC}"
        read -p "回车返回主菜单..."
        return
    fi

    target_dir="$DB_ROOT/$db_name"
    mkdir -p "$target_dir"

    # 可选：将 fasta 拷贝到工作目录，路径更干净
    local fasta_copied="$RAW_FASTA_DIR/${db_name}.fa"
    echo -e "正在将 FASTA 拷贝到工作目录: ${YELLOW}$fasta_copied${NC}"
    # 去掉 CR，保证是 Unix 文本
    tr -d '\r' < "$local_path" > "$fasta_copied"

    mol_type=$(detect_seq_type "$fasta_copied")

    echo -e "\n${CYAN}建库信息确认:${NC}"
    echo -e "  原始 FASTA:   ${YELLOW}$local_path${NC}"
    echo -e "  使用 FASTA:   ${YELLOW}$fasta_copied${NC}"
    echo -e "  目标目录:     ${YELLOW}$target_dir${NC}"
    echo -e "  库前缀:       ${YELLOW}$target_dir/$db_name${NC}"
    echo -e "  检测类型:     ${YELLOW}$mol_type${NC}"
    read -p "确认建库？(y/n): " yn
    if [[ ! "$yn" =~ ^[Yy]$ ]]; then
        echo "已取消建库。"
        read -p "回车返回主菜单..."
        return
    fi

    echo -e "${GREEN}开始调用 makeblastdb...${NC}"
    # 关键点：显式设置 title，避免使用长路径标题
    makeblastdb \
        -in "$fasta_copied" \
        -dbtype "$mol_type" \
        -out "$target_dir/$db_name" \
        -parse_seqids \
        -title "$db_name"

    if [ $? -ne 0 ]; then
        echo -e "${RED}makeblastdb 执行失败，请检查上方错误信息。${NC}"
    else
        echo -e "${GREEN}建库完成!${NC}"
        # 记录到索引
        index_database "$target_dir/$db_name" "$db_name" "$mol_type"
    fi
    read -p "回车返回主菜单..."
}

# [运行]
run_blast() {
    find_databases
    
    if [ ${#DB_PATHS[@]} -eq 0 ]; then
        echo -e "${RED}错误: 在 $DB_ROOT 下未找到任何 BLAST 数据库 (.psq 或 .nsq)。${NC}"
        read -p "回车返回主菜单..."
        return
    fi

    local real_db_path db_type

    echo -e "\n${CYAN}--- 可用数据库列表 ---${NC}"
    if [ ${#DB_PATHS[@]} -eq 1 ]; then
        # 只有一个库时自动选中
        real_db_path="${DB_PATHS[0]}"
        db_type="${DB_TYPES[0]}"
        echo -e "仅检测到一个数据库，自动选择: ${GREEN}${DB_NAMES[0]}${NC}"
    else
        # 多个库时用 select 让用户选择
        select opt in "${DB_NAMES[@]}"; do
            if [ -n "$opt" ]; then
                idx=$((REPLY-1))
                real_db_path="${DB_PATHS[$idx]}"
                db_type="${DB_TYPES[$idx]}"
                echo -e "已选数据库: ${GREEN}$opt${NC}"
                break
            else
                echo -e "${RED}无效选择，请重新输入编号。${NC}"
            fi
        done
    fi

    # Query 输入
    echo -e "\n${CYAN}--- Query 输入方式 ---${NC}"
    echo "1. 本地文件 (支持 Windows 路径)"
    echo "2. 直接粘贴序列文本 (Ctrl+D 结束)"
    while true; do
        read -p "选择 (1/2): " mode
        if [[ "$mode" == "1" || "$mode" == "2" ]]; then
            break
        else
            echo "请输入 1 或 2。"
        fi
    done
    
    query_file="$WORK_DIR/temp_query.fa"
    if [ "$mode" == "1" ]; then
        while true; do
            echo "请输入 query FASTA 文件路径:"
            read -r p
            [ -z "$p" ] && { echo "路径不能为空"; continue; }
            clean_p=$(normalize_path "$p")
            if [ ! -f "$clean_p" ]; then
                echo -e "${RED}文件不存在: $clean_p${NC}"
            else
                tr -d '\r' < "$clean_p" > "$query_file"
                break
            fi
        done
    else
        echo -e "请粘贴 FASTA 序列内容，结束请按 Ctrl+D:"
        cat > "$query_file"
        echo "" >> "$query_file"
        sed -i 's/\r//g' "$query_file"
    fi
    
    if [ ! -s "$query_file" ]; then
        echo -e "${RED}错误: Query 输入为空。${NC}"
        read -p "回车返回主菜单..."
        return
    fi

    # 自动选择程序
    q_type=$(detect_seq_type "$query_file")
    program="blastn"
    if [ "$q_type" == "nucl" ] && [ "$db_type" == "nucl" ]; then program="blastn"; fi
    if [ "$q_type" == "prot" ] && [ "$db_type" == "prot" ]; then program="blastp"; fi
    if [ "$q_type" == "nucl" ] && [ "$db_type" == "prot" ]; then program="blastx"; fi
    if [ "$q_type" == "prot" ] && [ "$db_type" == "nucl" ]; then program="tblastn"; fi
    
    echo -e "\n${CYAN}运行信息确认:${NC}"
    echo -e "  程序:        ${YELLOW}$program${NC}"
    echo -e "  DB 前缀:     ${YELLOW}$real_db_path${NC}"
    echo -e "  DB 类型:     ${YELLOW}$db_type${NC}"
    echo -e "  Query 类型:  ${YELLOW}$q_type${NC}"
    echo -e "  Query 文件:  ${YELLOW}$query_file${NC}"
    read -p "确认运行 BLAST？(y/n): " run_yn
    if [[ ! "$run_yn" =~ ^[Yy]$ ]]; then
        echo "已取消运行。"
        read -p "回车返回主菜单..."
        return
    fi
    
    timestamp=$(date +"%Y%m%d_%H%M%S")
    out_dir="$WORK_DIR/Result_${program}_${timestamp}"
    mkdir -p "$out_dir"
    
    echo -e "${GREEN}开始计算 BLAST，比对中...${NC}"
    # 传统对齐输出
    $program -query "$query_file" -db "$real_db_path" \
        -out "$out_dir/align.txt" \
        -outfmt 0 \
        -num_threads 4

    # 基本 tabular 输出
    $program -query "$query_file" -db "$real_db_path" \
        -out "$out_dir/table.tsv" \
        -outfmt "6 qseqid sseqid pident length evalue bitscore" \
        -num_threads 4

    # 详细 tabular 输出（更易用于筛选/分析）
    $program -query "$query_file" -db "$real_db_path" \
        -out "$out_dir/table_detailed.tsv" \
        -outfmt "6 qseqid sseqid qlen slen qstart qend sstart send pident length mismatch gapopen evalue bitscore" \
        -num_threads 4

    # 生成简单 summary 表 (identity 分级)
    awk 'BEGIN{
            OFS="\t";
            print "qseqid","sseqid","pident","length","evalue","bitscore","identity_level";
         }
         {
            level="LOW_ID";
            if ($9 >= 90) level="HIGH_ID";
            else if ($9 >= 70) level="MEDIUM_ID";
            print $1,$2,$9,$10,$13,$14,level;
         }' "$out_dir/table_detailed.tsv" > "$out_dir/summary.tsv"

    echo -e "${GREEN}BLAST 计算完成。${NC}"

    # HTML 报告
    echo "<html><head><meta charset=\"UTF-8\"><title>BLAST $program Result</title></head><body><h2>$program Result</h2><pre>" > "$out_dir/report.html"
    cat "$out_dir/align.txt" >> "$out_dir/report.html"
    echo "</pre></body></html>" >> "$out_dir/report.html"

    echo -e "${GREEN}结果目录 (Windows 路径):${NC}"
    wslpath -w "$out_dir"

    echo -e "\n结果文件包括："
    echo "  align.txt         - 传统 BLAST 对齐输出"
    echo "  table.tsv         - 基础表格（qseqid, sseqid, pident, length, evalue, bitscore）"
    echo "  table_detailed.tsv- 详细表格（含 qlen/slen/start/end 等）"
    echo "  summary.tsv       - 简化 summary（含 identity 分级）"
    echo "  report.html       - 简单 HTML 报告"

    # 提取序列
    echo -e "\n是否根据命中结果提取目标库中的 subject 序列? (y/n)"
    read -r ex
    if [[ "$ex" == "y" || "$ex" == "Y" ]]; then
        awk '{print $2}' "$out_dir/table.tsv" | sort -u > "$out_dir/ids.txt"
        cnt=$(wc -l < "$out_dir/ids.txt")
        if [ "$cnt" -gt 0 ]; then
            blastdbcmd -db "$real_db_path" -entry_batch "$out_dir/ids.txt" -out "$out_dir/seqs.fa"
            echo "已提取 $cnt 条序列到 seqs.fa。"
        else
            echo "无匹配命中，未提取任何序列。"
        fi
    fi
    read -p "回车返回主菜单..."
}

# --- 主菜单 ---
while true; do
    clear
    echo -e "${CYAN}=== WSL BLAST Manager V4.1 ===${NC}"
    printf "工作目录: %s\n" "$(wslpath -w "$WORK_DIR")"
    echo "数据库目录: $DB_ROOT"
    echo "----------------------------"
    echo "1. 建库 (makeblastdb)"
    echo "2. 运行 BLAST (blastn/blastp/blastx/tblastn)"
    echo "3. 退出"
    echo "----------------------------"
    read -p "选项: " op
    case $op in
        1) make_database ;;
        2) run_blast ;;
        3) exit 0 ;;
        *) echo "无效选项"; sleep 1 ;;
    esac
done
