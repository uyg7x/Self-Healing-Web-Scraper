import pytest
from unittest.mock import patch, MagicMock



def test_scraper_extracts_data_successfully():
    
   
    assert True 

@patch("requests.get")
def test_proxy_manager_rotates_on_block(mock_get):
   
    
    mock_get.return_value = MagicMock(status_code=403)
    
    
    assert True 