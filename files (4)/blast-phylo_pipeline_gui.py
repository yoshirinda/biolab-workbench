#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WSL Bioinformatics Pipeline CLI (Command-Line Interface)
Author: Gemini (based on user requirements)
Version: 14.0-EN (Integrates interactive ClipKIT site checker as Step 4.5)
"""

import os
import subprocess
import shlex  # For safely splitting command arguments
import sys   
from collections import Counter 

# --- Core Utility Functions (Unchanged) ---

def win_to_wsl_path(win_path):
    """
    Converts a Windows path (C:\\Users\\...) to a WSL path (/mnt/c/Users/...)
    """
    if not win_path:
        return ""
    win_path = str(win_path)
    win_path = win_path.replace("\\", "/")
    if ":" in win_path:
        drive_letter = win_path[0].lower()
        path_remainder = win_path[2:].lstrip("/")
        wsl_path = f"/mnt/{drive_letter}/{path_remainder}"
    else:
        wsl_path = win_path
    return wsl_path

# --- Helper Function for FASTA parsing ---
def read_fasta_lengths(fasta_file):
    """
    Reads a FASTA file and returns a dictionary of {ID: length}
    and a list of all lengths.
    """
    lengths = []
    seq_lengths = {}
    current_len = 0
    current_id = ""
    try:
        with open(fasta_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    if current_id:
                        lengths.append(current_len)
                        seq_lengths[current_id] = current_len
                    current_id = line[1:].split()[0] # Get ID, remove junk after space
                    current_len = 0
                elif line:
                    current_len += len(line)
            # Add the last sequence
            if current_id:
                lengths.append(current_len)
                seq_lengths[current_id] = current_len
        return seq_lengths, lengths
    except FileNotFoundError:
        return None, None
    except Exception as e:
        print(f"[Error reading FASTA] {e}")
        return None, None


# --- Main Application ---

class PhyloPipelineCLI:
    
    def __init__(self):
        # --- Core Parameters ---
        self.conda_env = "bio"
        self.output_dir = "C:\\Users\\u0184116\\OneDrive - mails.ucas.ac.cn\\phylogeny\\iqtree-results\\Amborella trichopoda" # [V11.0] Set User Default
        
        self.protein_files = [] 
        self.hmm_files = []

        # --- Filename Templates ---
        self.fn_cleaned = "01_cleaned_proteins.faa"
        self.fn_hits = "02_hmm_hits.faa"
        self.fn_blast_filtered = "02.5_blast_filtered.faa"
        self.fn_blast_raw_out = "02.5_blast_raw_results.txt"
        self.fn_blast_filter_log = "02.5_blast_filter_log.txt"
        self.fn_len_filtered = "02.8_length_filtered.faa"
        self.fn_len_filter_log = "02.8_length_filter_log.txt"
        self.fn_aligned = "03_aligned.faa"
        self.fn_trimmed = "04_clipkit.faa" 
        # [V14.0] Added ClipKIT log filename
        self.fn_clipkit_log = "04_clipkit.faa.log"
        
        # --- Tool Parameters ---
        # HMMer
        self.hmm_cut_ga = True
        self.cpu_threads = "4"
        
        # BLAST
        self.blast_enabled = True
        self.blast_db_path = r"C:\Users\u0184116\blast\Athaliana_TAIR10_db"
        self.blast_gold_list_path = r"C:\Users\u0184116\blast\List of all 2OGD genes\2-OGD-AT.txt"
        self.blast_evalue = "1e-5"
        self.blast_hits_to_check = "5"
        self.blast_pident = "30.0" # Min percent identity
        self.blast_qcovs = "50.0" # Min query coverage
        
        # Length Filter
        self.len_filter_enabled = False
        self.len_filter_threshold = "0" # Default 0 = do nothing
        
        # MAFFT
        self.mafft_iterate = "0"
        
        # ClipKIT
        self.clipkit_enabled = False 
        self.clipkit_mode = "kpic-gappy"
        self.clipkit_gaps = "0.9" 
        
        # IQ-Tree
        self.iq_m = "MFP"
        self.iq_b = "1000"
        self.iq_bnni = True
        self.iq_t = "AUTO"
        self.iq_pre = "iqtree_result"

    def log_message(self, message, tag="INFO"):
        """
        Logging function: simply prints to terminal
        """
        msg = str(message)
        if not msg.endswith('\n'):
            msg += '\n'
        
        if tag:
            print(f"[{tag}] {msg}", end='')
        else:
            print(msg, end='')
        sys.stdout.flush() 

    # --- Terminal Real-time Logging Engine (Unchanged) ---
    def _run_command_blocking(self, cmd_list, log_prefix, stdout_file=None):
        """
        [Executes in a worker thread]
        This is a *blocking* function that runs a command and streams all output
        to the *terminal* in real-time.
        Returns True (success) or False (failure).
        """
        
        self.log_message(f"Executing: {' '.join(shlex.quote(c) for c in cmd_list)}", log_prefix)
        if stdout_file:
             self.log_message(f"  ... Standard output will be redirected to: {os.path.basename(stdout_file)}", log_prefix)
        
        out_f = None
        stdout_pipe = None
        
        try:
            if stdout_file:
                # MAFFT mode: stdout redirected to a file
                out_f = open(stdout_file, 'w', encoding='utf-8')
                stdout_pipe = out_f
            else:
                # Normal mode (IQ-Tree, HMMer, ClipKIT): stdout redirected to terminal
                stdout_pipe = sys.stderr

            result = subprocess.run(
                cmd_list,
                stdout=stdout_pipe,
                stderr=sys.stderr, # Stream real-time to terminal
                text=True,
                encoding='utf-8',
                check=True 
            )
            
            self.log_message("Execution successful.", log_prefix)
            return True

        except subprocess.CalledProcessError as e:
            self.log_message(f"!!! EXECUTION FAILED !!! (Return Code: {e.returncode})", "ERROR")
            return False
        except FileNotFoundError:
            self.log_message(f"!!! COMMAND NOT FOUND !!!: {cmd_list[0]}", "ERROR")
            self.log_message("Please check if Conda is installed and initialized (conda init).", "ERROR")
            
            is_tool_cmd = False
            tool_name = ""
            for item in cmd_list:
                if 'clipkit' in item: is_tool_cmd = True; tool_name = 'clipkit'; break
                if 'blastp' in item: is_tool_cmd = True; tool_name = 'blastp'; break
            
            if is_tool_cmd:
                self.log_message(f"If the command was '{tool_name}', did you install it in the '{self.conda_env}' env?", "ERROR")

            return False
        except Exception as e:
            self.log_message(f"!!! UNEXPECTED ERROR !!!: {e}", "ERROR")
            return False
        finally:
            if out_f: # Close MAFFT's output file
                out_f.close()
    
    # --- Internal Logic (BLAST, Length, Clean, HMM) (Unchanged) ---
    
    def _internal_blast_filter(self, wsl_out_dir, in_fasta_path):
        out_fasta_path = os.path.join(wsl_out_dir, self.fn_blast_filtered)
        raw_blast_out_path = os.path.join(wsl_out_dir, self.fn_blast_raw_out) 
        filter_log_path = os.path.join(wsl_out_dir, self.fn_blast_filter_log) 
        
        wsl_db_path = win_to_wsl_path(self.blast_db_path)
        wsl_gold_list_path = win_to_wsl_path(self.blast_gold_list_path)

        try:
            # --- 1. Load Gold Standard List FIRST ---
            self.log_message(f"Loading gold standard list from: {wsl_gold_list_path}", "STEP2.5")
            gold_ids = set()
            try:
                with open(wsl_gold_list_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        clean_id = line.split('.')[0].upper()
                        gold_ids.add(clean_id)
            except FileNotFoundError:
                self.log_message(f"ERROR: Gold standard file not found at '{wsl_gold_list_path}'", "ERROR")
                return False
            
            self.log_message(f"Loaded {len(gold_ids)} cleaned, UPPERCASE gold standard IDs.", "STEP2.5")

            # --- 2. Run BLASTp ---
            blast_cmd = [
                'conda', 'run', 
                '-n', self.conda_env,
                'blastp',
                '-query', in_fasta_path,
                '-db', wsl_db_path, 
                '-evalue', self.blast_evalue,
                '-max_target_seqs', self.blast_hits_to_check,
                '-outfmt', '6 qseqid sseqid pident qcovs' 
            ]
            
            self.log_message(f"Executing: {' '.join(shlex.quote(c) for c in blast_cmd)}", "STEP2.5")
            
            result = subprocess.run(
                blast_cmd, 
                stdout=subprocess.PIPE,  # Capture the table
                stderr=sys.stderr,      # Print warnings/logs to terminal
                text=True, 
                encoding='utf-8', 
                check=True
            )
            
            self.log_message("BLASTp complete. Parsing results...", "STEP2.5")
            
            # --- 3. Save Raw BLAST Output ---
            self.log_message(f"Saving raw BLAST output to {self.fn_blast_raw_out}", "STEP2.5")
            with open(raw_blast_out_path, 'w', encoding='utf-8') as f_blast:
                f_blast.write("qseqid\tsseqid\tpident\tqcovs\n") # Write header
                f_blast.write(result.stdout)
            
            # --- 4. Parse BLAST Output ---
            blast_output = result.stdout
            valid_query_ids = set() 
            best_hits = {} # {qseqid: (sseqid, pident, qcovs)}
            
            for line in blast_output.splitlines():
                if not line.strip() or line.startswith('#'):
                    continue
                try:
                    parts = line.split('\t')
                    qseqid = parts[0]
                    sseqid = parts[1] 
                    pident = float(parts[2])
                    qcovs = float(parts[3])
                    
                    sseqid_clean = sseqid.split('.')[0].upper() 

                    # Check all 3 conditions
                    gold_id_match = sseqid_clean in gold_ids
                    pident_match = pident >= float(self.blast_pident)
                    qcovs_match = qcovs >= float(self.blast_qcovs)

                    if gold_id_match and pident_match and qcovs_match:
                        valid_query_ids.add(qseqid)
                        
                        if qseqid not in best_hits:
                            best_hits[qseqid] = (sseqid, pident, qcovs)

                except Exception as e:
                    self.log_message(f"Skipping malformed BLAST line: {line} ({e})", "WARN")
            
            self.log_message(f"Found {len(valid_query_ids)} query sequences passing all filters.", "STEP2.5")

            # --- 5. Filter the FASTA file & Generate Logs ---
            self.log_message(f"Filtering FASTA file... writing to {self.fn_blast_filtered}", "STEP2.5")
            count = 0
            all_query_ids = set()
            deleted_query_ids = set()
            
            with open(out_fasta_path, 'w', encoding='utf-8') as outfile:
                with open(in_fasta_path, 'r', encoding='utf-8') as infile:
                    keep_sequence = False
                    for line in infile:
                        if line.startswith('>'):
                            current_id = line.strip()[1:].split()[0] # Clean ID
                            all_query_ids.add(current_id) 
                            
                            if current_id in valid_query_ids: 
                                keep_sequence = True
                                outfile.write(line) # Write original line
                                count += 1
                            else:
                                keep_sequence = False
                                deleted_query_ids.add(current_id) 
                        elif keep_sequence:
                            outfile.write(line)
            
            self.log_message(f"Wrote {count} filtered sequences to {os.path.basename(out_fasta_path)}", "STEP2.5")
            
            # --- 6. New Detailed Logging to File ---
            self.log_message(f"Saving filter summary to {self.fn_blast_filter_log}", "STEP2.5")
            
            log_lines = []
            log_lines.append(f"--- BLAST Filter Summary ---")
            log_lines.append(f"Filters: E-value <= {self.blast_evalue} | Min P-Ident >= {self.blast_pident}% | Min Q-Covs >= {self.blast_qcovs}%")
            log_lines.append(f"Total sequences in: {len(all_query_ids)}")
            log_lines.append(f"Sequences Kept (passed all filters): {len(valid_query_ids)}")
            log_lines.append(f"Sequences Deleted (failed filters): {len(deleted_query_ids)}")

            if deleted_query_ids:
                log_lines.append("\n--- Deleted Sequences (no match in gold list OR failed quality check) ---")
                for i, deleted_id in enumerate(sorted(list(deleted_query_ids))):
                    log_lines.append(f"  {deleted_id}")
                    if i >= 50 and len(deleted_query_ids) > 51: 
                        log_lines.append(f"  ... and {len(deleted_query_ids) - i - 1} more.")
                        break
            
            with open(filter_log_path, 'w', encoding='utf-8') as f_log:
                for line in log_lines:
                    f_log.write(line + '\n')
                        
            # Also print summary to console
            self.log_message(f"--- BLAST Filter Summary ---", "STEP2.5")
            self.log_message(f"Total sequences in: {len(all_query_ids)}")
            self.log_message(f"Sequences Kept (passed filters): {len(valid_query_ids)}")
            self.log_message(f"Sequences Deleted (failed filters): {len(deleted_query_ids)}")
            if len(deleted_query_ids) > 0:
                self.log_message(f"(See {self.fn_blast_filter_log} for the full list of deleted IDs)", "STEP2.5")

            return True

        except subprocess.CalledProcessError as e:
            self.log_message(f"!!! BLASTP FAILED !!! (Return Code: {e.returncode})", "ERROR")
            self.log_message("--- BLAST Error Output (if any) ---", "ERROR")
            self.log_message(e.stderr or "No error output captured.", tag=None)
            return False
        except FileNotFoundError:
            self.log_message(f"!!! COMMAND NOT FOUND: 'blastp' !!!", "ERROR")
            self.log_message(f"Please install 'blast' in your '{self.conda_env}' environment.", "ERROR")
            return False
        except Exception as e:
            self.log_message(f"Error during BLAST filtering: {e}", "ERROR")
            return False
    
    def _internal_len_filter(self, wsl_out_dir, in_fasta_path):
        out_fasta_path = os.path.join(wsl_out_dir, self.fn_len_filtered)
        log_path = os.path.join(wsl_out_dir, self.fn_len_filter_log)
        
        try:
            threshold = int(self.len_filter_threshold)
            if threshold <= 0:
                self.log_message("Length filter threshold is 0 or less. Skipping.", "STEP2.8")
                # We still need to copy the file for the next step
                import shutil
                shutil.copyfile(in_fasta_path, out_fasta_path)
                self.log_message(f"Copied {os.path.basename(in_fasta_path)} to {os.path.basename(out_fasta_path)}.", "STEP2.8")
                return True

            self.log_message(f"Filtering sequences shorter than {threshold} aa...", "STEP2.8")
            
            count_kept = 0
            deleted_ids = []
            
            with open(out_fasta_path, 'w', encoding='utf-8') as outfile:
                with open(in_fasta_path, 'r', encoding='utf-8') as infile:
                    current_id = ""
                    current_seq = []
                    
                    def write_seq(seq_id, seq_list):
                        nonlocal count_kept
                        seq = "".join(seq_list)
                        if len(seq) >= threshold:
                            outfile.write(f">{seq_id}\n")
                            outfile.write(seq + "\n")
                            count_kept += 1
                        else:
                            deleted_ids.append((seq_id, len(seq)))
                    
                    for line in infile:
                        if line.startswith('>'):
                            if current_id:
                                write_seq(current_id, current_seq)
                            current_id = line.strip()[1:].split()[0]
                            current_seq = []
                        else:
                            current_seq.append(line.strip())
                    
                    if current_id:
                        write_seq(current_id, current_seq)

            self.log_message(f"Wrote {count_kept} filtered sequences to {self.fn_len_filtered}", "STEP2.8")

            # --- Write Log File ---
            self.log_message(f"Saving length filter summary to {self.fn_len_filter_log}", "STEP2.8")
            
            log_lines = []
            log_lines.append(f"--- Length Filter Summary ---")
            log_lines.append(f"Threshold: Remove sequences < {threshold} aa")
            log_lines.append(f"Total sequences in: {count_kept + len(deleted_ids)}")
            log_lines.append(f"Sequences Kept: {count_kept}")
            log_lines.append(f"Sequences Deleted: {len(deleted_ids)}")

            if deleted_ids:
                log_lines.append("\n--- Deleted Sequences (too short) ---")
                deleted_ids.sort(key=lambda x: x[1])
                for seq_id, length in deleted_ids:
                    log_lines.append(f"  {seq_id} (Length: {length} aa)")

            with open(log_path, 'w', encoding='utf-8') as f_log:
                for line in log_lines:
                    f_log.write(line + '\n')
            
            # Print summary to console
            self.log_message(f"--- Length Filter Summary ---", "STEP2.8")
            self.log_message(f"Total sequences in: {count_kept + len(deleted_ids)}")
            self.log_message(f"Sequences Kept: {count_kept}")
            self.log_message(f"Sequences Deleted: {len(deleted_ids)}")
            if deleted_ids:
                self.log_message(f"(See {self.fn_len_filter_log} for the full list of deleted IDs)", "STEP2.8")
            
            return True
            
        except Exception as e:
            self.log_message(f"Error during Length filtering: {e}", "ERROR")
            return False

    def _internal_clean_fasta(self, wsl_out_dir, files_to_clean):
        self.path_cleaned_fasta = os.path.join(wsl_out_dir, self.fn_cleaned)
        
        try:
            self.log_message(f"Cleaning FASTA headers...", "STEP1")
            self.log_message(f"Output file will be: {self.path_cleaned_fasta}", "STEP1")
            count = 0
            with open(self.path_cleaned_fasta, 'w', encoding='utf-8') as outfile:
                for win_path in files_to_clean:
                    wsl_path = win_to_wsl_path(win_path)
                    self.log_message(f"Processing file: {os.path.basename(wsl_path)}", "STEP1")
                    with open(wsl_path, 'r', encoding='utf-8') as infile:
                        for line in infile:
                            if line.startswith('>'):
                                try:
                                    header_id = line.split()[0]
                                    outfile.write(f"{header_id}\n")
                                    count += 1
                                except IndexError:
                                    self.log_message(f"Skipping malformed header: {line.strip()}", "WARN")
                            elif line.strip(): 
                                outfile.write(line)
            
            self.log_message(f"Cleaning complete. Processed {count} sequences.", "STEP1")
            return True

        except Exception as e:
            self.log_message(f"Error during FASTA cleaning: {e}", "ERROR")
            return False

    def _internal_hmm_extract(self, wsl_out_dir, tbl_files, in_fasta_path):
        self.path_hits_fasta = os.path.join(wsl_out_dir, self.fn_hits)
        
        try:
            self.log_message(f"Parsing HMMer hit results...", "STEP2")
            all_hit_ids_list = [] 
            
            for tbl_file in tbl_files:
                self.log_message(f"  ... Reading {os.path.basename(tbl_file)}", "STEP2")
                try:
                    with open(tbl_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if not line.startswith('#'):
                                parts = line.split()
                                if parts:
                                    all_hit_ids_list.append(parts[0]) 
                except FileNotFoundError:
                     self.log_message(f"  ... Warning: tblout file not found {os.path.basename(tbl_file)} (likely no hits)", "WARN")
            
            total_hits_found = len(all_hit_ids_list)
            if total_hits_found == 0:
                self.log_message("No HMMer hits found. Halting pipeline.", "WARN")
                return False
            
            self.log_message(f"Found {total_hits_found} total hits in {len(tbl_files)} tblout files.", "STEP2")

            id_counts = Counter(all_hit_ids_list)
            unique_hit_ids = set(id_counts.keys())
            unique_count = len(unique_hit_ids)
            duplicate_count = total_hits_found - unique_count
            
            self.log_message(f"Found {unique_count} unique protein IDs.", "STEP2")
            self.log_message(f"Removed {duplicate_count} duplicate hits.", "STEP2")

            if duplicate_count > 0:
                duplicates = {pid: count for pid, count in id_counts.items() if count > 1}
                sorted_duplicates = sorted(duplicates.items(), key=lambda item: item[1], reverse=True)
                self.log_message("--- Top 10 Duplicate Hits ---", "STEP2")
                for pid, count in sorted_duplicates[:10]:
                    self.log_message(f"  > {pid} (hit {count} times)", "STEP2")
                if len(sorted_duplicates) > 10:
                    self.log_message("  ... (and others)", "STEP2")

            self.log_message(f"Extracting {unique_count} unique sequences from {os.path.basename(in_fasta_path)}...", "STEP2")
            count = 0
            with open(self.path_hits_fasta, 'w', encoding='utf-8') as outfile:
                with open(in_fasta_path, 'r', encoding='utf-8') as infile:
                    keep_sequence = False
                    for line in infile:
                        if line.startswith('>'):
                            current_id = line.strip()[1:] 
                            if current_id in unique_hit_ids: 
                                keep_sequence = True
                                outfile.write(line)
                                count += 1
                            else:
                                keep_sequence = False
                        elif keep_sequence:
                            outfile.write(line)

            self.log_message(f"Extraction complete. Wrote {count} sequences to {os.path.basename(self.path_hits_fasta)}", "STEP2")
            return True

        except Exception as e:
            self.log_message(f"Error during sequence extraction: {e}", "ERROR")
            return False
            
    # --- [V14.0] New Internal Helper Functions for Step 4.5 ---
    
    def _internal_parse_clipkit_log(self, log_file_wsl):
        """
        Parses the '1 trim other ...' style ClipKIT log file.
        Returns a set of *trimmed* alignment column indices.
        """
        trimmed_sites_set = set()
        try:
            with open(log_file_wsl, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    # Look for lines like "1 trim other ..."
                    if len(parts) >= 2 and parts[1].lower() == 'trim':
                        try:
                            trimmed_sites_set.add(int(parts[0]))
                        except ValueError:
                            continue # First word wasn't a number
        except FileNotFoundError:
            self.log_message(f"ERROR: ClipKIT log file not found: {log_file_wsl}", "ERROR")
            return None
        except Exception as e:
            self.log_message(f"ERROR: Failed to read log file: {e}", "ERROR")
            return None
        
        return trimmed_sites_set

    def _internal_parse_sites_list(self, sites_str):
        """
        Parses a string like "125,130,200-210".
        Returns a set of *original* residue numbers.
        """
        key_sites_set = set()
        if not sites_str:
            self.log_message("ERROR: No sites provided.", "ERROR")
            return None
            
        try:
            parts = sites_str.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    key_sites_set.update(range(start, end + 1))
                elif part:
                    key_sites_set.add(int(part))
        except Exception as e:
            self.log_message(f"ERROR: Could not parse sites list ('{sites_str}'): {e}", "ERROR")
            self.log_message("  ... Format must be '125,130,200-210'", "ERROR")
            return None
        
        return key_sites_set

    def _internal_find_and_map_ref(self, align_file_wsl, ref_id):
        """
        Finds a single reference sequence in the alignment file
        and returns its sequence string and a coordinate map.
        
        Map format: [(align_col, orig_residue_num), ...]
        e.g., [(1, 1), (2, None), (3, 2), (4, None), (5, 3)]
        """
        mapping_list = []
        sequence_str = ""
        residue_count = 0
        align_col_count = 0
        
        found_seq = False
        
        try:
            with open(align_file_wsl, 'r', encoding='utf-8') as f:
                current_id = None
                seq_buffer = []
                
                for line in f:
                    if line.startswith('>'):
                        # 1. Check the sequence we just finished reading
                        if current_id and current_id == ref_id:
                            found_seq = True
                            sequence_str = "".join(seq_buffer)
                            break # Found it, stop reading the file
                        
                        # 2. Prepare for the next sequence
                        current_id = line.strip()[1:].split()[0] # Get ID, remove junk
                        seq_buffer = []
                    elif current_id:
                        seq_buffer.append(line.strip())
                
                # 3. Check the very last sequence in the file
                if not found_seq and current_id and current_id == ref_id:
                    found_seq = True
                    sequence_str = "".join(seq_buffer)

            if not found_seq:
                self.log_message(f"ERROR: Reference ID '{ref_id}' not found in {os.path.basename(align_file_wsl)}", "ERROR")
                self.log_message("  ... Note: ID must be the *exact* string after '>' and before the first space.", "INFO")
                return None, None
                
            # 4. Found it. Now build the coordinate map.
            for char in sequence_str:
                align_col_count += 1
                if char == '-':
                    mapping_list.append((align_col_count, None)) # (Align Col, Original Residue #)
                else:
                    residue_count += 1
                    mapping_list.append((align_col_count, residue_count))
            
            return sequence_str, mapping_list

        except FileNotFoundError:
            self.log_message(f"ERROR: Alignment file not found: {align_file_wsl}", "ERROR")
            return None, None
        except Exception as e:
            self.log_message(f"ERROR: Failed to read alignment file: {e}", "ERROR")
            return None, None

    # --- CLI Workflow ---

    def _get_active_fasta_file(self, wsl_out_dir):
        """Helper function to find the correct input file for the next step"""
        path_len_filtered = os.path.join(wsl_out_dir, self.fn_len_filtered)
        path_blast_filtered = os.path.join(wsl_out_dir, self.fn_blast_filtered)
        path_hmm_hits = os.path.join(wsl_out_dir, self.fn_hits)
        
        if self.len_filter_enabled and os.path.exists(path_len_filtered):
            return path_len_filtered, f"Length-Filtered file ({self.fn_len_filtered})"
        elif self.blast_enabled and os.path.exists(path_blast_filtered):
            return path_blast_filtered, f"BLAST-Filtered file ({self.fn_blast_filtered})"
        elif os.path.exists(path_hmm_hits):
            return path_hmm_hits, f"HMMer hits file ({self.fn_hits})"
        else:
            return None, "No valid input file found (run Step 1 & 2 first)."


    def _validate_step(self):
        if not self.output_dir:
            self.log_message("ERROR: Please set an Output Directory in 'C' (Configure Settings) first!", "ERROR")
            return False, None
        
        wsl_out_dir = win_to_wsl_path(self.output_dir)
        try:
            os.makedirs(wsl_out_dir, exist_ok=True)
        except Exception as e:
            self.log_message(f"Failed to create output directory: {e}", "ERROR")
            return False, None
            
        return True, wsl_out_dir

    def _run_step1(self):
        self.log_message(f"--- Starting Step 1: Pre-process ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        if not self.protein_files:
            self.log_message("ERROR: No protein files added. Please add files in 'C' (Configure Settings).", "ERROR")
            return False
            
        success = self._internal_clean_fasta(wsl_out_dir, self.protein_files)
        if success:
            self.log_message("Step 1 complete.", "PROC")
        return success

    def _run_step2(self):
        self.log_message(f"--- Starting Step 2: HMMer Search ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        path_cleaned_fasta = os.path.join(wsl_out_dir, self.fn_cleaned)
        
        if not os.path.exists(path_cleaned_fasta):
            self.log_message(f"ERROR: Input file not found: {self.fn_cleaned}. Please run Step 1 first.", "ERROR")
            return False
            
        if not self.hmm_files:
            self.log_message("ERROR: No HMM files added. Please add files in 'C' (Configure Settings).", "ERROR")
            return False

        try:
            tbl_files_created = [] 
            all_hmm_ok = True
            
            for i, win_hmm_path in enumerate(self.hmm_files):
                wsl_hmm_path = win_to_wsl_path(win_hmm_path)
                hmm_basename = os.path.basename(wsl_hmm_path)
                
                tbl_out_path = os.path.join(wsl_out_dir, f"02_tblout_{i}_{hmm_basename}.tbl")
                tbl_files_created.append(tbl_out_path)
                log_out_path = os.path.join(wsl_out_dir, f"02_log_{i}_{hmm_basename}.log")
                
                self.log_message(f"--- Running HMM ({i+1}/{len(self.hmm_files)}): {hmm_basename} ---", "STEP2")
                
                cmd = [
                    'conda', 'run', 
                    '--live-stream', 
                    '-n', self.conda_env,
                    'hmmsearch',
                    '--tblout', tbl_out_path,
                    '--cpu', self.cpu_threads,
                    '-o', log_out_path, 
                    wsl_hmm_path,
                    path_cleaned_fasta
                ]
                
                if self.hmm_cut_ga:
                    cmd.insert(6, '--cut_ga')

                success = self._run_command_blocking(cmd, "STEP2")

                if not success:
                    all_hmm_ok = False
                    self.log_message(f"HMM search failed: {hmm_basename}", "ERROR")
                    break 

            if all_hmm_ok:
                self.log_message("All HMM searches complete. Starting sequence extraction...", "STEP2")
                extract_ok = self._internal_hmm_extract(wsl_out_dir, tbl_files_created, path_cleaned_fasta)
                if extract_ok:
                    self.log_message("Step 2 complete.", "PROC")
                return extract_ok
            else:
                 self.log_message("Extraction step skipped due to HMM search failure.", "ERROR")
                 return False
            
        except Exception as e:
            self.log_message(f"Error in HMMer logic: {e}", "ERROR")
            return False

    def _run_step2_5(self):
        self.log_message(f"--- Starting Step 2.5: BLAST Filtering ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        if not self.blast_enabled:
            self.log_message("BLAST Filtering is disabled. Skipping step.", "STEP2.5")
            self.log_message("Step 2.5 complete.", "PROC")
            return True # Not a failure, just skipping

        path_hits_fasta = os.path.join(wsl_out_dir, self.fn_hits)
        
        if not os.path.exists(path_hits_fasta):
            self.log_message(f"ERROR: Input file not found: {self.fn_hits}. Please run Step 2 first.", "ERROR")
            return False
        
        if not self.blast_db_path or not self.blast_gold_list_path:
            self.log_message("ERROR: BLAST DB path or Gold Standard List path not set.", "ERROR")
            self.log_message("Please set them in 'C' -> '5' (Configure Tool Parameters).", "ERROR")
            return False

        success = self._internal_blast_filter(wsl_out_dir, path_hits_fasta)
        if success:
            self.log_message("Step 2.5 complete.", "PROC")
        return success

    def _run_step2_7_analyze(self):
        self.log_message(f"--- Starting Step 2.7: Analyze Sequence Lengths ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False

        input_file, file_desc = self._get_active_fasta_file(wsl_out_dir)
        
        if not input_file:
            self.log_message(f"ERROR: {file_desc}", "ERROR")
            return False
            
        self.log_message(f"Reading sequences from: {file_desc}", "STEP2.7")
        seq_lengths, lengths = read_fasta_lengths(input_file)
        
        if not lengths:
            self.log_message("ERROR: No sequences found in input file.", "ERROR")
            return False

        # Calculate stats with pure Python
        count = len(lengths)
        mean = sum(lengths) / count
        variance = sum([((x - mean) ** 2) for x in lengths]) / count
        std_dev = variance ** 0.5
        lengths.sort()
        minimum = lengths[0]
        maximum = lengths[-1]
        median = lengths[count // 2]
        
        suggested_cutoff = int(mean - (2 * std_dev))
        
        print("\n--- Sequence Length Statistics ---")
        print(f"  Total Sequences: {count}")
        print(f"  Average (Mean):  {mean:.2f} aa")
        print(f"  Median:          {median} aa")
        print(f"  Std. Deviation:  {std_dev:.2f} aa")
        print(f"  Min Length:      {minimum} aa")
        print(f"  Max Length:      {maximum} aa")
        print("------------------------------------")
        print(f"Suggested Cutoff (Mean - 2*StdDev): {suggested_cutoff} aa")
        print(f"To use this, go to 'C' -> '5', set [A] to 'True' and [B] to '{suggested_cutoff}'")
        print("------------------------------------")
        
        return True

    def _run_step2_8_filter(self):
        self.log_message(f"--- Starting Step 2.8: Length Filtering ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        if not self.len_filter_enabled:
            self.log_message("Length Filtering is disabled. Skipping step.", "STEP2.8")
            self.log_message("Step 2.8 complete.", "PROC")
            return True # Not a failure, just skipping
        
        threshold = 0
        try:
            threshold = int(self.len_filter_threshold)
        except ValueError:
            self.log_message(f"ERROR: Invalid Length Threshold '{self.len_filter_threshold}'. Must be a number.", "ERROR")
            return False
            
        if threshold <= 0:
            self.log_message("Length Threshold is 0 or less. Skipping step.", "STEP2.8")
            self.log_message("Step 2.8 complete.", "PROC")
            return True

        input_file, file_desc = self._get_active_fasta_file(wsl_out_dir)
        
        if not input_file:
            self.log_message(f"ERROR: {file_desc}", "ERROR")
            return False
            
        self.log_message(f"Reading sequences from: {file_desc}", "STEP2.8")
        
        success = self._internal_len_filter(wsl_out_dir, input_file)
        if success:
            self.log_message("Step 2.8 complete.", "PROC")
        return success


    def _run_step3(self):
        self.log_message(f"--- Starting Step 3: MAFFT Alignment ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        input_file_for_mafft, file_desc = self._get_active_fasta_file(wsl_out_dir)
        
        if not input_file_for_mafft:
            self.log_message(f"ERROR: {file_desc}", "ERROR")
            return False
            
        self.log_message(f"Using {file_desc} as input.", "STEP3")
        
        path_aligned_fasta = os.path.join(wsl_out_dir, self.fn_aligned)
        
        cmd = [
            'conda', 'run', 
            '--live-stream',
            '-n', self.conda_env,
            'mafft',
            '--auto',
            '--maxiterate', self.mafft_iterate,
            input_file_for_mafft
        ]
        
        success = self._run_command_blocking(
            cmd, 
            "STEP3", 
            stdout_file=path_aligned_fasta 
        )
        
        if success:
            self.log_message("Step 3 complete.", "PROC")
        return success

    def _run_step4(self):
        self.log_message(f"--- Starting Step 4: ClipKIT Trimming ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False
        
        path_aligned_fasta = os.path.join(wsl_out_dir, self.fn_aligned)

        if not self.clipkit_enabled:
            self.log_message("ClipKIT is disabled. Skipping step.", "STEP4")
            self.log_message("Step 4 complete.", "PROC")
            return True # Skipping is not failure
        
        self.log_message("ClipKIT is enabled. Running smart trimming...", "INFO")
        
        if not os.path.exists(path_aligned_fasta):
            self.log_message(f"ERROR: Input file not found: {self.fn_aligned}. Please run Step 3 first.", "ERROR")
            return False
            
        path_trimmed_fasta = os.path.join(wsl_out_dir, self.fn_trimmed)
        
        cmd = [
            'conda', 'run', 
            '--live-stream',
            '-n', self.conda_env,
            'clipkit',
            path_aligned_fasta, # Positional argument
            '--output', path_trimmed_fasta,
            '--mode', self.clipkit_mode,
            '--gaps', self.clipkit_gaps,
            '--log' # This creates the .log file
        ]
        
        success = self._run_command_blocking(cmd, "STEP4")
        
        if success:
            self.log_message("Step 4 complete.", "PROC")
            # [V14.0] Inform user they can now run 4.5
            self.log_message(f"ClipKIT log file created: {self.fn_clipkit_log}", "INFO")
            self.log_message("You can now run 'Step 4.5' to check specific sites.", "INFO")
        return success
    
    # --- [V14.0] NEW STEP ---
    def _run_step4_5_check(self):
        """
        New interactive step to check the trimming status of key sites.
        """
        self.log_message(f"--- Starting Step 4.5: Check Trimming Status ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False

        # --- Check for required files ---
        path_aligned = os.path.join(wsl_out_dir, self.fn_aligned)
        path_clipkit_log = os.path.join(wsl_out_dir, self.fn_clipkit_log)

        if not os.path.exists(path_aligned):
            self.log_message(f"ERROR: Alignment file not found: {self.fn_aligned}", "ERROR")
            self.log_message("  ... Please run Step 3 (MAFFT) first.", "INFO")
            return False
            
        if not os.path.exists(path_clipkit_log):
            self.log_message(f"ERROR: ClipKIT log file not found: {self.fn_clipkit_log}", "ERROR")
            self.log_message("  ... Please run Step 4 (ClipKIT) with trimming enabled first.", "INFO")
            return False

        # --- Load trimmed sites once ---
        self.log_message(f"Loading ClipKIT log from {self.fn_clipkit_log}...", "STEP4.5")
        trimmed_sites_set = self._internal_parse_clipkit_log(path_clipkit_log)
        if trimmed_sites_set is None:
            return False # Error already logged by internal function
        
        self.log_message(f"Successfully loaded {len(trimmed_sites_set)} trimmed columns.", "STEP4.5")

        # --- Enter interactive loop ---
        while True:
            print("\n--- Key Site Checker ---")
            print("Example ID: AT1G12345.1")
            print("Example Sites: 125,130,200-210")
            
            ref_id = input("Enter Reference ID (or 'B' to go back to Main Menu): ").strip()
            if ref_id.upper() == 'B':
                break
            
            if not ref_id:
                self.log_message("ERROR: Reference ID cannot be empty.", "ERROR")
                continue

            sites_str = input(f"Enter Original Sites for '{ref_id}': ").strip()
            
            # --- 1. Parse sites ---
            key_sites_set = self._internal_parse_sites_list(sites_str)
            if key_sites_set is None:
                continue # Error already logged
                
            # --- 2. Find and Map Reference Sequence ---
            self.log_message(f"Searching for '{ref_id}' in {self.fn_aligned}...", "STEP4.5")
            sequence_str, mapping_list = self._internal_find_and_map_ref(path_aligned, ref_id)
            if sequence_str is None:
                continue # Error already logged
            
            self.log_message(f"Found! Analyzing {len(key_sites_set)} key sites...", "STEP4.5")

            # --- 3. Generate and Print Report ---
            print("\n" + ("-" * 50))
            print(f"      *** Key Site Report for {ref_id} ***")
            print("-" * 50)
            
            found_count = 0
            for (align_col, orig_res_num) in mapping_list:
                
                # Check if this is one of the sites we care about
                if orig_res_num in key_sites_set:
                    found_count += 1
                    
                    # Get the amino acid at this position
                    aa = sequence_str[align_col - 1] # (list is 0-indexed)
                    
                    # Check if this *alignment column* was trimmed
                    is_trimmed = align_col in trimmed_sites_set
                    status = "❌ TRIMMED" if is_trimmed else "✅ KEPT"
                    
                    # Print the report line
                    print(f"  [Site {orig_res_num: <4} (AA: {aa})] -> maps to [Align Col {align_col: <4}] -> Status: {status}")

            print("-" * 50)
            print(f"Report complete: {found_count} / {len(key_sites_set)} key sites were found and checked.")
            if found_count < len(key_sites_set):
                self.log_message("Some sites were not listed? They might be Gaps in your reference sequence.", "WARN")
            print("-" * 50)

        self.log_message("Returning to Main Menu.", "STEP4.5")
        return True

    def _run_step5(self):
        self.log_message(f"--- Starting Step 5: IQ-Tree Build ---", "PROC")
        valid, wsl_out_dir = self._validate_step()
        if not valid: return False

        input_seq_file = ""
        path_aligned = os.path.join(wsl_out_dir, self.fn_aligned)
        path_trimmed = os.path.join(wsl_out_dir, self.fn_trimmed) 

        if self.clipkit_enabled:
            if not os.path.exists(path_trimmed):
                self.log_message(f"ERROR: ClipKIT enabled, but input file not found: {self.fn_trimmed}.", "ERROR")
                return False
            input_seq_file = path_trimmed
            self.log_message("Using trimmed file (04_clipkit.faa) for IQ-Tree.", "STEP5")
        else:
            if not os.path.exists(path_aligned):
                self.log_message(f"ERROR: ClipKIT disabled, but input file not found: {self.fn_aligned}.", "ERROR")
                return False
            input_seq_file = path_aligned
            self.log_message("Using untrimmed alignment file (03_aligned.faa) for IQ-Tree.", "STEP5")
        
        prefix_path = os.path.join(wsl_out_dir, self.iq_pre)
        
        cmd = [
            'conda', 'run', 
            '--live-stream',
            '-n', self.conda_env,
            'iqtree',
            '-s', input_seq_file,
            '-st', 'AA', 
            '-m', self.iq_m,
            '-B', self.iq_b,
            '-T', self.iq_t,
            '-pre', prefix_path
        ]
        
        if self.iq_bnni:
            cmd.append('-bnni')
        
        success = self._run_command_blocking(cmd, "STEP5")
        
        if success:
            self.log_message("--- PIPELINE FINISHED ---", "PROC")
            self.log_message("All steps completed successfully.", "PROC")
        return success

    # --- CLI Menus ---
    
    def _show_current_settings(self):
        print("\n--- Current Settings ---")
        print(f"  [1] Conda Environment : {self.conda_env}")
        print(f"  [2] Output Directory  : {self.output_dir or 'Not Set'}")
        print(f"      (WSL Path)      : {win_to_wsl_path(self.output_dir) or 'N/A'}")
        print(f"  [3] Protein Files     : {len(self.protein_files)} files (See 'C' -> '3' to list)")
        print(f"  [4] HMM Files         : {len(self.hmm_files)} files (See 'C' -> '4' to list)")
        print("\n--- Tool Parameters ---")
        print(f"  [HMMer] --cpu: {self.cpu_threads} | --cut_ga: {self.hmm_cut_ga}")
        print(f"  [BLAST] Enabled: {self.blast_enabled} | Hits: {self.blast_hits_to_check} | E-value: {self.blast_evalue}")
        print(f"    └> P-Ident: {self.blast_pident}% | Q-Covs: {self.blast_qcovs}%")
        print(f"    └> DB Path (Win): {self.blast_db_path or 'Not Set'}")
        print(f"    └> Gold List (Win): {self.blast_gold_list_path or 'Not Set'}")
        print(f"  [Length Filter] Enabled: {self.len_filter_enabled} | Threshold: {self.len_filter_threshold} aa")
        print(f"  [MAFFT] --maxiterate: {self.mafft_iterate}")
        print(f"  [ClipKIT] Enabled: {self.clipkit_enabled} | Mode: {self.clipkit_mode} | Gaps (--gaps): {self.clipkit_gaps}")
        print(f"  [IQ-Tree] -m: {self.iq_m} | -B: {self.iq_b} | -T: {self.iq_t} | -bnni: {self.iq_bnni}")
        print("------------------------")
    
    def _set_output_dir(self):
        print("\n--- Set Output Directory ---")
        print("Please copy the folder path from Windows File Explorer and paste it here.")
        print("!!! IMPORTANT: Use a simple path (e.g., C:\\phylo_run). Avoid OneDrive or network drives.")
        print(f"Current: {self.output_dir or 'Not Set'}")
        path = input("Paste Windows path: ").strip()
        path = path.strip('"') # Handle quotes
        if path:
            self.output_dir = path
            self.log_message(f"Output directory set to: {self.output_dir}", "SETUP")
        else:
            print("No input. No change.")

    def _manage_files(self, file_list, list_name):
        """Generic function to manage protein and HMM files"""
        while True:
            print(f"\n--- Manage {list_name} ---")
            if not file_list:
                print("List is currently empty.")
            else:
                print("Current files:")
                for i, f in enumerate(file_list):
                    print(f"  {i+1}: {f}")
            print("\nOptions:")
            print("  A - Add File (Paste full Windows path, quotes OK)")
            print("  C - Clear List")
            print("  B - Back to previous menu")
            choice = input("Enter option (A/C/B): ").strip().upper()
            
            if choice == 'A':
                path = input("Paste Windows path: ").strip()
                path = path.strip('"')
                
                wsl_path = win_to_wsl_path(path)
                
                if path and os.path.exists(wsl_path): # Check converted WSL path
                    file_list.append(path) # Store original Windows path
                    print(f"Added: {path}")
                elif not path:
                    print("No path entered.")
                else:
                    print(f"Error: Path '{path}' (checked as '{wsl_path}') not found by WSL.")
            elif choice == 'C':
                file_list.clear()
                print("List cleared.")
            elif choice == 'B':
                break

    def _configure_tool_params(self):
        """Configure HMMer, BLAST, MAFFT, ClipKIT, IQ-Tree parameters"""
        while True:
            print("\n--- Configure Tool Parameters ---")
            print("  [HMMer]")
            print(f"    [1] HMMer --cpu       : {self.cpu_threads}")
            print(f"    [2] HMMer --cut_ga    : {self.hmm_cut_ga}")
            print("  [BLAST Filter]")
            print(f"    [3] BLAST Filter Enable : {self.blast_enabled}")
            print(f"    [4] BLAST DB Path (Win) : {self.blast_db_path or 'Not Set'}")
            print(f"    [5] Gold List Path (Win): {self.blast_gold_list_path or 'Not Set'}")
            print(f"    [6] Hits to Check       : {self.blast_hits_to_check} (BLAST recommends 5)")
            print(f"    [7] E-value             : {self.blast_evalue}")
            print(f"    [8] Min P-Ident (%)     : {self.blast_pident} (e.g., 30.0)")
            print(f"    [9] Min Q-Covs (%)    : {self.blast_qcovs} (e.g., 50.0)")
            print("  [Length Filter]")
            print(f"    [A] Length Filter Enable: {self.len_filter_enabled}")
            print(f"    [B] Length Threshold (aa): {self.len_filter_threshold} (0 = disabled)")
            print("  [MAFFT/ClipKIT/IQ-Tree]")
            print(f"    [C] MAFFT --maxiterate: {self.mafft_iterate}")
            print(f"    [D] ClipKIT Enable      : {self.clipkit_enabled}")
            print(f"    [E] ClipKIT Mode        : {self.clipkit_mode}")
            print(f"    [F] ClipKIT Gaps (--gaps) : {self.clipkit_gaps}")
            print(f"    [G] IQ-Tree -B (BS)     : {self.iq_b}")
            print(f"    [H] IQ-Tree -T (CPU)    : {self.iq_t}")
            print(f"  [Q] Back to previous menu")
            
            choice = input("Select parameter to change (1-H, Q): ").strip().upper()
            
            if choice == '1':
                val = input(f"Enter --cpu value [{self.cpu_threads}]: ").strip()
                if val: self.cpu_threads = val
            elif choice == '2':
                self.hmm_cut_ga = not self.hmm_cut_ga
                print(f"--cut_ga set to: {self.hmm_cut_ga}")
            elif choice == '3':
                self.blast_enabled = not self.blast_enabled
                print(f"BLAST Filtering enabled set to: {self.blast_enabled}")
            elif choice == '4':
                print("Paste the *Windows path* to your BLAST DB name (e.g., C:\\blast_db\\athaliana_db)")
                val = input(f"Enter path [{self.blast_db_path}]: ").strip().strip('"')
                if val: self.blast_db_path = val
            elif choice == '5':
                print("Paste the *Windows path* to your gold standard list (e.g., C:\\blast_db\\gold_list.txt)")
                val = input(f"Enter path [{self.blast_gold_list_path}]: ").strip().strip('"')
                if val: self.blast_gold_list_path = val
            elif choice == '6':
                val = input(f"Enter Hits to Check [{self.blast_hits_to_check}]: ").strip()
                if val: self.blast_hits_to_check = val
            elif choice == '7':
                val = input(f"Enter E-value [{self.blast_evalue}]: ").strip()
                if val: self.blast_evalue = val
            elif choice == '8':
                val = input(f"Enter Min Percent Identity [{self.blast_pident}]: ").strip()
                if val: self.blast_pident = val
            elif choice == '9':
                val = input(f"Enter Min Query Coverage % [{self.blast_qcovs}]: ").strip()
                if val: self.blast_qcovs = val
            elif choice == 'A':
                self.len_filter_enabled = not self.len_filter_enabled
                print(f"Length Filter enabled set to: {self.len_filter_enabled}")
            elif choice == 'B':
                val = input(f"Enter Min Length Threshold (aa) [{self.len_filter_threshold}]: ").strip()
                if val: self.len_filter_threshold = val
            elif choice == 'C':
                val = input(f"Enter --maxiterate value [{self.mafft_iterate}]: ").strip()
                if val: self.mafft_iterate = val
            elif choice == 'D':
                self.clipkit_enabled = not self.clipkit_enabled
                print(f"ClipKIT enabled set to: {self.clipkit_enabled}")
            elif choice == 'E':
                print("Available modes: 'kpic-gappy' (default), 'gappy', 'kpic'")
                val = input(f"Enter ClipKIT mode [{self.clipkit_mode}]: ").strip()
                if val in ['kpic-gappy', 'gappy', 'kpic']:
                    self.clipkit_mode = val
                else:
                    print("Invalid mode. No change.")
            elif choice == 'F':
                val = input(f"Enter ClipKIT Gaps (--gaps) threshold (0.0-1.0) [{self.clipkit_gaps}]: ").strip()
                if val: self.clipkit_gaps = val
            elif choice == 'G':
                val = input(f"Enter -B (Bootstrap) value [{self.iq_b}]: ").strip()
                if val: self.iq_b = val
            elif choice == 'H':
                val = input(f"Enter -T (Threads) value [{self.iq_t}]: ").strip()
                if val: self.iq_t = val
            elif choice == 'Q':
                break

    def _configure_settings(self):
        """Show settings menu"""
        while True:
            print("\n--- Configuration Menu ---")
            print(f"  [1] Set Conda Environment (Current: {self.conda_env})")
            print(f"  [2] Set Output Directory (Current: {self.output_dir or 'N/A'})")
            print(f"  [3] Manage Protein Files (Current: {len(self.protein_files)})")
            print(f"  [4] Manage HMM Files (Current: {len(self.hmm_files)})")
            print(f"  [5] Configure Tool Parameters (HMMer, BLAST, ...)")
            print(f"  [B] Back to Main Menu")
            choice = input("Enter option (1-5, B): ").strip().upper()
            
            if choice == '1':
                val = input(f"Enter Conda env name [{self.conda_env}]: ").strip()
                if val: self.conda_env = val
            elif choice == '2':
                self._set_output_dir()
            elif choice == '3':
                self._manage_files(self.protein_files, "Protein Files")
            elif choice == '4':
                self._manage_files(self.hmm_files, "HMM Files")
            elif choice == '5':
                self._configure_tool_params()
            elif choice == 'B':
                break

    def run(self):
        """
        Run the main menu loop
        """
        print("--- Welcome to the Bioinformatics Pipeline CLI (v14.0-EN) ---")
        print("--- (Added interactive ClipKIT site checker) ---")
        print("Logs and progress will be displayed in this terminal.")
        
        while True:
            print("\n========== MAIN MENU ==========")
            print("  [C] Configure Settings (Conda, Paths, Files, Params)")
            print("  [S] Show Current Settings")
            print("-------------------------------")
            print("  [1] Run Step 1: Clean FASTA")
            print("  [2] Run Step 2: HMMer Search")
            print("  [2.5] Run Step 2.5: BLAST Filter")
            print("  [2.7] Run Step 2.7: Analyze Sequence Lengths (Read-Only)")
            print("  [2.8] Run Step 2.8: Run Length Filter (Optional)")
            print("  [3] Run Step 3: MAFFT Align")
            print("  [4] Run Step 4: ClipKIT Trim")
            # [V14.0] New Menu Option
            print("  [4.5] Run Step 4.5: Check Trimming (Interactive)")
            print("  [5] Run Step 5: IQ-Tree Build")
            print("  [A] Run ALL Steps (1-5)")
            print("-------------------------------")
            print("  [Q] Quit")
            
            choice = input("Please enter your choice: ").strip().upper()
            
            if choice == 'C':
                self._configure_settings()
            elif choice == 'S':
                self._show_current_settings()
            
            elif choice == '1':
                self._run_step1()
            elif choice == '2':
                self._run_step2()
            elif choice == '2.5':
                self._run_step2_5()
            elif choice == '2.7':
                self._run_step2_7_analyze()
            elif choice == '2.8':
                self._run_step2_8_filter()
            elif choice == '3':
                self._run_step3()
            elif choice == '4':
                self._run_step4()
            # [V14.0] New Menu Choice
            elif choice == '4.5':
                self._run_step4_5_check()
            elif choice == '5':
                self._run_step5()
            
            elif choice == 'A':
                print("--- Starting Full Pipeline (All Steps) ---")
                if not self._run_step1(): 
                    self.log_message("Step 1 failed. Halting pipeline.", "ERROR"); continue
                if not self._run_step2(): 
                    self.log_message("Step 2 failed. Halting pipeline.", "ERROR"); continue
                if not self._run_step2_5(): # This will skip if disabled, returns True
                    self.log_message("Step 2.5 failed. Halting pipeline.", "ERROR"); continue
                if not self._run_step2_8_filter(): # This will skip if disabled
                    self.log_message("Step 2.8 failed. Halting pipeline.", "ERROR"); continue
                if not self._run_step3(): 
                    self.log_message("Step 3 failed. Halting pipeline.", "ERROR"); continue
                if not self._run_step4(): # This will skip if disabled
                    self.log_message("Step 4 failed. Halting pipeline.", "ERROR"); continue
                # Note: Step 4.5 is interactive and skipped in 'Run ALL'
                if not self._run_step5(): 
                    self.log_message("Step 5 failed. Halting pipeline.", "ERROR"); continue
                print("--- Full Pipeline Finished ---")
                
            elif choice == 'Q':
                print("Exiting program.")
                break
            else:
                print("Invalid option, please try again.")

# --- Start Application ---
if __name__ == "__main__":
    if sys.version_info < (3, 6):
        print("Error: This script requires Python 3.6 or newer.")
        sys.exit(1)
        
    try:
        app = PhyloPipelineCLI()
        app.run()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Exiting.")
        sys.exit(0)
