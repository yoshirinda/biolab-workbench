import {
  genbankToJson,
  fastaToJson,
  jsonToGenbank,
  jsonToFasta,
  snapgeneToJson,
  anyToJson
} from "@teselagen/bio-parsers";

export interface ParsedSequence {
  name: string;
  seq: string;
  circular?: boolean;
  features?: Array<{
    name: string;
    start: number;
    end: number;
    type?: string;
    direction?: 1 | -1;
    color?: string;
  }>;
  description?: string;
  type?: 'dna' | 'rna' | 'protein';
}

/**
 * Parse various sequence file formats using TeselaGen bio-parsers
 * 
 * Supported formats:
 * - GenBank (.gb, .genbank)
 * - FASTA (.fasta, .fa, .faa, .fna)
 * - SnapGene (.dna)
 * - JSON (TeselaGen format)
 */
export async function parseSequenceFile(file: File): Promise<ParsedSequence[]> {
  const text = await file.text();
  const ext = file.name.split('.').pop()?.toLowerCase() || '';
  
  try {
    let parsedData: any;
    
    switch(ext) {
      case 'gb':
      case 'genbank':
        parsedData = await genbankToJson(text);
        break;
        
      case 'fasta':
      case 'fa':
      case 'faa':
      case 'fna':
        parsedData = await fastaToJson(text, { fileName: file.name });
        break;
        
      case 'dna':
        parsedData = await snapgeneToJson(text);
        break;
        
      case 'json':
        parsedData = JSON.parse(text);
        break;
        
      default:
        // Try to auto-detect format using anyToJson
        parsedData = await anyToJson(text, { fileName: file.name });
    }
    
    // Convert to array if single sequence
    const sequences = Array.isArray(parsedData) ? parsedData : [parsedData];
    
    // Convert to our standard format
    return sequences.map(convertToStandardFormat);
    
  } catch (error: any) {
    console.error('File parsing error:', error);
    throw new Error(`Failed to parse ${file.name}: ${error.message}`);
  }
}

/**
 * Convert TeselaGen format to our standard format
 */
function convertToStandardFormat(parsed: any): ParsedSequence {
  return {
    name: parsed.name || parsed.id || 'Untitled',
    seq: parsed.sequence || parsed.seq || '',
    circular: parsed.circular || false,
    features: (parsed.features || []).map((f: any) => ({
      name: f.name || f.label || f.type,
      start: (f.start || 0) + 1, // Convert to 1-based indexing
      end: (f.end || 0) + 1,
      type: f.type || 'misc_feature',
      direction: f.strand || f.direction || 1,
      color: f.color || getDefaultFeatureColor(f.type)
    })),
    description: parsed.description || parsed.comment || '',
    type: detectSequenceType(parsed.sequence || parsed.seq || '')
  };
}

/**
 * Detect sequence type from content
 */
function detectSequenceType(seq: string): 'dna' | 'rna' | 'protein' {
  const cleanSeq = seq.toUpperCase().replace(/[^A-Z]/g, '');
  
  // Check for RNA (has U but no T)
  if (cleanSeq.includes('U') && !cleanSeq.includes('T')) {
    return 'rna';
  }
  
  // Check for protein (has amino acid specific characters)
  const proteinChars = /[EFILPQZ]/;
  if (proteinChars.test(cleanSeq)) {
    return 'protein';
  }
  
  // Default to DNA
  return 'dna';
}

/**
 * Get default color for feature types (matching Geneious colors)
 */
function getDefaultFeatureColor(type?: string): string {
  const colorMap: Record<string, string> = {
    'CDS': '#ff7875',
    'gene': '#ff7875',
    'promoter': '#ffa940',
    'terminator': '#9254de',
    'RBS': '#52c41a',
    'misc_feature': '#9DEAED',
    'primer': '#FFD700',
    'origin': '#87d068',
    'regulatory': '#fa8c16'
  };
  
  return colorMap[type || ''] || '#9DEAED';
}

/**
 * Convert parsed sequences to GenBank format string
 */
export function toGenbankFormat(sequence: ParsedSequence): string {
  try {
    // Convert our format back to TeselaGen format
    const teselagenFormat = {
      name: sequence.name,
      sequence: sequence.seq,
      circular: sequence.circular || false,
      features: (sequence.features || []).map(f => ({
        name: f.name,
        start: f.start - 1, // Convert back to 0-based
        end: f.end - 1,
        type: f.type || 'misc_feature',
        strand: f.direction || 1,
        color: f.color
      })),
      description: sequence.description || ''
    };
    
    // Use bio-parsers to convert to GenBank format
    return jsonToGenbank(teselagenFormat, { reformatSeqName: false });
  } catch (error: any) {
    console.error('GenBank export error:', error);
    throw new Error(`Failed to export to GenBank: ${error.message}`);
  }
}

/**
 * Convert parsed sequences to FASTA format string
 */
export function toFastaFormat(sequences: ParsedSequence[]): string {
  return sequences.map(seq => {
    // Convert to TeselaGen format and use jsonToFasta
    const teselagenFormat = {
      name: seq.name,
      sequence: seq.seq,
      description: seq.description || ''
    };
    return jsonToFasta(teselagenFormat, { reformatSeqName: false });
  }).join('\n\n');
}

/**
 * Parse text that might contain gene IDs or FASTA headers
 */
export function parseGeneIds(text: string): string[] {
  const ids: string[] = [];
  const lines = text.split('\n');
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    
    // Parse FASTA header
    if (trimmed.startsWith('>')) {
      const id = trimmed.substring(1).split(/\s+/)[0];
      if (id) ids.push(id);
    } else {
      // Parse space/comma/tab separated IDs
      const tokens = trimmed.split(/[\s,;]+/);
      for (const token of tokens) {
        // Filter out obvious sequence data (too long)
        if (token.length > 0 && token.length <= 30) {
          // Remove common prefixes/suffixes
          const cleaned = token.replace(/^[>|]+|[|<]+$/g, '');
          if (cleaned && !/^[ATCGUN]+$/i.test(cleaned)) {
            ids.push(cleaned);
          }
        }
      }
    }
  }
  
  // Remove duplicates and return
  return Array.from(new Set(ids));
}

/**
 * Read file as text
 */
export function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target?.result as string);
    reader.onerror = (e) => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
}

/**
 * Download text as file
 */
export function downloadTextFile(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}