"""
SMM Text Parser

Parses the SMM (Sotilgan Mahsulot Miqdori) field from Savdo model.
Format: "Un 1 14500.0,Non 2 5000,Shakar 1 8000,"
"""

from typing import List, Dict, Optional
import re


def parse_smm(smm_text: Optional[str]) -> List[Dict[str, float]]:
    """
    Parse SMM text field into structured product data.
    
    Args:
        smm_text: String in format "ProductName qty price,ProductName qty price,"
        
    Returns:
        List of dicts with keys: 'name', 'qty', 'price'
        
    Examples:
        >>> parse_smm("Un 1 14500.0,Non 2 5000,")
        [
            {'name': 'Un', 'qty': 1.0, 'price': 14500.0},
            {'name': 'Non', 'qty': 2.0, 'price': 5000.0}
        ]
        
        >>> parse_smm(None)
        []
        
        >>> parse_smm("")
        []
    """
    if not smm_text or not smm_text.strip():
        return []
    
    products = []
    
    # Split by comma and process each entry
    entries = smm_text.split(',')
    
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        
        try:
            # Split by spaces and extract components
            parts = entry.split()
            
            if len(parts) < 3:
                # Malformed entry, skip
                continue
            
            # Product name can have multiple words
            # Last two parts are qty and price
            price = float(parts[-1])
            qty = float(parts[-2])
            name = ' '.join(parts[:-2])
            
            products.append({
                'name': name,
                'qty': qty,
                'price': price
            })
            
        except (ValueError, IndexError) as e:
            # Skip malformed entries
            continue
    
    return products


def parse_smm_safe(smm_text: Optional[str]) -> List[Dict[str, float]]:
    """
    Safe version of parse_smm that never raises exceptions.
    
    Args:
        smm_text: SMM text to parse
        
    Returns:
        List of parsed products, empty list on any error
    """
    try:
        return parse_smm(smm_text)
    except Exception:
        return []
