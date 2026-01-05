import { BioSequence, Feature } from '../types/biolab';
import { v4 as uuidv4 } from 'uuid';

export const calculateGC = (seq: string): number => {
  if (!seq) return 0;
  const g = (seq.match(/G/gi) || []).length;
  const c = (seq.match(/C/gi) || []).length;
  return parseFloat(((g + c) / seq.length * 100).toFixed(1));
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
