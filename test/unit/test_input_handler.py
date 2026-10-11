import pytest
from app.services.input_handler import InputHandler
from pathlib import Path
from test import test_resources

@pytest.fixture
def input_handler():
    return InputHandler()

@pytest.fixture
def valid_image_bytes():
    # Use path from local resources
    img_path = Path(test_resources.PNG_IMAGE_PATH)
    with open(img_path, "rb") as f:
        return f.read()

@pytest.fixture
def valid_pdf_bytes():
    # Use path from local resources
    pdf_path = Path(test_resources.PDF_IMAGE_PATH)
    with open(pdf_path, "rb") as f:
        return f.read()

def test_parse_image_success(input_handler, valid_image_bytes):
    """
    Verify that a valid image is correctly recognized and 
    returned as page 1.
    """
    # Act
    result = input_handler.parse_image(valid_image_bytes)
    
    # Assert
    assert len(result) == 1
    assert result[0][0] == 1
    assert result[0][1] == valid_image_bytes

def test_parse_image_failure(input_handler):
    """
    Verify that invalid data (not an image) 
    leads to an empty list.
    """
    # Arrange: Use random text instead of an image
    invalid_bytes = b"This is definitely not an image format!"
    
    # Act
    result = input_handler.parse_image(invalid_bytes)
    
    # Assert
    assert result == []

def test_parse_pdf_success(input_handler, valid_pdf_bytes):
    """
    Verify that a valid PDF is correctly split into 
    individual page images.
    """
    # Act
    result = input_handler.parse_pdf(valid_pdf_bytes)
    
    # Assert
    assert len(result) > 0
    # Check if the first element is a tuple (page number, bytes)
    assert isinstance(result[0], tuple)
    assert result[0][0] == 1
    assert isinstance(result[0][1], bytes)
    assert len(result[0][1]) > 0
