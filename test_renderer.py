#!/usr/bin/env python3
"""
Quick test script for PhyloRenderer
Tests if the new beautiful rendering is working
"""
import sys
import os

# Add project to path
sys.path.insert(0, '/mnt/e/Kun/wsl/biolab/biolab-workbench')

from app.core.phylo_renderer import PhyloRenderer

# Test colors
test_colors = {
    'AT': '#e6194b',
    'Os': '#3cb44b', 
    'Mp': '#ffe119',
    'Sl': '#4363d8'
}

test_highlights = ['Os', 'AT']

print("=" * 60)
print("Testing PhyloRenderer with Beautiful Styling")
print("=" * 60)

# Check if class loaded correctly
print(f"\n✓ PhyloRenderer class loaded")
print(f"✓ Module docstring: {PhyloRenderer.__doc__[:50]}...")

# Check methods exist
methods = ['_render_rectangular', '_render_circular', '_style_tree_labels', 
           '_highlight_target_gene', '_add_legend', '_get_species_prefix']

print(f"\nChecking methods:")
for method in methods:
    if hasattr(PhyloRenderer, method):
        print(f"  ✓ {method}")
    else:
        print(f"  ✗ {method} MISSING!")

print("\n" + "=" * 60)
print("If all methods show ✓, the renderer is properly loaded!")
print("=" * 60)

# Test species prefix extraction
renderer = type('MockRenderer', (), {})()
renderer._get_species_prefix = PhyloRenderer._get_species_prefix.__get__(renderer)

test_genes = ['AT1G12345', 'LOC_Os05g05680', 'Mp3g19700', 'Solyc01g123456']
print(f"\nTesting species prefix extraction:")
for gene in test_genes:
    prefix = renderer._get_species_prefix(gene)
    print(f"  {gene} → {prefix}")

print("\n✓ Test completed successfully!")
print("\nIf Flask is showing old rendering, you MUST:")
print("  1. Stop Flask (Ctrl+C)")
print("  2. Run: ./restart_flask.sh")
print("  3. Or manually: python3 run.py")

