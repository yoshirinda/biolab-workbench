import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
  Component,
  ErrorInfo,
} from 'react';
import { Sequence } from '../types/biolab';
import {
  Empty,
  Segmented,
  Space,
  Button,
  Tooltip,
  Tag,
  Alert,
  Switch,
  Input,
  InputNumber,
  Badge,
  Select,
} from 'antd';
import type { InputRef } from 'antd';
import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import { translateSequence } from '../utils/bioUtils';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ViewerErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('SequenceViewer Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Alert
            message="Visualization Error"
            description={this.state.error?.message || 'An unexpected error occurred while rendering the sequence.'}
            type="error"
            showIcon
            action={
              <Button size="small" type="primary" onClick={() => this.setState({ hasError: false, error: null })}>
                Retry
              </Button>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}

interface SequenceViewerProps {
  sequence: Sequence | null;
  onSelection?: (selection: { start: number; end: number; clockwise: boolean } | null) => void;
  simpleMode?: boolean;
}

type Density = 'compact' | 'comfortable';
type TranslationMode = 'off' | 'f1' | 'f3';

interface NormalizedFeature {
  id: string;
  key: string;
  name: string;
  type: string;
  color: string;
  start: number;
  end: number;
  strand: '+' | '-';
}

interface RowSlice {
  start: number;
  end: number;
  seq: string;
  complement: string;
}

interface FeatureSlice {
  id: string;
  key: string;
  name: string;
  type: string;
  color: string;
  strand: '+' | '-';
  start: number;
  end: number;
  left: number;
  width: number;
}

interface CodonCell {
  start: number;
  end: number;
  aa: string;
  frame: number;
  left: number;
  width: number;
}

const NUCLEOTIDE_COLORS: Record<string, { bg: string; text: string }> = {
  A: { bg: '#e3f7ea', text: '#0f6b3a' },
  T: { bg: '#ffe8df', text: '#8f3608' },
  G: { bg: '#dce8ff', text: '#13408c' },
  C: { bg: '#fff3d9', text: '#8a5a06' },
  N: { bg: '#eef2f7', text: '#4e6072' },
};

const AMINO_COLORS: Record<string, { bg: string; text: string; group: string }> = {
  D: { bg: '#ffe0e0', text: '#9a2020', group: 'Acidic' },
  E: { bg: '#ffe0e0', text: '#9a2020', group: 'Acidic' },
  K: { bg: '#e1edff', text: '#1c4f99', group: 'Basic' },
  R: { bg: '#e1edff', text: '#1c4f99', group: 'Basic' },
  H: { bg: '#e8ebff', text: '#464f95', group: 'Basic' },
  S: { bg: '#fff2de', text: '#9c5d13', group: 'Polar' },
  T: { bg: '#fff2de', text: '#9c5d13', group: 'Polar' },
  N: { bg: '#e2f8f8', text: '#1a6d6d', group: 'Polar' },
  Q: { bg: '#e2f8f8', text: '#1a6d6d', group: 'Polar' },
  A: { bg: '#eceff3', text: '#3d4a56', group: 'Hydrophobic' },
  V: { bg: '#dff4df', text: '#2f6b2f', group: 'Hydrophobic' },
  L: { bg: '#dff4df', text: '#2f6b2f', group: 'Hydrophobic' },
  I: { bg: '#dff4df', text: '#2f6b2f', group: 'Hydrophobic' },
  P: { bg: '#f7e2d9', text: '#8f4a2d', group: 'Hydrophobic' },
  F: { bg: '#e4e7ff', text: '#2f3f95', group: 'Hydrophobic' },
  M: { bg: '#fbf7d8', text: '#817214', group: 'Hydrophobic' },
  W: { bg: '#f1e5f8', text: '#6d3e87', group: 'Hydrophobic' },
  G: { bg: '#f4f7fb', text: '#4d5d6d', group: 'Hydrophobic' },
  Y: { bg: '#eceeff', text: '#3a4aa0', group: 'Hydrophobic' },
  C: { bg: '#fff7cc', text: '#7d6b00', group: 'Special' },
  '*': { bg: '#222', text: '#fff', group: 'Stop' },
  X: { bg: '#f0f0f0', text: '#555', group: 'Unknown' },
  '-': { bg: '#fff', text: '#888', group: 'Gap' },
};

const DNA_COMP: Record<string, string> = {
  A: 'T',
  T: 'A',
  G: 'C',
  C: 'G',
  N: 'N',
};

const IUPAC_MATCH: Record<string, string> = {
  A: 'A',
  C: 'C',
  G: 'G',
  T: 'T',
  U: 'T',
  R: 'AG',
  Y: 'CT',
  S: 'GC',
  W: 'AT',
  K: 'GT',
  M: 'AC',
  B: 'CGT',
  D: 'AGT',
  H: 'ACT',
  V: 'ACG',
  N: 'ACGTN',
};

const SequenceViewerCore: React.FC<SequenceViewerProps> = ({ sequence, onSelection, simpleMode = true }) => {
  const [zoom, setZoom] = useState(50);
  const [chunkSize, setChunkSize] = useState(120);
  const [autoFitChunk, setAutoFitChunk] = useState(true);
  const [density, setDensity] = useState<Density>('comfortable');
  const [showComplement, setShowComplement] = useState(true);
  const [showFeatures, setShowFeatures] = useState(true);
  const [translationMode, setTranslationMode] = useState<TranslationMode>('f1');
  const [showResidueTooltip, setShowResidueTooltip] = useState(!simpleMode);
  const [useIupacSearch, setUseIupacSearch] = useState(!simpleMode);

  const [selectionRange, setSelectionRange] = useState<{ start: number; end: number } | null>(null);
  const [selectionAnchor, setSelectionAnchor] = useState<number | null>(null);
  const [cursorIndex, setCursorIndex] = useState<number | null>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragHover, setDragHover] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [motif, setMotif] = useState('');
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const [gotoPosition, setGotoPosition] = useState<number | null>(null);

  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [featureJumpKey, setFeatureJumpKey] = useState<string | undefined>(undefined);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const motifInputRef = useRef<InputRef | null>(null);
  const scrollRafRef = useRef<number | null>(null);
  const pendingScrollTopRef = useRef(0);

  const seqString = (sequence?.sequence || sequence?.seq || '').trim();
  const isProtein = sequence?.meta?.type === 'protein' || sequence?.type === 'protein';
  const isHugeSequence = seqString.length > 50000;

  const cellWidth = density === 'compact' ? 11 : 15;
  const fontSize = density === 'compact' ? 11 : 13;
  const effectiveCellWidth = Math.max(9, Math.round(cellWidth * (0.6 + zoom / 200)));

  const normalizedSequence = useMemo(() => {
    if (!seqString) return '';
    const upper = seqString.toUpperCase();
    if (isProtein) {
      return upper.replace(/[^A-Z*\-]/g, 'X');
    }
    return upper.replace(/U/g, 'T').replace(/[^ATGCRYSWKMBDHVN]/g, 'N');
  }, [seqString, isProtein]);
  const enableResidueTooltips = !simpleMode && showResidueTooltip && !isHugeSequence && normalizedSequence.length <= 12000;

  const normalizedFeatures = useMemo<NormalizedFeature[]>(() => {
    const seqLen = normalizedSequence.length;
    if (!seqLen) return [];

    return (sequence?.features || [])
      .map((feature, idx) => {
        const rawStart = Math.max(0, Number(feature.start || 1) - 1);
        const rawEnd = Math.max(rawStart + 1, Number(feature.end || rawStart + 1));
        const start = Math.min(rawStart, seqLen - 1);
        const end = Math.min(rawEnd, seqLen);
        const name = feature.name || feature.label || feature.id || `feature_${idx + 1}`;
        const id = feature.id || `${name}_${idx + 1}`;
        return {
          id,
          key: `${id}:${start}:${end}:${idx}`,
          name,
          type: feature.type || 'misc',
          color: feature.color || '#3f72b5',
          start,
          end,
          strand: feature.direction === 1 || feature.strand === '+' || feature.strand === 1 ? '+' : '-',
        };
      })
      .filter((f) => f.end > f.start);
  }, [normalizedSequence.length, sequence?.features]);

  const autoChunkSize = useMemo(() => {
    if (!viewportWidth) return 120;
    const usableWidth = Math.max(300, viewportWidth - 160);
    const byWidth = Math.floor(usableWidth / Math.max(effectiveCellWidth, 9));
    const rounded = Math.max(30, Math.min(600, Math.floor(byWidth / 10) * 10));
    return rounded;
  }, [viewportWidth, effectiveCellWidth]);

  const renderChunkSize = autoFitChunk ? autoChunkSize : chunkSize;

  const translationTracks = translationMode === 'off' ? 0 : translationMode === 'f1' ? 1 : 3;
  const translationVisible = translationTracks > 0 && !isProtein && renderChunkSize <= 360;

  const rowHeight = useMemo(() => {
    const lineHeight = density === 'compact' ? 18 : 22;
    const featureHeight = showFeatures && !isProtein ? 20 : 0;
    const translationHeight = translationVisible ? translationTracks * 20 + 6 : 0;
    const complementHeight = showComplement && !isProtein ? lineHeight + 6 : 0;
    return featureHeight + translationHeight + lineHeight + complementHeight + 30;
  }, [density, showFeatures, isProtein, translationVisible, showComplement, translationTracks]);

  const rows = useMemo<RowSlice[]>(() => {
    const seqLen = normalizedSequence.length;
    const chunks: RowSlice[] = [];

    for (let start = 0; start < seqLen; start += renderChunkSize) {
      const end = Math.min(start + renderChunkSize, seqLen);
      const slice = normalizedSequence.slice(start, end);
      const complement = isProtein
        ? ''
        : slice
            .split('')
            .map((base) => DNA_COMP[base] || 'N')
            .join('');

      chunks.push({ start, end, seq: slice, complement });
    }

    return chunks;
  }, [normalizedSequence, renderChunkSize, isProtein]);

  const normalizedMotif = useMemo(() => {
    const raw = motif.trim().toUpperCase();
    if (!raw) return '';
    if (isProtein) return raw.replace(/[^A-Z*\-]/g, '');
    return raw.replace(/U/g, 'T').replace(/[^ATGCRYSWKMBDHVN]/g, '');
  }, [motif, isProtein]);

  const motifMatches = useMemo(() => {
    if (!normalizedMotif || normalizedMotif.length < 2 || !normalizedSequence) return [];

    if (isProtein || !useIupacSearch) {
      const hits: number[] = [];
      let idx = normalizedSequence.indexOf(normalizedMotif);
      while (idx !== -1) {
        hits.push(idx);
        idx = normalizedSequence.indexOf(normalizedMotif, idx + 1);
      }
      return hits;
    }

    const motifChars = normalizedMotif.split('');
    const hits: number[] = [];
    const maxStart = normalizedSequence.length - normalizedMotif.length;

    for (let i = 0; i <= maxStart; i += 1) {
      let ok = true;
      for (let j = 0; j < motifChars.length; j += 1) {
        const code = motifChars[j];
        const allowed = IUPAC_MATCH[code] || code;
        if (!allowed.includes(normalizedSequence[i + j])) {
          ok = false;
          break;
        }
      }
      if (ok) hits.push(i);
    }

    return hits;
  }, [normalizedSequence, normalizedMotif, isProtein, useIupacSearch]);

  useEffect(() => {
    setCurrentMatchIndex(0);
  }, [normalizedMotif, sequence?.id]);

  const currentMatch = useMemo(() => {
    if (!motifMatches.length || !normalizedMotif) return null;
    const safeIndex = Math.min(currentMatchIndex, motifMatches.length - 1);
    const start = motifMatches[safeIndex];
    return { start, end: start + normalizedMotif.length - 1 };
  }, [motifMatches, currentMatchIndex, normalizedMotif]);

  const setSelection = useCallback((start: number, end: number) => {
    if (!normalizedSequence.length) return;
    const safeStart = Math.max(0, Math.min(start, normalizedSequence.length - 1));
    const safeEnd = Math.max(0, Math.min(end, normalizedSequence.length - 1));
    const range = {
      start: Math.min(safeStart, safeEnd),
      end: Math.max(safeStart, safeEnd),
    };
    setSelectionRange(range);
    onSelection?.({ start: range.start, end: range.end, clockwise: false });
  }, [normalizedSequence.length, onSelection]);

  const resolveDragRange = useCallback(() => {
    if (dragStart === null || dragHover === null) return null;
    return {
      start: Math.min(dragStart, dragHover),
      end: Math.max(dragStart, dragHover),
    };
  }, [dragStart, dragHover]);

  const finishSelection = useCallback(() => {
    if (!isDragging) return;
    const range = resolveDragRange();
    if (range) {
      setSelection(range.start, range.end);
      setSelectionAnchor(range.start);
      setCursorIndex(range.end);
    }
    setIsDragging(false);
    setDragStart(null);
    setDragHover(null);
  }, [isDragging, resolveDragRange, setSelection]);

  const jumpToBase = useCallback((baseIndex: number) => {
    if (!scrollRef.current || normalizedSequence.length === 0) return;
    const safe = Math.max(0, Math.min(baseIndex, normalizedSequence.length - 1));
    const rowIndex = Math.floor(safe / renderChunkSize);
    const target = Math.max(0, rowIndex * rowHeight - rowHeight * 2);
    scrollRef.current.scrollTop = target;
    setScrollTop(target);
  }, [normalizedSequence.length, renderChunkSize, rowHeight]);

  const moveCursor = useCallback((nextIndex: number, extend: boolean) => {
    if (!normalizedSequence.length) return;
    const safe = Math.max(0, Math.min(nextIndex, normalizedSequence.length - 1));

    if (extend) {
      const anchor = selectionAnchor ?? cursorIndex ?? safe;
      setSelection(anchor, safe);
      setSelectionAnchor(anchor);
    } else {
      setSelection(safe, safe);
      setSelectionAnchor(safe);
    }

    setCursorIndex(safe);
    jumpToBase(safe);
  }, [normalizedSequence.length, selectionAnchor, cursorIndex, setSelection, jumpToBase]);

  const getRowFeatures = useCallback((rowStart: number, rowEnd: number): FeatureSlice[] => {
    const rowLen = Math.max(rowEnd - rowStart, 1);
    return normalizedFeatures
      .map((feature) => {
        const overlapStart = Math.max(rowStart, feature.start);
        const overlapEnd = Math.min(rowEnd, feature.end);
        if (overlapEnd <= overlapStart) return null;
        return {
          ...feature,
          left: ((overlapStart - rowStart) / rowLen) * 100,
          width: ((overlapEnd - overlapStart) / rowLen) * 100,
        };
      })
      .filter(Boolean) as FeatureSlice[];
  }, [normalizedFeatures]);

  const getRowCodons = useCallback((rowStart: number, rowEnd: number): CodonCell[] => {
    if (!translationVisible || rowEnd - rowStart < 3) return [];

    const frames = translationMode === 'f3' ? [0, 1, 2] : [0];
    const rowLen = Math.max(rowEnd - rowStart, 1);
    const cells: CodonCell[] = [];

    frames.forEach((frameOffset, frameIndex) => {
      const startOffset = (frameOffset - (rowStart % 3) + 3) % 3;
      const frameStart = rowStart + startOffset;

      for (let codonStart = frameStart; codonStart + 2 < rowEnd; codonStart += 3) {
        const codon = normalizedSequence.slice(codonStart, codonStart + 3);
        const aa = (translateSequence(codon)[0] || 'X').replace(/_/g, '*');
        cells.push({
          start: codonStart,
          end: codonStart + 3,
          aa,
          frame: frameIndex,
          left: ((codonStart - rowStart) / rowLen) * 100,
          width: (3 / rowLen) * 100,
        });
      }
    });

    return cells;
  }, [translationVisible, translationMode, normalizedSequence]);

  useEffect(() => {
    if (isProtein) {
      setShowComplement(false);
      setTranslationMode('off');
    }
  }, [isProtein]);

  useEffect(() => {
    if (normalizedSequence.length > 120000) {
      setDensity('compact');
      setAutoFitChunk(true);
      setTranslationMode('off');
      setShowResidueTooltip(false);
    }
  }, [normalizedSequence.length]);

  useEffect(() => {
    if (isHugeSequence) {
      setShowResidueTooltip(false);
    }
  }, [isHugeSequence]);

  useEffect(() => {
    if (simpleMode) {
      setShowResidueTooltip(false);
      setUseIupacSearch(false);
    }
  }, [simpleMode]);

  useEffect(() => {
    setSelectionRange(null);
    setSelectionAnchor(null);
    setCursorIndex(null);
    setDragStart(null);
    setDragHover(null);
    setIsDragging(false);
    setFeatureJumpKey(undefined);
    onSelection?.(null);
  }, [sequence?.id, onSelection]);

  useEffect(() => {
    window.addEventListener('mouseup', finishSelection);
    return () => window.removeEventListener('mouseup', finishSelection);
  }, [finishSelection]);

  useEffect(() => () => {
    if (scrollRafRef.current !== null) {
      window.cancelAnimationFrame(scrollRafRef.current);
      scrollRafRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!currentMatch) return;
    jumpToBase(currentMatch.start);
    setCursorIndex(currentMatch.start);
    setSelection(currentMatch.start, currentMatch.end);
  }, [currentMatch, jumpToBase, setSelection]);

  useEffect(() => {
    const updateViewport = () => {
      if (!scrollRef.current) return;
      setViewportHeight(scrollRef.current.clientHeight || 600);
      setViewportWidth(scrollRef.current.clientWidth || 0);
    };

    updateViewport();

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && scrollRef.current) {
      observer = new ResizeObserver(updateViewport);
      observer.observe(scrollRef.current);
    } else {
      window.addEventListener('resize', updateViewport);
    }

    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', updateViewport);
    };
  }, []);

  const totalRows = rows.length;
  const overscan = 4;
  const visibleStartRow = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleEndRow = Math.min(totalRows, Math.ceil((scrollTop + viewportHeight) / rowHeight) + overscan);
  const topSpacer = visibleStartRow * rowHeight;
  const bottomSpacer = Math.max(0, (totalRows - visibleEndRow) * rowHeight);
  const visibleRows = rows.slice(visibleStartRow, visibleEndRow);

  const viewportBaseStart = Math.max(1, visibleStartRow * renderChunkSize + 1);
  const viewportBaseEnd = Math.min(normalizedSequence.length, visibleEndRow * renderChunkSize);
  const viewportPctStart = normalizedSequence.length ? ((viewportBaseStart - 1) / normalizedSequence.length) * 100 : 0;
  const viewportPctWidth = normalizedSequence.length
    ? Math.max(1, ((viewportBaseEnd - viewportBaseStart + 1) / normalizedSequence.length) * 100)
    : 0;

  const activeDrag = isDragging ? resolveDragRange() : null;
  const activeSelection = activeDrag || selectionRange;
  const selectionLength = activeSelection ? activeSelection.end - activeSelection.start + 1 : 0;

  const isSelectedIndex = (index: number) => {
    if (!activeSelection) return false;
    return index >= activeSelection.start && index <= activeSelection.end;
  };

  const isMatchIndex = (index: number) => {
    if (!currentMatch) return false;
    return index >= currentMatch.start && index <= currentMatch.end;
  };

  const residueStyle = (residue: string, index: number): React.CSSProperties => {
    const selected = isSelectedIndex(index);
    const matchHit = isMatchIndex(index);
    const focused = cursorIndex === index;

    const baseStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: `${effectiveCellWidth}px`,
      height: density === 'compact' ? 18 : 22,
      borderRadius: 4,
      fontSize,
      fontWeight: 600,
      userSelect: 'none',
      cursor: 'crosshair',
      border: '1px solid transparent',
      transition: 'all 0.08s ease',
      boxSizing: 'border-box',
      boxShadow: focused ? '0 0 0 1px #005fcb inset' : undefined,
    };

    if (isProtein) {
      const colors = AMINO_COLORS[residue] || AMINO_COLORS.X;
      return {
        ...baseStyle,
        background: selected ? '#005fcb' : colors.bg,
        color: selected ? '#fff' : colors.text,
        borderColor: selected ? '#005fcb' : matchHit ? '#f59f00' : 'transparent',
      };
    }

    const colors = NUCLEOTIDE_COLORS[residue] || NUCLEOTIDE_COLORS.N;
    return {
      ...baseStyle,
      background: selected ? '#005fcb' : colors.bg,
      color: selected ? '#fff' : colors.text,
      borderColor: selected ? '#005fcb' : matchHit ? '#f59f00' : 'transparent',
    };
  };

  const handleFeatureJump = (value: string) => {
    setFeatureJumpKey(value);
    const feature = normalizedFeatures.find((f) => f.key === value);
    if (!feature) return;
    jumpToBase(feature.start);
    setSelection(feature.start, feature.end - 1);
    setSelectionAnchor(feature.start);
    setCursorIndex(feature.start);
  };

  const focusMotifSearch = useCallback(() => {
    motifInputRef.current?.focus();
    motifInputRef.current?.input?.select();
  }, []);

  const isTypingTarget = useCallback((target: EventTarget | null) => {
    const el = target as HTMLElement | null;
    if (!el) return false;
    return (
      el.tagName === 'INPUT' ||
      el.tagName === 'TEXTAREA' ||
      el.isContentEditable ||
      !!el.closest('.ant-input') ||
      !!el.closest('.ant-select') ||
      !!el.closest('.ant-picker')
    );
  }, []);

  useEffect(() => {
    const handleGlobalFind = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'f') return;
      if (isTypingTarget(event.target)) return;
      event.preventDefault();
      focusMotifSearch();
    };

    window.addEventListener('keydown', handleGlobalFind, true);
    return () => window.removeEventListener('keydown', handleGlobalFind, true);
  }, [focusMotifSearch, isTypingTarget]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLDivElement> = (event) => {
    if (!normalizedSequence.length) return;

    const isTypingContext = isTypingTarget(event.target);

    if (!isTypingContext && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
      event.preventDefault();
      focusMotifSearch();
      return;
    }

    if (isTypingContext) return;

    const current = cursorIndex ?? activeSelection?.end ?? 0;
    let nextIndex = current;
    let handled = true;

    if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'h') {
      nextIndex = current - 1;
    } else if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'l') {
      nextIndex = current + 1;
    } else if (event.key === 'ArrowUp' || event.key.toLowerCase() === 'k') {
      nextIndex = current - renderChunkSize;
    } else if (event.key === 'ArrowDown' || event.key.toLowerCase() === 'j') {
      nextIndex = current + renderChunkSize;
    } else if (event.key === 'PageUp') {
      nextIndex = current - renderChunkSize * 8;
    } else if (event.key === 'PageDown') {
      nextIndex = current + renderChunkSize * 8;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = normalizedSequence.length - 1;
    } else if (event.key.toLowerCase() === 'n' && motifMatches.length > 0) {
      setCurrentMatchIndex((idx) => (idx + 1) % motifMatches.length);
      return;
    } else if (event.key.toLowerCase() === 'p' && motifMatches.length > 0) {
      setCurrentMatchIndex((idx) => (idx - 1 + motifMatches.length) % motifMatches.length);
      return;
    } else if (event.key === 'Escape') {
      setSelectionRange(null);
      setSelectionAnchor(null);
      setCursorIndex(null);
      onSelection?.(null);
      return;
    } else {
      handled = false;
    }

    if (!handled) return;
    event.preventDefault();
    moveCursor(nextIndex, event.shiftKey);
  };

  if (!sequence) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="Select a sequence to view" />
      </div>
    );
  }

  if (!normalizedSequence) {
    return (
      <div style={{ padding: 20 }}>
        <Alert message="Invalid Data" description="The sequence data is empty." type="warning" showIcon />
      </div>
    );
  }

  const featureJumpOptions = normalizedFeatures.slice(0, 1000).map((feature) => ({
    value: feature.key,
    label: `${feature.name} [${feature.type}] ${feature.start + 1}-${feature.end}`,
  }));

  return (
    <div
      ref={rootRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#ffffff', outline: 'none' }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #d6e4f2', background: '#f7fbff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <Space wrap>
            <Tag color="blue">Linear Sequence View</Tag>
            {!simpleMode && (
              <>
                <Switch size="small" checked={autoFitChunk} onChange={setAutoFitChunk} />
                <span className="wb-muted" style={{ fontSize: 12 }}>Auto-fit line</span>
                <Segmented
                  options={[
                    { label: '60', value: 60 },
                    { label: '120', value: 120 },
                    { label: '240', value: 240 },
                  ]}
                  value={chunkSize}
                  onChange={(val) => setChunkSize(Number(val))}
                  disabled={autoFitChunk}
                />
                <Segmented
                  options={[
                    { label: 'Compact', value: 'compact' },
                    { label: 'Readable', value: 'comfortable' },
                  ]}
                  value={density}
                  onChange={(val) => setDensity(val as Density)}
                />
              </>
            )}
          </Space>

          <Space wrap>
            {!simpleMode && !isProtein && (
              <>
                <span className="wb-muted" style={{ fontSize: 12 }}>Features</span>
                <Switch size="small" checked={showFeatures} onChange={setShowFeatures} />
                <span className="wb-muted" style={{ fontSize: 12 }}>Complement</span>
                <Switch size="small" checked={showComplement} onChange={setShowComplement} />
                <span className="wb-muted" style={{ fontSize: 12 }}>Translation</span>
                <Segmented
                  options={[
                    { label: 'Off', value: 'off' },
                    { label: '+1', value: 'f1' },
                    { label: '+1/+2/+3', value: 'f3' },
                  ]}
                  value={translationMode}
                  onChange={(val) => setTranslationMode(val as TranslationMode)}
                  size="small"
                />
              </>
            )}
            {!simpleMode && (
              <>
                <span className="wb-muted" style={{ fontSize: 12 }}>Tooltips</span>
                <Switch size="small" checked={showResidueTooltip} onChange={setShowResidueTooltip} disabled={isHugeSequence} />
              </>
            )}
            <Tooltip title="Zoom Out">
              <Button icon={<ZoomOutOutlined />} onClick={() => setZoom((z) => Math.max(0, z - 10))} size="small" />
            </Tooltip>
            <Tooltip title="Zoom In">
              <Button icon={<ZoomInOutlined />} onClick={() => setZoom((z) => Math.min(100, z + 10))} size="small" />
            </Tooltip>
            <Tooltip title="Reset Zoom">
              <Button icon={<ReloadOutlined />} onClick={() => setZoom(50)} size="small" />
            </Tooltip>
            <Button
              size="small"
              onClick={() => {
                setSelectionRange(null);
                setSelectionAnchor(null);
                setCursorIndex(null);
                onSelection?.(null);
              }}
              disabled={!selectionRange}
            >
              Clear Selection
            </Button>
          </Space>
        </div>

        <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Space wrap>
            <Input
              ref={motifInputRef}
              size="small"
              placeholder={
                isProtein
                  ? 'Find motif (AA)...'
                  : (useIupacSearch ? 'Find motif (DNA/IUPAC)...' : 'Find motif (DNA exact)...')
              }
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              style={{ width: 220 }}
              allowClear
              data-motif-search="1"
            />
            {!simpleMode && !isProtein && (
              <>
                <span className="wb-muted" style={{ fontSize: 12 }}>IUPAC</span>
                <Switch size="small" checked={useIupacSearch} onChange={setUseIupacSearch} />
              </>
            )}
            <Button
              size="small"
              disabled={motifMatches.length === 0}
              onClick={() => setCurrentMatchIndex((idx) => (idx - 1 + motifMatches.length) % motifMatches.length)}
            >
              Prev
            </Button>
            <Button
              size="small"
              disabled={motifMatches.length === 0}
              onClick={() => setCurrentMatchIndex((idx) => (idx + 1) % motifMatches.length)}
            >
              Next
            </Button>
            <Badge color={motifMatches.length ? '#0969da' : '#9aa9b8'} text={`${motifMatches.length} matches`} />
          </Space>

          {!simpleMode && (
            <Space wrap>
              {!isProtein && normalizedFeatures.length > 0 && (
                <Select
                  size="small"
                  showSearch
                  value={featureJumpKey}
                  placeholder="Jump to feature"
                  style={{ width: 320 }}
                  options={featureJumpOptions}
                  onChange={handleFeatureJump}
                  optionFilterProp="label"
                />
              )}
              <span className="wb-muted" style={{ fontSize: 12 }}>Go to</span>
              <InputNumber
                size="small"
                min={1}
                max={normalizedSequence.length}
                value={gotoPosition}
                onChange={(val) => setGotoPosition(typeof val === 'number' ? val : null)}
                style={{ width: 100 }}
              />
              <Button
                size="small"
                onClick={() => {
                  if (!gotoPosition) return;
                  const idx = gotoPosition - 1;
                  jumpToBase(idx);
                  moveCursor(idx, false);
                }}
              >
                Jump
              </Button>
            </Space>
          )}
        </div>
      </div>

      <div style={{ padding: '8px 12px', borderBottom: '1px solid #e2ecf7', background: '#ffffff' }}>
        <div
          style={{
            position: 'relative',
            height: 20,
            borderRadius: 10,
            background: 'linear-gradient(90deg, #e5effa 0%, #f0f5fb 100%)',
            border: '1px solid #d7e5f4',
            cursor: 'pointer',
            overflow: 'hidden',
          }}
          onClick={(e) => {
            const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            jumpToBase(Math.floor(pct * normalizedSequence.length));
          }}
        >
          {showFeatures && !isProtein && normalizedFeatures.map((feature) => (
            <div
              key={`overview-${feature.key}`}
              style={{
                position: 'absolute',
                left: `${(feature.start / normalizedSequence.length) * 100}%`,
                width: `${Math.max(0.2, ((feature.end - feature.start) / normalizedSequence.length) * 100)}%`,
                top: 4,
                height: 10,
                borderRadius: 5,
                background: feature.color,
                opacity: 0.65,
              }}
            />
          ))}
          <div
            style={{
              position: 'absolute',
              left: `${viewportPctStart}%`,
              width: `${viewportPctWidth}%`,
              minWidth: 2,
              top: 1,
              height: 16,
              borderRadius: 8,
              border: '1px solid #0969da',
              background: 'rgba(9, 105, 218, 0.18)',
            }}
          />
        </div>
        <div style={{ marginTop: 4, display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#5d7287' }}>
          <span className="mono">{normalizedSequence.length.toLocaleString()} residues</span>
          <span className="mono">
            View {viewportBaseStart.toLocaleString()} - {viewportBaseEnd.toLocaleString()} | line {renderChunkSize} {autoFitChunk ? '(auto)' : ''}
          </span>
        </div>
        {activeSelection && (
          <div style={{ marginTop: 4, fontSize: 12, color: '#35506b' }} className="mono">
            Selection: {activeSelection.start + 1} - {activeSelection.end + 1} ({selectionLength} bp/aa)
          </div>
        )}
      </div>

      <div
        ref={scrollRef}
        onScroll={(e) => {
          pendingScrollTopRef.current = (e.currentTarget as HTMLDivElement).scrollTop;
          if (scrollRafRef.current !== null) return;
          scrollRafRef.current = window.requestAnimationFrame(() => {
            scrollRafRef.current = null;
            setScrollTop(pendingScrollTopRef.current);
          });
        }}
        style={{ flex: 1, overflow: 'auto', padding: 12 }}
      >
        <div style={{ minWidth: 'fit-content' }}>
          {topSpacer > 0 && <div style={{ height: topSpacer }} />}

          {visibleRows.map((row, idx) => {
            const rowIndex = visibleStartRow + idx;
            const rowPixelWidth = row.seq.length * effectiveCellWidth;
            const rowFeatures = getRowFeatures(row.start, row.end);
            const rowCodons = getRowCodons(row.start, row.end);

            return (
              <div
                key={`${row.start}-${row.end}`}
                style={{
                  height: rowHeight,
                  borderBottom: rowIndex < totalRows - 1 ? '1px dashed #e6eef7' : 'none',
                  paddingBottom: 10,
                  marginBottom: 8,
                  boxSizing: 'border-box',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div className="mono" style={{ width: 100, color: '#4d6378', fontSize: 12, paddingTop: 4 }}>
                    {row.start + 1}-{row.end}
                  </div>

                  <div style={{ width: rowPixelWidth }}>
                    {showFeatures && !isProtein && (
                      <div style={{ position: 'relative', height: 16, marginBottom: 6, borderRadius: 8, background: '#f2f7fd', border: '1px solid #e1ebf6' }}>
                        {rowFeatures.map((feature) => (
                          <Tooltip key={`${feature.key}-${row.start}`} title={`${feature.name} [${feature.type}] (${feature.strand})`} mouseEnterDelay={0.2}>
                            <div
                              role="button"
                              tabIndex={-1}
                              onClick={() => {
                                jumpToBase(feature.start);
                                setSelection(feature.start, feature.end - 1);
                                setSelectionAnchor(feature.start);
                                setCursorIndex(feature.start);
                              }}
                              style={{
                                position: 'absolute',
                                left: `${feature.left}%`,
                                width: `${feature.width}%`,
                                top: 2,
                                height: 10,
                                borderRadius: 5,
                                background: feature.color,
                                opacity: 0.9,
                                cursor: 'pointer',
                              }}
                            />
                          </Tooltip>
                        ))}
                      </div>
                    )}

                    {translationVisible && (
                      <div
                        style={{
                          position: 'relative',
                          height: translationTracks * 20,
                          marginBottom: 4,
                          borderRadius: 6,
                          background: '#f7f9fc',
                          border: '1px solid #e7eef6',
                        }}
                      >
                        {rowCodons.map((cell) => {
                          const codonNode = (
                            <div
                              className="mono"
                              style={{
                                position: 'absolute',
                                left: `${cell.left}%`,
                                width: `${cell.width}%`,
                                height: 18,
                                top: cell.frame * 20 + 1,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: 11,
                                fontWeight: 600,
                                color: '#35506b',
                              }}
                            >
                              {cell.aa}
                            </div>
                          );

                          if (!enableResidueTooltips) {
                            return <React.Fragment key={`${cell.frame}-${cell.start}-${row.start}`}>{codonNode}</React.Fragment>;
                          }

                          return (
                            <Tooltip
                              key={`${cell.frame}-${cell.start}-${row.start}`}
                              title={`Frame +${cell.frame + 1}: ${normalizedSequence.slice(cell.start, cell.end)} (${cell.start + 1}-${cell.end})`}
                            >
                              {codonNode}
                            </Tooltip>
                          );
                        })}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 0 }}>
                      {row.seq.split('').map((residue, localIndex) => {
                        const absoluteIndex = row.start + localIndex;
                        const aaInfo = AMINO_COLORS[residue] || AMINO_COLORS.X;

                        const residueNode = (
                          <span
                            className="mono"
                            style={residueStyle(residue, absoluteIndex)}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              setIsDragging(true);
                              setDragStart(absoluteIndex);
                              setDragHover(absoluteIndex);
                              setCursorIndex(absoluteIndex);
                              setSelectionAnchor(absoluteIndex);
                            }}
                            onMouseEnter={() => {
                              if (isDragging) setDragHover(absoluteIndex);
                            }}
                          >
                            {residue}
                          </span>
                        );

                        if (!enableResidueTooltips) {
                          return <React.Fragment key={`${row.start}-${localIndex}`}>{residueNode}</React.Fragment>;
                        }

                        return (
                          <Tooltip
                            key={`${row.start}-${localIndex}`}
                            title={isProtein ? `${residue} (${aaInfo.group || 'Unknown'}) @ ${absoluteIndex + 1}` : `${residue} @ ${absoluteIndex + 1}`}
                            mouseEnterDelay={0.1}
                          >
                            {residueNode}
                          </Tooltip>
                        );
                      })}
                    </div>

                    {showComplement && !isProtein && (
                      <div style={{ display: 'flex', gap: 0, marginTop: 4 }}>
                        {row.complement.split('').map((residue, localIndex) => (
                          <span
                            key={`comp-${row.start}-${localIndex}`}
                            className="mono"
                            style={{
                              ...residueStyle(residue, -1),
                              cursor: 'default',
                              opacity: 0.8,
                              borderColor: 'transparent',
                            }}
                          >
                            {residue}
                          </span>
                        ))}
                      </div>
                    )}

                    <div style={{ position: 'relative', height: 16, marginTop: 6 }}>
                      {Array.from({ length: Math.floor((row.end - row.start - 1) / 10) + 1 }).map((_, tick) => {
                        const position = row.start + tick * 10;
                        if (position >= row.end) return null;
                        const left = ((position - row.start) / Math.max(row.end - row.start, 1)) * 100;
                        return (
                          <span
                            key={`${row.start}-tick-${position}`}
                            className="mono"
                            style={{
                              position: 'absolute',
                              left: `${left}%`,
                              transform: 'translateX(-50%)',
                              fontSize: 10,
                              color: '#6d8195',
                            }}
                          >
                            {position + 1}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {bottomSpacer > 0 && <div style={{ height: bottomSpacer }} />}
        </div>

        <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          {isProtein ? (
            <Space wrap size={[8, 8]}>
              <Tag color="red">Acidic</Tag>
              <Tag color="blue">Basic</Tag>
              <Tag color="orange">Polar</Tag>
              <Tag color="green">Hydrophobic</Tag>
              <Tag color="gold">Special</Tag>
            </Space>
          ) : (
            <Space wrap size={[8, 8]}>
              <Tag color="green">A</Tag>
              <Tag color="volcano">T</Tag>
              <Tag color="blue">G</Tag>
              <Tag color="gold">C</Tag>
              <Tag>N</Tag>
            </Space>
          )}
          {!simpleMode && (
            <Tag>
              Keys: Ctrl/Cmd+F find, Arrow/HJKL move, Shift+move extend, N/P next/prev match, Esc clear
            </Tag>
          )}
        </div>
      </div>
    </div>
  );
};

const SequenceViewer = React.memo(
  ({ sequence, onSelection, simpleMode = true }: SequenceViewerProps) => {
    return (
      <ViewerErrorBoundary>
        <SequenceViewerCore sequence={sequence} onSelection={onSelection} simpleMode={simpleMode} />
      </ViewerErrorBoundary>
    );
  },
  (prev, next) =>
    prev.sequence === next.sequence &&
    prev.onSelection === next.onSelection &&
    prev.simpleMode === next.simpleMode
);

export default SequenceViewer;
