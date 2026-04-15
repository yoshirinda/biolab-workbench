import { BioSequence, Feature } from '../types/biolab';
import { v4 as uuidv4 } from 'uuid';

export const calculateGC = (seq: string): number => {
  if (!seq) return 0;
  const g = (seq.match(/G/gi) || []).length;
  const c = (seq.match(/C/gi) || []).length;
  return parseFloat(((g + c) / seq.length * 100).toFixed(1));
};

export interface ORF {
  start: number;
  end: number;
  frame: number;
  strand: '+' | '-';
  length: number;
  protein: string;
}

const DNA_WEIGHTS: Record<string, number> = {
  A: 313.2,
  T: 304.2,
  G: 329.2,
  C: 289.2,
  U: 290.2,
  N: 0,
};

const AA_WEIGHTS: Record<string, number> = {
  A: 89.09, R: 174.2, N: 132.12, D: 133.1, C: 121.16,
  E: 147.13, Q: 146.15, G: 75.07, H: 155.16, I: 131.18,
  L: 131.18, K: 146.19, M: 149.21, F: 165.19, P: 115.13,
  S: 105.09, T: 119.12, W: 204.23, Y: 181.19, V: 117.15,
  X: 0,
};

export const formatNumber = (num: number): string => {
  return Number(num || 0).toLocaleString('en-US', { maximumFractionDigits: 2 });
};

export const calculateMolecularWeight = (
  seq: string,
  type: 'nucleotide' | 'protein' | string = 'nucleotide'
): number => {
  const clean = (seq || '').toUpperCase().replace(/[^A-Z]/g, '');
  if (!clean) return 0;

  if (type === 'protein') {
    let total = 0;
    for (const aa of clean) {
      total += AA_WEIGHTS[aa] || 0;
    }
    // Remove water mass for each peptide bond.
    if (clean.length > 1) {
      total -= (clean.length - 1) * 18.015;
    }
    return parseFloat(total.toFixed(2));
  }

  let total = 0;
  for (const base of clean) {
    total += DNA_WEIGHTS[base] || 0;
  }
  return parseFloat(total.toFixed(2));
};

export const calculateTm = (seq: string): number => {
  const clean = (seq || '').toUpperCase().replace(/[^ATGC]/g, '');
  if (!clean) return 0;

  const a = (clean.match(/A/g) || []).length;
  const t = (clean.match(/T/g) || []).length;
  const g = (clean.match(/G/g) || []).length;
  const c = (clean.match(/C/g) || []).length;

  if (clean.length < 14) {
    return (a + t) * 2 + (g + c) * 4;
  }

  // Simple long-oligo approximation.
  return parseFloat((64.9 + (41 * (g + c - 16.4)) / clean.length).toFixed(2));
};

export const getNucleotideComposition = (seq: string): Record<string, number> => {
  const clean = (seq || '').toUpperCase().replace(/[^ATGCN]/g, '');
  const counts: Record<string, number> = { A: 0, T: 0, G: 0, C: 0, N: 0 };
  for (const base of clean) {
    counts[base] = (counts[base] || 0) + 1;
  }
  return counts;
};

export const getAminoAcidComposition = (seq: string): Record<string, number> => {
  const clean = (seq || '').toUpperCase().replace(/[^A-Z]/g, '');
  const counts: Record<string, number> = {};
  for (const aa of clean) {
    counts[aa] = (counts[aa] || 0) + 1;
  }
  return counts;
};

export const getReverseComplement = (seq: string): string => {
  const complement: { [key: string]: string } = {
    A: 'T', T: 'A', C: 'G', G: 'C',
    a: 't', t: 'a', c: 'g', g: 'c',
    N: 'N', n: 'n'
  };
  return seq.split('').reverse().map(base => complement[base] || base).join('');
};

const CODON_TABLE: { [key: string]: string } = {
  'ATA':'I', 'ATC':'I', 'ATT':'I', 'ATG':'M',
  'ACA':'T', 'ACC':'T', 'ACG':'T', 'ACT':'T',
  'AAC':'N', 'AAT':'N', 'AAA':'K', 'AAG':'K',
  'AGC':'S', 'AGT':'S', 'AGA':'R', 'AGG':'R',
  'CTA':'L', 'CTC':'L', 'CTG':'L', 'CTT':'L',
  'CCA':'P', 'CCC':'P', 'CCG':'P', 'CCT':'P',
  'CAC':'H', 'CAT':'H', 'CAA':'Q', 'CAG':'Q',
  'CGA':'R', 'CGC':'R', 'CGG':'R', 'CGT':'R',
  'GTA':'V', 'GTC':'V', 'GTG':'V', 'GTT':'V',
  'GCA':'A', 'GCC':'A', 'GCG':'A', 'GCT':'A',
  'GAC':'D', 'GAT':'D', 'GAA':'E', 'GAG':'E',
  'GGA':'G', 'GGC':'G', 'GGG':'G', 'GGT':'G',
  'TCA':'S', 'TCC':'S', 'TCG':'S', 'TCT':'S',
  'TTC':'F', 'TTT':'F', 'TTA':'L', 'TTG':'L',
  'TAC':'Y', 'TAT':'Y', 'TAA':'_', 'TAG':'_',
  'TGC':'C', 'TGT':'C', 'TGA':'_', 'TGG':'W',
};

export const translateSequence = (seq: string): string => {
  let protein = "";
  const cleanSeq = seq.toUpperCase().replace(/[^ATCG]/g, "");
  for (let i = 0; i < cleanSeq.length - 2; i += 3) {
    const codon = cleanSeq.substring(i, i + 3);
    protein += CODON_TABLE[codon] || "X";
  }
  return protein;
};

const START_CODON = 'ATG';
const STOP_CODONS = new Set(['TAA', 'TAG', 'TGA']);

export const findORFs = (seq: string, minLength = 100): ORF[] => {
  const clean = (seq || '').toUpperCase().replace(/[^ATGC]/g, '');
  if (!clean) return [];

  const results: ORF[] = [];
  const reverse = getReverseComplement(clean);

  const scanStrand = (strandSeq: string, strand: '+' | '-', offsetMap: (start: number, end: number) => [number, number]) => {
    for (let frame = 0; frame < 3; frame++) {
      for (let i = frame; i <= strandSeq.length - 3; i += 1) {
        const codon = strandSeq.slice(i, i + 3);
        if (codon !== START_CODON) continue;

        for (let j = i + 3; j <= strandSeq.length - 3; j += 3) {
          const stop = strandSeq.slice(j, j + 3);
          if (!STOP_CODONS.has(stop)) continue;

          const ntLength = j + 3 - i;
          if (ntLength < minLength) break;

          const codingSeq = strandSeq.slice(i, j + 3);
          const protein = translateSequence(codingSeq).replace(/_+$/g, '');
          const [start, end] = offsetMap(i, j + 3);

          results.push({
            start: start + 1,
            end,
            frame: frame + 1,
            strand,
            length: ntLength,
            protein,
          });
          break;
        }
      }
    }
  };

  scanStrand(clean, '+', (s, e) => [s, e]);
  scanStrand(reverse, '-', (s, e) => [clean.length - e, clean.length - s]);

  return results.sort((a, b) => b.length - a.length);
};

export const createNewSequence = (name: string, seq: string, type: 'nucleotide' | 'protein' = 'nucleotide'): BioSequence => {
  return {
    id: uuidv4(),
    seq: seq,
    features: [],
    meta: {
      name: name,
      length: seq.length,
      created: new Date().toISOString(),
      topology: 'linear',
      type: type,
      gcContent: type === 'nucleotide' ? calculateGC(seq) : undefined
    }
  };
};
