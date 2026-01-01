"""
JSON repair utilities to fix malformed JSON responses
"""
import json
import re
from typing import Optional, Dict, Any


def repair_json(json_str: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to repair malformed JSON by fixing common issues:
    - Trailing commas
    - Missing quotes
    - Unclosed brackets/braces
    - Invalid escape sequences
    - Comments
    """
    try:
        # First, try to parse as-is
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Try various repair strategies
    repaired = json_str
    
    # Strategy 1: Remove trailing commas before closing brackets/braces
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
    
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Remove comments (single-line and multi-line)
    repaired = re.sub(r'//.*?$', '', repaired, flags=re.MULTILINE)
    repaired = re.sub(r'/\*.*?\*/', '', repaired, flags=re.DOTALL)
    
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Fix unclosed strings (add closing quote if missing)
    # Count quotes to find unclosed strings
    lines = repaired.split('\n')
    fixed_lines = []
    for line in lines:
        # Simple heuristic: if line has odd number of unescaped quotes, might be unclosed
        unescaped_quotes = len(re.findall(r'(?<!\\)"', line))
        if unescaped_quotes % 2 == 1 and not line.strip().endswith('"'):
            # Try to add closing quote at end of value
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    value = parts[1].strip()
                    if value.startswith('"') and not value.endswith('"'):
                        line = parts[0] + ':' + value + '"'
        fixed_lines.append(line)
    repaired = '\n'.join(fixed_lines)
    
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    
    # Strategy 4: Extract the largest valid JSON object/array
    # Find all potential JSON structures
    json_objects = []
    
    # Find objects { ... }
    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', repaired, re.DOTALL):
        obj_str = match.group(0)
        try:
            parsed = json.loads(obj_str)
            json_objects.append((len(obj_str), parsed))
        except:
            pass
    
    # Find arrays [ ... ]
    for match in re.finditer(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', repaired, re.DOTALL):
        arr_str = match.group(0)
        try:
            parsed = json.loads(arr_str)
            json_objects.append((len(arr_str), parsed))
        except:
            pass
    
    if json_objects:
        # Return the largest valid JSON structure
        json_objects.sort(reverse=True, key=lambda x: x[0])
        return json_objects[0][1]
    
    # Strategy 5: Try to extract and fix partial JSON
    # Find the JSON-like structure and try to close it
    start_idx = repaired.find('{')
    if start_idx == -1:
        start_idx = repaired.find('[')
    
    if start_idx != -1:
        # Try to find matching closing bracket
        bracket_stack = []
        end_idx = start_idx
        
        for i in range(start_idx, len(repaired)):
            char = repaired[i]
            if char == '{' or char == '[':
                bracket_stack.append(char)
            elif char == '}' or char == ']':
                if bracket_stack:
                    bracket_stack.pop()
                    if not bracket_stack:
                        end_idx = i + 1
                        break
        
        if end_idx > start_idx:
            json_part = repaired[start_idx:end_idx]
            # Apply all fixes to this part
            json_part = re.sub(r',(\s*[}\]])', r'\1', json_part)
            json_part = re.sub(r'//.*?$', '', json_part, flags=re.MULTILINE)
            json_part = re.sub(r'/\*.*?\*/', '', json_part, flags=re.DOTALL)
            
            try:
                return json.loads(json_part)
            except:
                pass
    
    # Strategy 6: Try to build a minimal valid JSON from what we have
    # Extract key-value pairs even if structure is broken
    try:
        # Find all "key": "value" patterns
        kv_pattern = r'"([^"]+)":\s*"([^"]*)"'
        matches = re.findall(kv_pattern, repaired)
        
        if matches:
            result = {}
            for key, value in matches:
                result[key] = value
            return result
    except:
        pass
    
    # If all strategies fail, return None
    return None


def extract_partial_json(json_str: str) -> Optional[Dict[str, Any]]:
    """
    Extract partial data from malformed JSON by finding valid key-value pairs
    """
    result = {}
    
    # Extract stocks array if present
    stocks_pattern = r'"stocks"\s*:\s*\[(.*?)\]'
    stocks_match = re.search(stocks_pattern, json_str, re.DOTALL)
    if stocks_match:
        stocks_content = stocks_match.group(1)
        # Try to extract individual stock objects
        stock_pattern = r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"'
        stocks = []
        for match in re.finditer(stock_pattern, stocks_content):
            stocks.append({
                "symbol": match.group(1),
                "name": match.group(2)
            })
        if stocks:
            result["stocks"] = stocks
    
    # Extract indices array if present
    indices_pattern = r'"indices"\s*:\s*\[(.*?)\]'
    indices_match = re.search(indices_pattern, json_str, re.DOTALL)
    if indices_match:
        indices_content = indices_match.group(1)
        index_pattern = r'\{"name":\s*"([^"]+)",\s*"value":\s*"([^"]+)"'
        indices = []
        for match in re.finditer(index_pattern, indices_content):
            indices.append({
                "name": match.group(1),
                "value": match.group(2)
            })
        if indices:
            result["indices"] = indices
    
    # Extract market_overview if present
    overview_pattern = r'"market_overview"\s*:\s*"([^"]+)"'
    overview_match = re.search(overview_pattern, json_str)
    if overview_match:
        result["market_overview"] = overview_match.group(1)
    
    return result if result else None

