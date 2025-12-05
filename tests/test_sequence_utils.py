import pytest
from app.core.sequence_utils import layout_features

def test_layout_features_empty():
    """Test layout with no features."""
    assert layout_features([]) == []

def test_layout_features_no_overlap():
    """Test features that do not overlap."""
    features = [
        {'id': 'f1', 'start': 10, 'end': 20},
        {'id': 'f2', 'start': 30, 'end': 40},
    ]
    # Expect one lane
    result = layout_features(features)
    assert len(result) == 1
    assert len(result[0]) == 2
    assert result[0][0]['id'] == 'f1'
    assert result[0][1]['id'] == 'f2'

def test_layout_features_simple_overlap():
    """Test two features that overlap."""
    features = [
        {'id': 'f1', 'start': 10, 'end': 30},
        {'id': 'f2', 'start': 20, 'end': 40},
    ]
    # Expect two lanes
    result = layout_features(features)
    assert len(result) == 2
    assert len(result[0]) == 1
    assert len(result[1]) == 1
    assert result[0][0]['id'] == 'f1'
    assert result[1][0]['id'] == 'f2'

def test_layout_features_multiple_lanes():
    """Test a more complex scenario requiring multiple lanes."""
    features = [
        {'id': 'f1', 'start': 10, 'end': 50},
        {'id': 'f2', 'start': 20, 'end': 40}, # Overlaps f1
        {'id': 'f3', 'start': 60, 'end': 70}, # No overlap, should be in lane 1
        {'id': 'f4', 'start': 30, 'end': 45}, # Overlaps f1 and f2
        {'id': 'f5', 'start': 65, 'end': 75}, # Overlaps f3
    ]
    result = layout_features(features)
    
    # Expect three lanes
    assert len(result) == 3

    # Lane 1 should have f1 and f3
    assert len(result[0]) == 2
    assert result[0][0]['id'] == 'f1'
    assert result[0][1]['id'] == 'f3'

    # Lane 2 should have f2 and f5
    assert len(result[1]) == 2
    assert result[1][0]['id'] == 'f2'
    assert result[1][1]['id'] == 'f5'
    
    # Lane 3 should have f4
    assert len(result[2]) == 1
    assert result[2][0]['id'] == 'f4'

def test_layout_features_touching_endpoints():
    """Test features that touch at endpoints (e.g., end of one is start of next)."""
    features = [
        {'id': 'f1', 'start': 10, 'end': 20},
        {'id': 'f2', 'start': 20, 'end': 30},
    ]
    # Should not overlap, so one lane
    result = layout_features(features)
    assert len(result) == 1
    assert len(result[0]) == 2
    assert result[0][0]['id'] == 'f1'
    assert result[0][1]['id'] == 'f2'

def test_layout_features_contained_feature():
    """Test a feature that is completely contained within another."""
    features = [
        {'id': 'f1', 'start': 10, 'end': 50},
        {'id': 'f2', 'start': 20, 'end': 40},
    ]
    # Expect two lanes
    result = layout_features(features)
    assert len(result) == 2
    assert result[0][0]['id'] == 'f1'
    assert result[1][0]['id'] == 'f2'

def test_layout_features_unsorted_input():
    """Test that the function works correctly even if input is not sorted by start time."""
    features = [
        {'id': 'f1', 'start': 60, 'end': 70},
        {'id': 'f2', 'start': 10, 'end': 50},
        {'id': 'f3', 'start': 20, 'end': 40},
    ]
    # Expect two lanes
    result = layout_features(features)
    assert len(result) == 2
    
    # Check that f2 is in lane 0 and f3 is in lane 1
    lane0_ids = [f['id'] for f in result[0]]
    lane1_ids = [f['id'] for f in result[1]]

    assert 'f2' in lane0_ids
    assert 'f1' in lane0_ids
    assert 'f3' in lane1_ids
