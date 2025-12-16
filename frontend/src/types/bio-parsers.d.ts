declare module '@teselagen/bio-parsers' {
  export interface ParseOptions {
    fileName?: string;
    isProtein?: boolean;
    reformatSeqName?: boolean;
  }

  export interface ParsedSequence {
    name: string;
    sequence: string;
    circular?: boolean;
    features?: Array<{
      name: string;
      start: number;
      end: number;
      type?: string;
      strand?: number;
      color?: string;
    }>;
    description?: string;
  }

  export function genbankToJson(text: string, options?: ParseOptions): Promise<ParsedSequence[]>;
  export function fastaToJson(text: string, options?: ParseOptions): Promise<ParsedSequence[]>;
  export function snapgeneToJson(text: string, options?: ParseOptions): Promise<ParsedSequence[]>;
  export function anyToJson(text: string, options?: ParseOptions): Promise<ParsedSequence[]>;
  export function jsonToGenbank(sequence: any, options?: ParseOptions): string;
  export function jsonToFasta(sequence: any, options?: ParseOptions): string;
}