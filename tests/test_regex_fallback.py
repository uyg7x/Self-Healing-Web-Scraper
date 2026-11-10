import re

def test_regex_fallback_extraction():
    html = """
    <div class="product">
        <h2>Super Widget Pro</h2>
        <span class="price-tag">$49.99</span>
        <a href="/products/super-widget-pro">View Details</a>
    </div>
    """
    
  
    name_pattern = r'<h2[^>]*>(.*?)</h2>'
    price_pattern = r'\$[\d,]+\.?\d*'
    link_pattern = r'href="([^"]*)"'
    
   
    name_match = re.search(name_pattern, html)
    price_match = re.search(price_pattern, html)
    link_match = re.search(link_pattern, html)
    

    assert name_match is not None, "Regex failed to find product name"
    assert name_match.group(1) == "Super Widget Pro", f"Expected 'Super Widget Pro', got '{name_match.group(1)}'"
    
    assert price_match is not None, "Regex failed to find price"
    assert price_match.group(0) == "$49.99", f"Expected '$49.99', got '{price_match.group(0)}'"
    
    assert link_match is not None, "Regex failed to find link"
    assert link_match.group(1) == "/products/super-widget-pro", f"Expected '/products/super-widget-pro', got '{link_match.group(1)}'"
    
    print("✅ Regex fallback test passed!")

if __name__ == "__main__":
    test_regex_fallback_extraction()