"""
Version Parser for V2X Device Versions

Utility to parse device versions and extract metadata like date, variant, and build info.
Expected format: v040.040.065.iconsf25.oem_260525

Example:
    v = VersionParser("v040.040.065.iconsf25.oem_260525")
    print(v.date)           # "260525"
    print(v.device_variant) # "iconsf25"
    print(v.full_version)   # "v040.040.065.iconsf25.oem_260525"
"""

import re
from pathlib import Path


class VersionParser:
    """Parse and extract metadata from device version strings."""
    
    def __init__(self, version: str):
        """
        Initialize version parser.
        
        Args:
            version: Version string (e.g., "v040.040.065.iconsf25.oem_260525")
                    or "ICON_NAD.v040.040.065.iconsf25.oem_260525"
        """
        self.full_version = version.strip()
        self.clean_version = self._extract_clean_version()
        self._parse_version()
    
    def _extract_clean_version(self) -> str:
        """
        Extract clean version string without device prefix.
        
        Examples:
            "ICON_NAD.v040.040.065.iconsf25.oem_260525" -> "v040.040.065.iconsf25.oem_260525"
            "v040.040.065.iconsf25.oem_260525" -> "v040.040.065.iconsf25.oem_260525"
        """
        version = self.full_version
        # Remove common prefixes like "ICON_NAD.", "ICON25SF.", etc.
        if '.' in version and not version.startswith('v'):
            # Split on first dot and take the part that starts with 'v'
            parts = version.split('.')
            for i, part in enumerate(parts):
                if part.lower().startswith('v'):
                    return '.'.join(parts[i:])
        return version
    
    def _parse_version(self):
        """Parse version string and extract components."""
        # Example: v040.040.065.iconsf25.oem_260525
        # Pattern: v{x}.{x}.{x}.{device_variant}.oem_{date}
        
        pattern = r'v[\d.]+\.([a-z0-9]+)\.(?:oem|sop|mtk)_(\d{6})'
        match = re.search(pattern, self.clean_version, re.IGNORECASE)
        
        if match:
            self.device_variant = match.group(1)  # e.g., "iconsf25"
            self.date = match.group(2)              # e.g., "260525"
        else:
            # Fallback extraction
            self.device_variant = "unknown"
            self.date = "unknown"
    
    def get_directory_path(self, base_path: str = None) -> Path:
        """
        Generate directory path based on version metadata.
        
        Expected structure:
            base_path/{date}/{device_variant}/
        
        Example:
            base_path = "D:\\SANITY"
            Result: D:\\SANITY\\260525\\iconsf25\\
        
        Args:
            base_path: Base directory (default: current workspace "logs/sanity")
        
        Returns:
            Path object for the version-specific directory
        """
        if base_path is None:
            base_path = "logs/sanity"
        
        base = Path(base_path)
        version_dir = base / self.date / self.device_variant
        
        return version_dir
    
    def create_directory(self, base_path: str = None) -> Path:
        """
        Create version-specific directory if it doesn't exist.
        
        Args:
            base_path: Base directory for sanity logs
        
        Returns:
            Path object for created directory
        """
        version_dir = self.get_directory_path(base_path)
        version_dir.mkdir(parents=True, exist_ok=True)
        return version_dir
    
    def get_expected_dlt_filename(self) -> str:
        """
        Get the expected DLT filename for this version.
        
        Expected format: basic_sanity_{clean_version}.dlt
        
        Args:
            None
        
        Returns:
            Expected filename (e.g., "basic_sanity_v040.040.065.iconsf25.oem_260525.dlt")
        """
        return f"basic_sanity_{self.clean_version}.dlt"
    
    def find_dlt_file(self, base_path: str = None) -> Path:
        """
        Find DLT file in version-specific directory.
        
        Args:
            base_path: Base directory for sanity logs
        
        Returns:
            Path to DLT file if found, None otherwise
        """
        version_dir = self.get_directory_path(base_path)
        
        if not version_dir.exists():
            return None
        
        # First, try exact filename match
        expected_file = version_dir / self.get_expected_dlt_filename()
        if expected_file.exists():
            return expected_file
        
        # Fallback: find any .dlt file with basic_sanity prefix
        dlt_files = list(version_dir.glob("basic_sanity_*.dlt"))
        if dlt_files:
            return dlt_files[0]
        
        return None
    
    def get_csv_path(self, base_path: str = None, auto_create: bool = True) -> Path:
        """
        Get the path for CSV export of DLT file.
        
        CSV should be in the same directory as DLT.
        Expected format: basic_sanity_{full_version}.csv
        
        Args:
            base_path: Base directory for sanity logs
            auto_create: If True, return path assuming directory will be created
        
        Returns:
            Path object for CSV file
        """
        version_dir = self.get_directory_path(base_path)
        csv_name = f"basic_sanity_{self.full_version}.csv"
        return version_dir / csv_name
    
    def __str__(self) -> str:
        """String representation of parsed version."""
        return f"Version(full={self.full_version}, date={self.date}, variant={self.device_variant})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return self.__str__()


if __name__ == "__main__":
    # Test examples
    test_versions = [
        "v040.040.065.iconsf25.oem_260525",
        "v1.2.3.icon25.oem_250101",
        "v0.0.1.test_device.oem_310301",
    ]
    
    for ver_str in test_versions:
        v = VersionParser(ver_str)
        print(f"\n{v}")
        print(f"  Directory: {v.get_directory_path('D:\\SANITY')}")
        print(f"  DLT Filename: {v.get_expected_dlt_filename()}")
        print(f"  CSV Path: {v.get_csv_path('D:\\SANITY')}")
