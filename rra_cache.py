"""
RRA Comparison Cache Manager

Manages caching of RRA-to-briefing comparisons to avoid expensive regeneration.
Cache is tied to briefing and RRA metadata to detect staleness.
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any


class RRAComparisonCache:
    """Handles caching of RRA comparison results."""
    
    def __init__(self, cache_dir: str = None, country: str = None):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache storage. Defaults to intermediary_outputs/rra_comparisons/
            country: Country name (optional, for debugging)
        """
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, 'intermediary_outputs', 'rra_comparisons')
        
        self.cache_dir = cache_dir
        self.country = country
        self.metadata_suffix = '.metadata.json'
        self.result_suffix = '.result.html'
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text for comparison."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def _get_file_mtime(self, path: str) -> float:
        """Get file modification time, or 0 if file doesn't exist."""
        try:
            return os.path.getmtime(path)
        except (OSError, FileNotFoundError):
            return 0.0
    
    def _build_cache_key(self, country: str, briefing_content: str) -> str:
        """
        Build a cache key from country name and briefing content hash.
        
        Format: {country_normalized}_{briefing_hash}
        
        Args:
            country: Country name
            briefing_content: Briefing text content
            
        Returns:
            Cache key string
        """
        country_normalized = country.lower().replace(' ', '_').replace(',', '')
        briefing_hash = self._compute_hash(briefing_content)
        return f"{country_normalized}_{briefing_hash}"
    
    def get_cache_path(self, cache_key: str) -> Dict[str, str]:
        """
        Get full paths for cache files given a cache key.
        
        Returns dict with 'metadata' and 'result' keys.
        """
        return {
            'metadata': os.path.join(self.cache_dir, f"{cache_key}{self.metadata_suffix}"),
            'result': os.path.join(self.cache_dir, f"{cache_key}{self.result_suffix}")
        }
    
    def is_cache_valid(
        self,
        country: str,
        briefing_content: str,
        rra_path: str,
    ) -> bool:
        """
        Check if a valid cache entry exists for this briefing and RRA.
        
        A cache is considered valid if:
        1. Both metadata and result files exist
        2. Metadata hash matches current briefing
        3. RRA file has not been modified since cache creation
        
        Args:
            country: Country name
            briefing_content: Current briefing content
            rra_path: Path to RRA file
            
        Returns:
            True if cache is valid and should be used
        """
        cache_key = self._build_cache_key(country, briefing_content)
        paths = self.get_cache_path(cache_key)
        
        # Check if both files exist
        if not (os.path.exists(paths['metadata']) and os.path.exists(paths['result'])):
            return False
        
        # Load metadata
        try:
            with open(paths['metadata'], 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except (IOError, json.JSONDecodeError):
            return False
        
        # Verify briefing hash matches
        if metadata.get('briefing_hash') != self._compute_hash(briefing_content):
            return False
        
        # Check if RRA file is newer than cache
        rra_mtime = self._get_file_mtime(rra_path)
        cache_mtime = metadata.get('created_timestamp', 0)
        if rra_mtime > cache_mtime:
            return False
        
        return True
    
    def get_cached_comparison(self, country: str, briefing_content: str) -> Optional[str]:
        """
        Retrieve a cached comparison result if it exists and is valid.
        
        Args:
            country: Country name
            briefing_content: Briefing content
            
        Returns:
            Cached HTML comparison string, or None if cache miss
        """
        cache_key = self._build_cache_key(country, briefing_content)
        paths = self.get_cache_path(cache_key)
        
        if not os.path.exists(paths['result']):
            return None
        
        try:
            with open(paths['result'], 'r', encoding='utf-8') as f:
                return f.read()
        except IOError:
            return None
    
    def save_comparison(
        self,
        country: str,
        briefing_content: str,
        rra_path: str,
        comparison_result: str
    ) -> bool:
        """
        Save a comparison result to cache.
        
        Args:
            country: Country name
            briefing_content: Full briefing content
            rra_path: Path to RRA file used
            comparison_result: HTML comparison result from LLM
            
        Returns:
            True if save was successful
        """
        cache_key = self._build_cache_key(country, briefing_content)
        paths = self.get_cache_path(cache_key)
        
        # Prepare metadata
        metadata = {
            'country': country,
            'briefing_hash': self._compute_hash(briefing_content),
            'briefing_length': len(briefing_content),
            'rra_path': rra_path,
            'rra_mtime': self._get_file_mtime(rra_path),
            'created_timestamp': time.time(),
            'cache_key': cache_key
        }
        
        try:
            # Save metadata
            with open(paths['metadata'], 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Save result
            with open(paths['result'], 'w', encoding='utf-8') as f:
                f.write(comparison_result)
            
            return True
        except IOError as e:
            print(f"Error saving RRA comparison cache: {e}")
            return False
    
    def clear_country_cache(self, country: str) -> int:
        """
        Clear all cache entries for a specific country.
        
        Args:
            country: Country name
            
        Returns:
            Number of cache entries cleared
        """
        country_prefix = country.lower().replace(' ', '_').replace(',', '')
        cleared = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith(country_prefix):
                    filepath = os.path.join(self.cache_dir, filename)
                    os.remove(filepath)
                    cleared += 1
        except OSError as e:
            print(f"Error clearing cache for {country}: {e}")
        
        return cleared
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache statistics including entry count, total size, etc.
        """
        stats = {
            'total_entries': 0,
            'total_size_bytes': 0,
            'by_country': {}
        }
        
        try:
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith(self.metadata_suffix):
                    continue
                
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    country = metadata.get('country', 'unknown')
                    if country not in stats['by_country']:
                        stats['by_country'][country] = {'entries': 0, 'size_bytes': 0}
                    
                    # Add metadata file size
                    size = os.path.getsize(filepath)
                    stats['by_country'][country]['size_bytes'] += size
                    stats['total_size_bytes'] += size
                    
                    # Add result file size if it exists
                    result_filename = filename.replace(self.metadata_suffix, self.result_suffix)
                    result_filepath = os.path.join(self.cache_dir, result_filename)
                    if os.path.exists(result_filepath):
                        result_size = os.path.getsize(result_filepath)
                        stats['by_country'][country]['size_bytes'] += result_size
                        stats['total_size_bytes'] += result_size
                    
                    stats['by_country'][country]['entries'] += 1
                    stats['total_entries'] += 1
                
                except (IOError, json.JSONDecodeError):
                    continue
        
        except OSError:
            pass
        
        return stats


def get_rra_cache(country: str = None) -> RRAComparisonCache:
    """
    Convenience function to get an initialized cache manager.
    
    Args:
        country: Optional country name (for debugging)
        
    Returns:
        RRAComparisonCache instance
    """
    return RRAComparisonCache(country=country)
